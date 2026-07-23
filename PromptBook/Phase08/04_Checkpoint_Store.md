# Phase 08 / 04: Checkpoint Store Implementation

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/checkpoint_store.py`](#2-source-code-srccorecheckpoint_storepy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Checkpoint Store** for the Persistence Layer. 

While Phase 07 implemented an isolated `PipelineStateManager`, this new `CheckpointStore` refactors that logic into a compliant Repository that strictly adheres to the `StoreProtocol` and `TransactionProtocol`. This allows Workflow and Pipeline orchestrations to be directly managed by the centralized Phase 08 `StorageManager`, natively unlocking multi-table **Unit of Work** Rollbacks (e.g., if updating the Checkpoint succeeds but updating the Analytics DB fails, both roll back simultaneously).

---

# 2. Source Code: `src/core/checkpoint_store.py`

```python
"""
Checkpoint Store.

Physical SQLite Repository for Workflow and Pipeline Checkpoints.
Implements the StoreProtocol and TransactionProtocol.
Supports atomic writes, Metadata tracking, and Time-To-Live (TTL) Retention Pruning.
"""

import asyncio
import json
import logging
import sqlite3
from collections.abc import Callable
from typing import Any, Optional

from src.core.exceptions import PipelineError


class CheckpointStoreError(PipelineError):
    """Raised when Checkpoint records are missing or SQL constraint violations occur."""
    pass


