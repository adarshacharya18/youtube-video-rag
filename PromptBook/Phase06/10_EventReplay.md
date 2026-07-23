# Phase06/10_EventReplay.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/event_replay.py`](#2-source-code-srccoreevent_replaypy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Event Replay Engine**. 

When building a fully automated Video Rendering Pipeline, transient failures are inevitable (e.g., a 3rd-party Text-To-Speech API goes down for 5 minutes). When the API recovers, we do not want to restart the 2-hour video rendering process from scratch. 

The `EventReplayer` allows administrators to query the `SQLiteEventStore` for specific failed checkpoints (using Workflow IDs or Time Ranges) and mathematically re-inject those exact historic events back into the active `EventBus`. This triggers the downstream plugins to pick up exactly where they left off, saving immense computational time and money.

---

# 2. Source Code: `src/core/event_replay.py`

```python
"""
Event Replay Engine.

Allows administrators to recover failed pipelines by querying archived events
from the Persistence Layer and injecting them back into the active Event Bus.
"""

import asyncio
import logging
import sqlite3
from datetime import datetime
from typing import Any, Optional

from src.core.event_bus import EventBus
from src.core.events import Event
from src.core.exceptions import PipelineError


class ReplayError(PipelineError):
    """Raised when an Event Replay query fails."""
    pass


class EventReplayer:
    """
    Query and Re-injection engine for recovering failed or lost pipelines.
    Supports Dry Runs and granular JSON-based payload filtering.
    """

    def __init__(self, db_path: str, event_bus: EventBus) -> None:
        self.db_path = db_path
        self._bus = event_bus
        self._logger = logging.getLogger(__name__)

    async def _query_events(
        self,
        pipeline_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        topic: Optional[str] = None,
        correlation_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> list[Event]:
        """
        Constructs a dynamic SQL query to extract historic events.
        Leverages SQLite native JSON_EXTRACT functions to query inside payloads.
        """
        query = "SELECT payload_json FROM events WHERE 1=1"
        params: list[Any] = []
        
        if topic:
            query += " AND topic = ?"
            params.append(topic)
            
        if correlation_id:
            query += " AND correlation_id = ?"
            params.append(correlation_id)
            
        if pipeline_id:
            # Pydantic natively embeds pipeline_id inside the JSON blob.
            query += " AND json_extract(payload_json, '$.pipeline_id') = ?"
            params.append(pipeline_id)
            
        if workflow_id:
            query += " AND json_extract(payload_json, '$.workflow_id') = ?"
            params.append(workflow_id)
            
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
            
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())
            
        # Chronological ordering is strictly enforced to prevent causality paradoxes
        query += " ORDER BY timestamp ASC"

        def _execute() -> list[Event]:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                return [Event.from_json(row[0]) for row in cursor.fetchall()]
                
        return await asyncio.to_thread(_execute)

    async def replay(
        self,
        pipeline_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        topic: Optional[str] = None,
        correlation_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Executes a targeted Replay operation.
        If dry_run=True, returns the query results without polluting the active Bus.
        """
        events = await self._query_events(
            pipeline_id=pipeline_id,
            workflow_id=workflow_id,
            topic=topic,
            correlation_id=correlation_id,
            start_time=start_time,
            end_time=end_time
        )
        
        if not events:
            self._logger.info("Replay aborted: No historic events matched the criteria.")
            return {"status": "success", "replayed": 0, "dry_run": dry_run, "events": []}
            
        if dry_run:
            self._logger.info(f"[DRY RUN] Replay would have injected {len(events)} events.")
            return {
                "status": "success",
                "replayed": len(events),
                "dry_run": True,
                "events": [e.event_id for e in events]
            }
            
        # Execution Phase
        self._logger.warning(f"INITIATING REPLAY: Injecting {len(events)} historic events into the Master Bus.")
        replayed_count = 0
        
        for historic_event in events:
            # We must reset the 'retry_count' to 0 so the new Dispatcher doesn't 
            # instantly throw the event into the Dead Letter Queue.
            payload_dict = historic_event.model_dump()
            payload_dict["retry_count"] = 0
            
            fresh_event = Event(**payload_dict)
            
            # Publish to the back of the queue
            await self._bus.publish(fresh_event)
            replayed_count += 1
            
        return {
            "status": "success",
            "replayed": replayed_count,
            "dry_run": False,
            "events": [e.event_id for e in events]
        }
```

---

# 3. Design Decisions

1. **JSON Extraction Queries:** Rather than migrating the SQLite database schema to include 50 new columns just for querying, I utilized the native `json_extract()` function built into SQLite 3.9+. Because Pydantic serialized the `Event` directly to `payload_json`, we can query the inner JSON keys dynamically: `json_extract(payload_json, '$.pipeline_id')`.
2. **Chronological Sorting (`ORDER BY timestamp ASC`):** If an administrator triggers a massive replay of an entire Pipeline's history, we must inject them back into the Event Bus in the exact order they originally occurred. Failure to do so would create causality paradoxes (e.g., trying to Upload a Video before the Scraper finishes).
3. **Dry Run Safety:** Replaying events into a live production system is incredibly dangerous. The `dry_run=True` boolean serves as an essential safety switch, allowing administrators to use the CLI tool to preview exactly how many events they are about to inject, verifying their Time-Range boundaries are correct before committing.
4. **Retry Counter Scrubbing:** When a failed event is pulled from the database, its `retry_count` is likely maxed out at `3`. If we re-injected it verbatim, the Dispatcher would instantly send it back to the Dead Letter Queue. The Replayer explicitly scrubs this integer back to `0` before cloning the Pydantic envelope.
