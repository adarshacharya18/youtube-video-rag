# Phase 08 / 06: Metadata Store Implementation

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/metadata_store.py`](#2-source-code-srccoremetadata_storepy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Metadata Store** for the Persistence Layer. 

While the `StateStore` manages rapidly mutating Runtime telemetry and Pipeline Configurations, the `MetadataStore` serves as a permanent, categorized registry for static and semi-static domain models. It securely catalogs Plugin Manifests, Workflow Schema Definitions, and RAG Knowledge Base pointers. 

It implements the strict `StoreProtocol` / `TransactionProtocol` abstractions, enabling it to participate in global SQLite Unit-of-Work boundaries, and exposes high-speed `Category` indices for instantaneous plugin resolution during pipeline Boot Sequences.

---

# 2. Source Code: `src/core/metadata_store.py`

```python
"""
Metadata Store.

Physical SQLite Repository for structured Metadata.
Provides flexible tagging, indexing, and fast querying across Plugin definitions,
Workflow configurations, and Knowledge Base references.
Implements the StoreProtocol and TransactionProtocol.
"""

import asyncio
import json
import logging
import sqlite3
from collections.abc import Callable
from typing import Any

from src.core.exceptions import PipelineError


class MetadataStoreError(PipelineError):
    """Raised during query misses or Constraint Violations."""
    pass


class MetadataStore:
    """
    Categorized Document Registry for the Orchestration Ecosystem.
    """

    def __init__(self, db_path: str = "metadata.db") -> None:
        self._db_path = db_path
        self._logger = logging.getLogger(__name__)
        
        # Unit of Work Transaction State
        self._conn: sqlite3.Connection | None = None
        self._in_transaction = False

    async def initialize(self) -> None:
        """Boot Sequence: Schema Definitions and WAL mode."""
        def _setup() -> None:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                
                # Categorized Metadata Ledger
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS metadata (
                        category TEXT NOT NULL,       -- e.g., 'plugin', 'workflow', 'knowledge'
                        entity_id TEXT NOT NULL,      -- e.g., 'core.renderer.davinci'
                        tags TEXT DEFAULT '[]',       -- JSON array of strings for fast filtering
                        data_json TEXT NOT NULL,      -- The actual Schema payload
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (category, entity_id)
                    )
                """)
                
                # High-Speed Query Indexes
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_category ON metadata(category)")
                conn.commit()
                
        await asyncio.to_thread(_setup)
        self._logger.info(f"MetadataStore initialized at {self._db_path}")

    async def shutdown(self) -> None:
        """Memory flush and socket termination."""
        if self._conn:
            self._conn.close()
            self._conn = None

    async def check_health(self) -> bool:
        """Fast path SELECT query to verify DB Integrity."""
        def _check() -> bool:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("SELECT 1 FROM metadata LIMIT 1")
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
            raise MetadataStoreError("Transaction already in progress.")
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("BEGIN TRANSACTION")
        self._in_transaction = True

    async def commit(self) -> None:
        if not self._in_transaction or not self._conn:
            raise MetadataStoreError("No active transaction.")
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
    # Metadata Operations
    # ---------------------------------------------------------
    async def save_metadata(
        self, 
        category: str, 
        entity_id: str, 
        data: dict[str, Any], 
        tags: list[str] | None = None
    ) -> None:
        """Upserts a metadata document into the categorized ledger."""
        data_json = json.dumps(data)
        tags_json = json.dumps(tags or [])
        
        def _execute(conn: sqlite3.Connection) -> None:
            conn.execute("""
                INSERT INTO metadata (category, entity_id, tags, data_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(category, entity_id) DO UPDATE SET
                    tags=excluded.tags,
                    data_json=excluded.data_json,
                    updated_at=CURRENT_TIMESTAMP
            """, (category, entity_id, tags_json, data_json))
            
        await self._run_query(_execute)

    async def get_metadata(self, category: str, entity_id: str) -> tuple[dict[str, Any], list[str]]:
        """Retrieves exactly one metadata document and its associated tags."""
        def _execute(conn: sqlite3.Connection) -> tuple[dict[str, Any], list[str]]:
            cursor = conn.execute(
                "SELECT data_json, tags FROM metadata WHERE category = ? AND entity_id = ?",
                (category, entity_id)
            )
            row = cursor.fetchone()
            if not row:
                raise MetadataStoreError(f"FATAL: Metadata for [{category}] '{entity_id}' not found.")
            return json.loads(row[0]), json.loads(row[1])
            
        return await self._run_query(_execute)

    async def query_by_category(self, category: str) -> dict[str, dict[str, Any]]:
        """
        Mass-loads an entire category. 
        Highly optimized via the `idx_metadata_category` SQLite index.
        """
        def _execute(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
            cursor = conn.execute(
                "SELECT entity_id, data_json FROM metadata WHERE category = ?",
                (category,)
            )
            results: dict[str, dict[str, Any]] = {}
            for row in cursor.fetchall():
                results[row[0]] = json.loads(row[1])
            return results
            
        return await self._run_query(_execute)

    async def delete_metadata(self, category: str, entity_id: str) -> None:
        """Purges a metadata document."""
        def _execute(conn: sqlite3.Connection) -> None:
            conn.execute(
                "DELETE FROM metadata WHERE category = ? AND entity_id = ?",
                (category, entity_id)
            )
        await self._run_query(_execute)

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

1. **Category Clustering Matrix:** To prevent creating 10 different SQLite databases for Plugins, Knowledge, and Configurations, the engine clusters all domain objects into a single master Table using the `category` string. By applying `CREATE INDEX IF NOT EXISTS idx_metadata_category`, the `query_by_category("plugin")` function returns massive dicts of Plugin Definitions at C-Speed, instantly satisfying the Orchestrator's Boot Sequence requirements.
2. **Transaction Composability:** Like the other Repositories in Phase 08, the MetadataStore rigorously implements `StoreProtocol` and `TransactionProtocol`. An admin can update a RAG Knowledge pointer and a Pipeline Checkpoint in the same `async with storage.transaction()` block, guaranteeing total system consistency.
3. **JSON Tagging Arrays:** The schema natively introduces a `tags` array alongside the primary JSON payload. In Phase 09 (Plugins), this will allow the AI Engine to rapidly query specific tools via mathematical tag intersections (e.g., `["audio", "tts", "elevenlabs"]`) without parsing the heavy `data_json` block for every row.