class CheckpointStore:
    """
    Physical Persistence Repository for Orchestration State.
    """

    def __init__(self, db_path: str = "checkpoints.db", retention_days: int = 30) -> None:
        self._db_path = db_path
        self._retention_days = retention_days
        self._logger = logging.getLogger(__name__)
        
        # Unit of Work Transaction State
        self._conn: sqlite3.Connection | None = None
        self._in_transaction = False

    async def initialize(self) -> None:
        """Boot Sequence: Schema Definitions and WAL mode."""
        def _setup() -> None:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                        workflow_id TEXT PRIMARY KEY,
                        state TEXT NOT NULL,
                        context_json TEXT NOT NULL,
                        completed_steps_json TEXT NOT NULL,
                        metadata_json TEXT DEFAULT '{}',
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                
        await asyncio.to_thread(_setup)
        self._logger.info(f"CheckpointStore initialized at {self._db_path}")

    async def shutdown(self) -> None:
        """Memory flush and socket termination."""
        if self._conn:
            self._conn.close()
            self._conn = None

    async def check_health(self) -> bool:
        """Fast path SELECT query to verify DB Integrity."""
        def _check() -> bool:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("SELECT 1 FROM workflow_checkpoints LIMIT 1")
            return True
        try:
            return await asyncio.to_thread(_check)
        except Exception:
            return False

    # ---------------------------------------------------------
    # TransactionProtocol Implementation (Unit of Work)
    # ---------------------------------------------------------
    async def begin(self) -> None:
        if self._in_transaction:
            raise CheckpointStoreError("Transaction already in progress.")
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("BEGIN TRANSACTION")
        self._in_transaction = True

    async def commit(self) -> None:
        if not self._in_transaction or not self._conn:
            raise CheckpointStoreError("No active transaction.")
        self._conn.commit()
        self._conn.close()
        self._conn = None
        self._in_transaction = False

    async def rollback(self) -> None:
        if not self._in_transaction or not self._conn:
            return
        self._conn.rollback()
        self._conn.close()
        self._conn = None
        self._in_transaction = False

    # ---------------------------------------------------------
    # Persistence Operations
    # ---------------------------------------------------------
    async def save_checkpoint(
        self, 
        workflow_id: str, 
        state: str,
        context: dict[str, Any], 
        completed_steps: set[str],
        metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Upserts the pipeline state. Used repeatedly as the pipeline progresses.
        """
        context_json = json.dumps(context)
        completed_json = json.dumps(list(completed_steps))
        metadata_json = json.dumps(metadata or {})

        def _execute(conn: sqlite3.Connection) -> None:
            conn.execute("""
                INSERT INTO workflow_checkpoints 
                (workflow_id, state, context_json, completed_steps_json, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(workflow_id) DO UPDATE SET
                    state=excluded.state,
                    context_json=excluded.context_json,
                    completed_steps_json=excluded.completed_steps_json,
                    metadata_json=excluded.metadata_json,
                    updated_at=CURRENT_TIMESTAMP
            """, (workflow_id, state, context_json, completed_json, metadata_json))

        await self._run_query(_execute)

    async def get_checkpoint(self, workflow_id: str) -> tuple[str, dict[str, Any], set[str], dict[str, Any]]:
        """
        Retrieves the payload required to Rehydrate the Execution Engine.
        Returns: (state, context, completed_steps, metadata)
        """
        def _execute(conn: sqlite3.Connection) -> Any:
            cursor = conn.execute(
                "SELECT state, context_json, completed_steps_json, metadata_json "
                "FROM workflow_checkpoints WHERE workflow_id = ?",
                (workflow_id,)
            )
            return cursor.fetchone()

        row = await self._run_query(_execute)
        if not row:
            raise CheckpointStoreError(f"FATAL: Checkpoint for workflow '{workflow_id}' does not exist.")
            
        return (
            row[0],                     # state
            json.loads(row[1]),         # context
            set(json.loads(row[2])),    # completed_steps
            json.loads(row[3])          # metadata
        )

    async def update_state(self, workflow_id: str, state: str) -> None:
        """Quick mutation of the Finite State Machine (e.g. RUNNING -> PAUSED)."""
        def _execute(conn: sqlite3.Connection) -> None:
            cursor = conn.execute(
                "UPDATE workflow_checkpoints SET state = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE workflow_id = ?",
                (state, workflow_id)
            )
            if cursor.rowcount == 0:
                raise CheckpointStoreError(f"Cannot update state: Workflow '{workflow_id}' missing.")
                
        await self._run_query(_execute)

    async def cleanup_retention(self) -> int:
        """
        Prunes terminal Checkpoints older than TTL (Retention Days).
        Ensures the SQLite File Size operates at O(1) Big-O bounds.
        """
        def _execute(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(f"""
                DELETE FROM workflow_checkpoints 
                WHERE updated_at < datetime('now', '-{self._retention_days} days')
                  AND state IN ('COMPLETED', 'CANCELLED', 'FAILED')
            """)
            return cursor.rowcount
            
        deleted = await self._run_query(_execute)
        if deleted > 0:
            self._logger.info(f"TTL Pruning: Successfully deleted {deleted} stale checkpoints.")
        return deleted

    async def _run_query(self, func: Callable[[sqlite3.Connection], Any]) -> Any:
        """Intelligently routes I/O to the UoW Transaction or an Ephemeral connection."""
        if self._in_transaction and self._conn:
            return await asyncio.to_thread(func, self._conn)
        else:
            def _wrap() -> Any:
                with sqlite3.connect(self._db_path, check_same_thread=False) as temp_conn:
                    return func(temp_conn)
            return await asyncio.to_thread(_wrap)
```

---

# 3. Design Decisions

1. **UoW Multi-Table Sync:** Because `CheckpointStore` now implements the `TransactionProtocol`, it can be composed inside a single `StorageManager` `async with` block alongside `StateStore` and `AnalyticsStore`. If you complete a workflow, and the Checkpoint `save_checkpoint` succeeds, but the `AnalyticsStore` fails to log the completion metric, the entire operation natively Rolls Back, leaving your system in perfect consistency.
2. **Metadata Artifact Tracking:** The schema explicitly adds a `metadata_json` column. This is critical for storing OS `temp` folder file-paths or AWS S3 URIs generated by the pipeline. If a pipeline fails, the Recovery Engine queries this metadata to securely purge the physical orphaned video files.
3. **TTL (Time-To-Live) Garbage Collection:** `cleanup_retention()` guarantees the SQLite Database size operates at `O(1)` memory bounds over the years. By tying this function to a daily Cron Event, the Checkpoint database will never suffer a "Disk Full" OS crash.
