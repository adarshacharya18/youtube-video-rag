"""
Event Store.

Physical SQLite Repository for Event Sourcing and the Dead Letter Queue.
Implements the StoreProtocol and TransactionProtocol.
Supports high-throughput Event logging, querying, and Replay logic.
"""

import asyncio
import json
import logging
import sqlite3
from collections.abc import Callable
from typing import Any, Optional

from src.core.events import Event
from src.core.exceptions import PipelineError


class EventStoreError(PipelineError):
    """Raised during query failures or Dead Letter Queue access errors."""
    pass


class EventStore:
    """
    Physical Persistence Repository for Event Sourcing.
    """

    def __init__(self, db_path: str = "event_bus.db") -> None:
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
                
                # Primary Event Source Ledger
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS event_log (
                        event_id TEXT PRIMARY KEY,
                        topic TEXT NOT NULL,
                        correlation_id TEXT,
                        payload_json TEXT NOT NULL,
                        metadata_json TEXT DEFAULT '{}',
                        status TEXT DEFAULT 'PUBLISHED',
                        timestamp REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Dead Letter Queue for Replay Infrastructure
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS dead_letters (
                        event_id TEXT PRIMARY KEY,
                        topic TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        error_reason TEXT NOT NULL,
                        retry_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # High-Performance Query Indexes
                conn.execute("CREATE INDEX IF NOT EXISTS idx_event_topic ON event_log(topic)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_event_correlation ON event_log(correlation_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_dlq_topic ON dead_letters(topic)")
                
                conn.commit()
                
        await asyncio.to_thread(_setup)
        self._logger.info(f"EventStore initialized at {self._db_path}")

    async def shutdown(self) -> None:
        """Memory flush and socket termination."""
        if self._conn:
            self._conn.close()
            self._conn = None

    async def check_health(self) -> bool:
        """Fast path SELECT query to verify DB Integrity."""
        def _check() -> bool:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("SELECT 1 FROM event_log LIMIT 1")
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
            raise EventStoreError("Transaction already in progress.")
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("BEGIN TRANSACTION")
        self._in_transaction = True

    async def commit(self) -> None:
        if not self._in_transaction or not self._conn:
            raise EventStoreError("No active transaction.")
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
    # Event Sourcing & Ledger Operations
    # ---------------------------------------------------------
    async def append_event(self, event: Event, status: str = "PUBLISHED") -> None:
        """Appends an event to the immutable Event Source Ledger."""
        payload_json = json.dumps(event.payload)
        meta_json = json.dumps(event.metadata)
        
        def _execute(conn: sqlite3.Connection) -> None:
            conn.execute("""
                INSERT INTO event_log 
                (event_id, topic, correlation_id, payload_json, metadata_json, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    status=excluded.status
            """, (event.id, event.topic, event.correlation_id, payload_json, meta_json, status, event.timestamp))
            
        await self._run_query(_execute)

    async def query_events(self, topic: Optional[str] = None, correlation_id: Optional[str] = None) -> list[Event]:
        """Queries the Ledger via fast-path Indexes. Essential for Analytics and Subagent tracing."""
        def _execute(conn: sqlite3.Connection) -> list[Event]:
            query = "SELECT event_id, topic, correlation_id, payload_json, metadata_json, timestamp FROM event_log WHERE 1=1"
            params: list[Any] = []
            
            if topic:
                query += " AND topic = ?"
                params.append(topic)
                
            if correlation_id:
                query += " AND correlation_id = ?"
                params.append(correlation_id)
                
            query += " ORDER BY timestamp ASC"
            
            cursor = conn.execute(query, params)
            results: list[Event] = []
            
            for row in cursor.fetchall():
                e = Event(
                    topic=row[1],
                    payload=json.loads(row[3]),
                    correlation_id=row[2],
                    metadata=json.loads(row[4])
                )
                e.id = row[0]
                e.timestamp = row[5]
                results.append(e)
            return results
            
        return await self._run_query(_execute)

    # ---------------------------------------------------------
    # Dead Letter Queue (Replay) Operations
    # ---------------------------------------------------------
    async def append_dlq(self, event: Event, error_reason: str) -> None:
        """Pushes an unprocessable event into the Dead Letter Queue."""
        payload_json = json.dumps(event.payload)
        
        def _execute(conn: sqlite3.Connection) -> None:
            conn.execute("""
                INSERT INTO dead_letters (event_id, topic, payload_json, error_reason)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    retry_count = retry_count + 1,
                    error_reason = excluded.error_reason
            """, (event.id, event.topic, payload_json, error_reason))
            
        await self._run_query(_execute)

    async def get_dlq_events(self) -> list[tuple[Event, str, int]]:
        """Yields (Event, ErrorReason, RetryCount) for manual or automated Replay loops."""
        def _execute(conn: sqlite3.Connection) -> list[tuple[Event, str, int]]:
            cursor = conn.execute(
                "SELECT event_id, topic, payload_json, error_reason, retry_count FROM dead_letters"
            )
            results: list[tuple[Event, str, int]] = []
            
            for row in cursor.fetchall():
                e = Event(
                    topic=row[1],
                    payload=json.loads(row[2])
                )
                e.id = row[0]
                results.append((e, row[3], row[4]))
            return results
            
        return await self._run_query(_execute)
        
    async def remove_dlq_event(self, event_id: str) -> None:
        """Permanently purges an event from the DLQ after a successful Replay."""
        def _execute(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM dead_letters WHERE event_id = ?", (event_id,))
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
