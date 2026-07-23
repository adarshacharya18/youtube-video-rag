# Phase 07 / 08: Workflow Checkpointing Implementation

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/pipeline_state.py`](#2-source-code-srccorepipeline_statepy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Pipeline State Manager** (Checkpoint Engine). 

Because rendering and uploading videos can take hours, protecting the system from power loss or OS-level crashes is non-negotiable. This component implements a robust, Zero-Dependency SQLite layer. 

It satisfies the `StateManagerProtocol` defined by the Workflow Executor. At the end of every successful parallel execution batch, it securely locks the SQLite database and writes the exact JSON snapshot of the `PipelineContext` and the mathematical `completed_steps` Set. If the pipeline reboots, the Orchestrator requests the Checkpoint, perfectly rehydrates the Execution Graph, and continues seamlessly without losing a single compute cycle.

---

# 2. Source Code: `src/core/pipeline_state.py`

```python
"""
Pipeline State & Checkpoint Manager.

Implements robust SQLite-backed checkpointing for Workflow executions.
Guarantees atomicity and supports snapshot pruning (Retention Policies) 
and Artifact Physical Validation.
"""

import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from src.core.exceptions import PipelineError


class CheckpointError(PipelineError):
    """Raised when a checkpoint is mathematically corrupted or missing critical artifacts."""
    pass


class PipelineStateManager:
    """
    SQLite-backed Persistence Layer.
    Utilizes WAL mode and asyncio.to_thread to guarantee zero blocking on the Event Loop.
    """

    def __init__(self, db_path: str = "pipeline_checkpoints.db", retention_days: int = 30) -> None:
        self._db_path = db_path
        self._retention_days = retention_days
        self._logger = logging.getLogger(__name__)
        self._setup_db()

    def _setup_db(self) -> None:
        """Synchronous boot sequence to prepare the schema."""
        with sqlite3.connect(self._db_path) as conn:
            # WAL mode allows concurrent Read/Writes across threads without locking the whole file
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    workflow_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    completed_steps_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    async def save_checkpoint(
        self, 
        workflow_id: str, 
        context: dict[str, Any], 
        completed_steps: set[str]
    ) -> None:
        """Atomically upserts the immutable Pipeline Context and DAG progression state."""
        context_json = json.dumps(context)
        completed_json = json.dumps(list(completed_steps))
        
        def _write() -> None:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    INSERT INTO checkpoints (workflow_id, state, context_json, completed_steps_json, updated_at)
                    VALUES (?, 'RUNNING', ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(workflow_id) DO UPDATE SET
                        context_json=excluded.context_json,
                        completed_steps_json=excluded.completed_steps_json,
                        updated_at=CURRENT_TIMESTAMP
                """, (workflow_id, context_json, completed_json))
                conn.commit()
                
        # Transport SQLite I/O directly to a background C-Thread
        await asyncio.to_thread(_write)

    async def get_checkpoint(self, workflow_id: str) -> tuple[dict[str, Any], set[str]]:
        """Reads and rigorously validates the last known stable state of the Pipeline."""
        def _read() -> tuple[Any, Any] | None:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    "SELECT context_json, completed_steps_json FROM checkpoints WHERE workflow_id = ?", 
                    (workflow_id,)
                )
                return cursor.fetchone()
        
        row = await asyncio.to_thread(_read)
        if not row:
            # Fresh Pipeline (No previous checkpoint)
            return {}, set()
            
        try:
            context = json.loads(row[0])
            completed_steps = set(json.loads(row[1]))
            return context, completed_steps
        except json.JSONDecodeError as e:
            raise CheckpointError(f"Fatal Checkpoint JSON corruption for {workflow_id}: {e}") from e

    async def update_state(self, workflow_id: str, state: str) -> None:
        """
        Updates the high-level Finite State Machine (FSM).
        (e.g., transitioning from RUNNING -> PAUSED).
        """
        def _write() -> None:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    INSERT INTO checkpoints (workflow_id, state, context_json, completed_steps_json, updated_at)
                    VALUES (?, ?, '{}', '[]', CURRENT_TIMESTAMP)
                    ON CONFLICT(workflow_id) DO UPDATE SET
                        state=excluded.state,
                        updated_at=CURRENT_TIMESTAMP
                """, (workflow_id, state))
                conn.commit()
                
        await asyncio.to_thread(_write)

    async def enforce_retention(self) -> int:
        """
        Prunes terminal checkpoints older than retention_days. 
        Guarantees the SQLite file does not bloat indefinitely over years of operation.
        """
        def _prune() -> int:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(f"""
                    DELETE FROM checkpoints 
                    WHERE updated_at < datetime('now', '-{self._retention_days} days')
                      AND state IN ('COMPLETED', 'CANCELLED', 'FAILED')
                """)
                deleted = cursor.rowcount
                conn.commit()
                return deleted
        
        deleted = await asyncio.to_thread(_prune)
        if deleted > 0:
            self._logger.info(f"Checkpoint Pruning: Safely deleted {deleted} stale workflow states.")
        return deleted

    async def validate_artifacts(self, workflow_id: str) -> bool:
        """
        Deep Validation: Iterates through the Context Checkpoint dictionary.
        If it finds absolute file paths pointing to OS artifacts (e.g., /tmp/script.md), 
        it strictly verifies the file has not been deleted by the OS since the checkpoint was written.
        """
        context, _ = await self.get_checkpoint(workflow_id)
        
        for key, value in context.items():
            if isinstance(value, str) and value.startswith("/") and "." in value:
                path = Path(value)
                if not path.exists():
                    self._logger.error(
                        f"Artifact Validation Failed: Context key '{key}' expects file at '{path}', "
                        "but the file is missing from the Operating System."
                    )
                    return False
        return True
```

---

# 3. Design Decisions

1. **Artifact Reference Integrity:** If a pipeline pauses for 3 days, and the OS temp-file cleanup script deletes `/tmp/video.mp4`, attempting to resume the pipeline will result in a disastrous internal failure when the Youtube Uploader tries to read the missing file. The `validate_artifacts()` method scans the `Context` for filepaths and strictly checks OS existence, warning the Administrator *before* they try to resume a fatally corrupted Checkpoint.
2. **Data-Loss Protection (WAL Mode):** During `__init__`, we execute `PRAGMA journal_mode=WAL;`. This turns on Write-Ahead Logging in SQLite. If a concurrent workflow is saving a checkpoint at the exact same millisecond that a Dashboard is trying to read another checkpoint, WAL mode prevents the dreaded `database is locked` Operational Error, natively unlocking multi-threaded Database concurrency.
3. **Automated Pruning (Retention Policy):** The `enforce_retention()` method guarantees O(1) disk space complexity. By hooking this to a daily scheduler, the database will never grow beyond `retention_days` (default: 30), preventing "Disk Full" outages that commonly plague long-running logging servers. It strictly guards against deleting `RUNNING` or `PAUSED` pipelines, only pruning `COMPLETED`, `CANCELLED`, or `FAILED` runs.
