"""
Generalized State Store.

An ACID-compliant, versioned key-value document store powered by SQLite.
Implements the StoreProtocol and TransactionProtocol.
Stores generic states for Plugins, Pipelines, and the Core Runtime.
"""

import asyncio
import json
import logging
import sqlite3
from collections.abc import Callable
from typing import Any, Optional

from src.core.exceptions import PipelineError


class StateStoreError(PipelineError):
    """Base exception for Storage errors."""
    pass


class ConcurrencyCollisionError(StateStoreError):
    """Raised when Optimistic Locking detects a version mismatch during updates."""
    pass


class StateStore:
    """
    Universal Document Store for the Pipeline Ecosystem.
    """

    def __init__(self, db_path: str = "core_state.db") -> None:
        self._db_path = db_path
        self._logger = logging.getLogger(__name__)
        
        # Transaction State
        self._conn: sqlite3.Connection | None = None
        self._in_transaction = False

    async def initialize(self) -> None:
        """Executes Schema Migrations on boot."""
        def _setup() -> None:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                
                # Primary Key-Value Document Store
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS states (
                        entity_type TEXT NOT NULL,
                        entity_id TEXT NOT NULL,
                        data_json TEXT NOT NULL,
                        version INTEGER NOT NULL DEFAULT 1,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (entity_type, entity_id)
                    )
                """)
                
                # Append-Only Ledger for Point-in-Time Recovery
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS state_snapshots (
                        snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        entity_type TEXT NOT NULL,
                        entity_id TEXT NOT NULL,
                        data_json TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                
        await asyncio.to_thread(_setup)
        self._logger.info(f"StateStore initialized at {self._db_path}")

    async def shutdown(self) -> None:
        """Flushes memory locks."""
        if self._conn:
            self._conn.close()
            self._conn = None
        self._logger.info("StateStore cleanly shut down.")

    async def check_health(self) -> bool:
        """Proves DB connectivity."""
        def _check() -> bool:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("SELECT 1")
            return True
        try:
            return await asyncio.to_thread(_check)
        except Exception:
            return False

    # ---------------------------------------------------------
    # TransactionProtocol Implementation (Unit of Work)
    # ---------------------------------------------------------
    async def begin(self) -> None:
        """Locks a dedicated DB connection for atomic writes."""
        if self._in_transaction:
            raise StateStoreError("Transaction already in progress on this store instance.")
            
        # check_same_thread=False allows asyncio.to_thread to execute on this connection
        # Safe because the StorageManager UoW context strictly enforces sequential awaits
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("BEGIN TRANSACTION")
        self._in_transaction = True

    async def commit(self) -> None:
        """Physically commits the UoW batch to the SSD."""
        if not self._in_transaction or not self._conn:
            raise StateStoreError("No active transaction to commit.")
            
        self._conn.commit()
        self._conn.close()
        self._conn = None
        self._in_transaction = False

    async def rollback(self) -> None:
        """Physically undoes the UoW batch if Business Logic crashed."""
        if not self._in_transaction or not self._conn:
            return
            
        self._conn.rollback()
        self._conn.close()
        self._conn = None
        self._in_transaction = False

    # ---------------------------------------------------------
    # CRUD, Versioning, & Snapshots
    # ---------------------------------------------------------
    async def read(self, entity_type: str, entity_id: str) -> tuple[Optional[dict[str, Any]], int]:
        """Returns a Tuple of (JSON_Data, Version_Integer)."""
        def _execute(conn: sqlite3.Connection) -> tuple[Optional[dict[str, Any]], int]:
            cursor = conn.execute(
                "SELECT data_json, version FROM states WHERE entity_type = ? AND entity_id = ?",
                (entity_type, entity_id)
            )
            row = cursor.fetchone()
            if not row:
                return None, 0
            return json.loads(row[0]), row[1]

        return await self._run_query(_execute)

    async def write(
        self, 
        entity_type: str, 
        entity_id: str, 
        data: dict[str, Any], 
        expected_version: Optional[int] = None
    ) -> int:
        """
        Creates or updates a state. Utilizes Optimistic Locking.
        Automatically appends a Snapshot ledger entry.
        """
        data_json = json.dumps(data)

        def _execute(conn: sqlite3.Connection) -> int:
            # 1. Version Check
            cursor = conn.execute(
                "SELECT version FROM states WHERE entity_type = ? AND entity_id = ?",
                (entity_type, entity_id)
            )
            row = cursor.fetchone()
            current_version = row[0] if row else 0

            if expected_version is not None and expected_version != current_version:
                raise ConcurrencyCollisionError(
                    f"Optimistic Lock Failure: {entity_type} '{entity_id}' is at version {current_version}, "
                    f"but process expected {expected_version}. Another thread modified the data!"
                )

            new_version = current_version + 1

            # 2. Upsert State
            if current_version == 0:
                conn.execute(
                    "INSERT INTO states (entity_type, entity_id, data_json, version) VALUES (?, ?, ?, ?)",
                    (entity_type, entity_id, data_json, new_version)
                )
            else:
                conn.execute(
                    "UPDATE states SET data_json = ?, version = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE entity_type = ? AND entity_id = ?",
                    (data_json, new_version, entity_type, entity_id)
                )
                
            # 3. Snapshot Generation (Audit Trail)
            conn.execute(
                "INSERT INTO state_snapshots (entity_type, entity_id, data_json, version) VALUES (?, ?, ?, ?)",
                (entity_type, entity_id, data_json, new_version)
            )
            
            return new_version

        return await self._run_query(_execute)
        
    async def delete(self, entity_type: str, entity_id: str) -> None:
        """Purges a record. (Snapshots remain intact for audit purposes)."""
        def _execute(conn: sqlite3.Connection) -> None:
            conn.execute(
                "DELETE FROM states WHERE entity_type = ? AND entity_id = ?", 
                (entity_type, entity_id)
            )
            
        await self._run_query(_execute)

    async def _run_query(self, func: Callable[[sqlite3.Connection], Any]) -> Any:
        """Intelligently routes I/O to the UoW Transaction or a standalone Ephemeral connection."""
        if self._in_transaction and self._conn:
            # We are inside the UnitOfWork! Run synchronously on the locked connection.
            return await asyncio.to_thread(func, self._conn)
        else:
            # Standalone Ephemeral execution
            def _wrap() -> Any:
                with sqlite3.connect(self._db_path, check_same_thread=False) as temp_conn:
                    # Native context manager handles ephemeral commit/rollback
                    return func(temp_conn)
            return await asyncio.to_thread(_wrap)
