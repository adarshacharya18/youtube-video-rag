# Phase06/02_Event.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/events.py`](#2-source-code-srccoreeventspy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document specifies the **Core Event Model**. It serves as the universal, immutable data envelope used to transmit messages across the Event Bus. 

Instead of passing raw dictionaries or custom dataclasses directly, all subsystems (Plugins, Workflow Engine, Telemetry) wrap their data in this standard `Event` envelope. This guarantees that the Event Bus always has access to the `trace_id`, `priority`, and `retry_count` needed to perform routing and Dead Letter Queue (DLQ) operations without having to inspect the underlying payload.

---

# 2. Source Code: `src/core/events.py`

```python
"""
Core Event Model.

Defines the universal immutable Event envelope used by the central Event Bus.
Provides strict type validation, tracing headers, and JSON serialization.
"""

import uuid
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    """Returns a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _uuid() -> str:
    """Generates a standard UUIDv4 string."""
    return str(uuid.uuid4())


class EventPriority(IntEnum):
    """
    Strict integer priorities for the Event Bus queues.
    Lower number = Higher execution priority in asyncio.PriorityQueue.
    """
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class Event(BaseModel):
    """
    The immutable envelope carrying all messages across the Event Bus.
    Uses Pydantic for zero-cost validation and serialization.
    """
    
    # Mathematically lock the object from mutations after instantiation
    model_config = ConfigDict(frozen=True)

    # ==========================================
    # Identifiers & Routing
    # ==========================================
    event_id: str = Field(default_factory=_uuid, description="Unique ID for this exact message.")
    topic: str = Field(..., description="The routing topic (e.g., 'plugin.core.scraper.started')")
    
    # ==========================================
    # Tracing & Telemetry (OpenTelemetry Standard)
    # ==========================================
    trace_id: str = Field(
        default_factory=_uuid, 
        description="Distributed trace ID spanning an entire workflow across multiple events."
    )
    correlation_id: Optional[str] = Field(
        default=None, 
        description="Links this event directly to a previous parent event."
    )
    
    # ==========================================
    # Contextual Origins
    # ==========================================
    pipeline_id: Optional[str] = None
    workflow_id: Optional[str] = None
    plugin_id: Optional[str] = None
    
    # ==========================================
    # Delivery Mechanics
    # ==========================================
    timestamp: datetime = Field(default_factory=_now)
    priority: EventPriority = Field(default=EventPriority.NORMAL)
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    retry_count: int = Field(default=0, ge=0, description="How many times the Bus has attempted delivery.")
    
    # ==========================================
    # Content
    # ==========================================
    payload: dict[str, Any] = Field(
        default_factory=dict, 
        description="The actual business data (e.g., video URL, error stack trace)."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, 
        description="Extraneous headers (e.g., server IP, memory usage)."
    )

    def with_retry(self) -> "Event":
        """
        Creates a new immutable copy of this event with the retry_count incremented.
        Because the model is frozen, the Event Bus calls this to generate a new instance
        before pushing it back into the queue for a retry attempt.
        """
        data = self.model_dump()
        data["retry_count"] += 1
        return Event(**data)

    def to_json(self) -> str:
        """Serializes the event for SQLite persistence or network transmission."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "Event":
        """Deserializes a strict JSON string back into the frozen Pydantic model."""
        return cls.model_validate_json(json_str)

```

---

# 3. Design Decisions

1. **Pydantic Immutability (`frozen=True`)**: By explicitly freezing the Pydantic configuration, I mathematically guarantee that a maliciously coded plugin cannot intercept an event from the bus, alter the `payload`, and let it pass to the next subscriber. If the Event Bus needs to retry a message, it must use the `.with_retry()` method which safely clones the object.
2. **Standardized Tracing (Trace ID / Correlation ID)**: When generating YouTube videos, a single "Make Video" task might trigger 50 distinct events across 6 plugins. By utilizing a global `trace_id` mapped across all 50 events, our logging middleware can instantly group the entire workflow in standard OpenTelemetry formats (like Jaeger or Splunk). The `correlation_id` allows us to build Parent-Child tree diagrams of exactly *why* an event fired.
3. **Integer Priority Alignment**: The `EventPriority` enum explicitly uses `CRITICAL = 0` and `LOW = 3`. This aligns perfectly with `asyncio.PriorityQueue`, which extracts integers in ascending order (0 comes out before 3).
4. **JSON Serialization**: The payload must traverse memory boundaries and occasionally be written to SQLite (when pending). Embedding `.to_json()` natively leverages Pydantic's hyper-fast Rust-based serialization core, ensuring minimal performance impact on the Event Bus.
