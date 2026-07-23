"""
Event Persistence Layer.

Provides Crash Recovery and Audit Logging by persisting all Event Bus traffic
to disk. Supports native SQLite with structural typing for future PostgreSQL swap.
"""

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Protocol

from src.core.events import Event
from src.core.exceptions import PipelineError


class PersistenceError(PipelineError):
    """Raised on critical database I/O failures."""
    pass


class EventStatus(str, Enum):
    """Tracks the lifecycle of an Event inside the physical database."""
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DLQ = "DLQ"


class EventStoreProtocol(Protocol):
    """
    Structural interface for Event Stores.
    Allows us to seamlessly swap SQLite for PostgreSQL in Production later.
    """
    async def save(self, event: Event, status: EventStatus = EventStatus.PENDING) -> None: ...
    async def update_status(self, event_id: str, status: EventStatus) -> None: ...
    async def get_pending(self) -> list[Event]: ...
    async def cleanup(self, retention_days: int) -> int: ...


class SQLiteEventStore:
    """
    Zero-dependency SQLite backing store.
    Wraps standard synchronous sqlite3 operations inside asyncio.to_thread 
    to prevent Database I/O from freezing the master Event Loop.
    """

    def __init__(self, db_path: str = "pipeline_events.db") -> None:
        self.db_path = db_path
        self._logger = logging.getLogger(__name__)
        
        # Synchronous initialization to guarantee the table exists before Boot
        self._init_db()

    def _init_db(self) -> None:
        """Compiles the SQL schema and indexes."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    correlation_id TEXT,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
            """)
            # Indexes optimize Crash Recovery queries and Cleanup scans
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON events(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_topic ON events(topic)")
            self._logger.debug(f"SQLite Event Store initialized at '{self.db_path}'")

    async def save(self, event: Event, status: EventStatus = EventStatus.PENDING) -> None:
        """Backs up the event payload to disk. Usually called by Ingress Middleware."""
        def _insert() -> None:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO events 
                    (event_id, topic, trace_id, correlation_id, status, retry_count, timestamp, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.topic,
                        event.trace_id,
                        event.correlation_id,
                        status.value,
                        event.retry_count,
                        event.timestamp.isoformat(),
                        event.to_json()  # Natively dump the Pydantic model to string
                    )
                )
        await asyncio.to_thread(_insert)

    async def update_status(self, event_id: str, status: EventStatus) -> None:
        """Marks an event as COMPLETED or DLQ. Usually called by Egress Middleware."""
        def _update() -> None:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE events SET status = ? WHERE event_id = ?", (status.value, event_id))
        await asyncio.to_thread(_update)

    async def get_pending(self) -> list[Event]:
        """
        Extracts all PENDING events. 
        Triggered on System Boot for crash recovery operations.
        """
        def _select() -> list[Event]:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT payload_json FROM events WHERE status = ?", 
                    (EventStatus.PENDING.value,)
                )
                # Rehydrate the JSON strings back into immutable Pydantic Event objects
                return [Event.from_json(row[0]) for row in cursor.fetchall()]
                
        recovered = await asyncio.to_thread(_select)
        if recovered:
            self._logger.info(f"Recovered {len(recovered)} PENDING events from previous crash.")
        return recovered

    async def cleanup(self, retention_days: int = 7) -> int:
        """
        Archiving / Garbage Collection mechanism.
        Deletes COMPLETED events older than retention_days to prevent database bloat.
        """
        # Calculate the absolute UTC cutoff threshold
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        
        def _delete() -> int:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM events WHERE status = ? AND timestamp < ?", 
                    (EventStatus.COMPLETED.value, cutoff)
                )
                return cursor.rowcount
                
        count = await asyncio.to_thread(_delete)
        self._logger.info(f"Cleanup Agent purged {count} stale events from SQLite.")
        return count
