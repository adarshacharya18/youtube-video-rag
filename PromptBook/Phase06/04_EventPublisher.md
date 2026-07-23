# Phase06/04_EventPublisher.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/publisher.py`](#2-source-code-srccorepublisherpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document specifies the **Event Publisher Facade**. 

While the underlying `EventBus` manages the raw `asyncio.PriorityQueue`, individual developers and Plugins rarely interact with it directly. Instead, they interact with the `EventPublisher`. 

The Publisher acts as a robust Middleware. It is responsible for wrapping raw dictionary payloads into the strict `Event` Pydantic envelope, automatically generating OpenTelemetry `trace_id`s, and managing **Exponential Backoff Retries** in the event that the master Event Bus experiences severe congestion.

---

# 2. Source Code: `src/core/publisher.py`

```python
"""
Event Publisher Facade.

Provides a high-level, resilient API for constructing and transmitting Events.
Handles automatic Trace ID propagation, payload validation, and exponential 
backoff retries if the Event Bus is heavily congested.
"""

import asyncio
import logging
import uuid
from typing import Any, Optional

from pydantic import ValidationError

from src.core.event_bus import EventBus
from src.core.events import Event, EventPriority
from src.core.exceptions import PipelineError
from src.core.metrics import MetricsRegistry


class PublisherError(PipelineError):
    """Raised when an event fails validation or exhausts retry attempts."""
    pass


class EventPublisher:
    """
    A localized facade injected into Plugins and Subsystems.
    Enforces trace propagation and implements resilient publishing strategies.
    """

    def __init__(self, event_bus: EventBus, metrics: MetricsRegistry, source_id: str = "core") -> None:
        self._bus = event_bus
        self._metrics = metrics
        
        # Identity of the component publishing the events (e.g., core.scraper)
        self._source = source_id
        self._logger = logging.getLogger(f"publisher.{self._source}")

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        timeout_sec: float = 5.0,
        max_retries: int = 3
    ) -> Event:
        """
        Constructs a mathematically proven Event envelope and attempts to transmit it.
        If the master Event Bus queue is full, this triggers an Exponential Backoff Retry.
        """
        
        # 1. Validation & Telemetry Construction
        try:
            event = Event(
                topic=topic,
                payload=payload,
                priority=priority,
                correlation_id=correlation_id,
                # Force Trace ID propagation. Generate a new one if this is the root event.
                trace_id=trace_id or str(uuid.uuid4()),
                pipeline_id=pipeline_id,
                workflow_id=workflow_id,
                plugin_id=self._source if self._source != "core" else None
            )
        except ValidationError as e:
            self._metrics.increment(f"publisher.validation_failed.{topic}")
            raise PublisherError(f"Malformed event payload for topic '{topic}': {e}") from e

        # 2. Resilient Transmission (Exponential Backoff for Congestion)
        attempt = 0
        backoff = 0.5
        
        while attempt <= max_retries:
            try:
                # We wrap the underlying Queue PUT in an asyncio timeout.
                # If the Bus is full (maxsize=5000) and hasn't drained enough space 
                # within timeout_sec, this forces a TimeoutError instead of hanging forever.
                await asyncio.wait_for(self._bus.publish(event), timeout=timeout_sec)
                
                self._logger.debug(f"Successfully published '{topic}' [Trace: {event.trace_id}]")
                return event
                
            except asyncio.TimeoutError:
                attempt += 1
                self._logger.warning(
                    f"Bus congestion timeout publishing '{topic}'. "
                    f"Retry {attempt}/{max_retries} in {backoff}s."
                )
                self._metrics.increment(f"publisher.retries.{topic}")
                
                if attempt > max_retries:
                    self._metrics.increment(f"publisher.dropped.{topic}")
                    self._logger.error(f"FATAL: Dropped event '{topic}' due to extreme Bus congestion.")
                    raise PublisherError(
                        f"Failed to publish '{topic}' after {max_retries} retries."
                    )
                    
                await asyncio.sleep(backoff)
                backoff *= 2  # Exponential scaling
                
            except Exception as e:
                self._logger.error(f"Unexpected error publishing '{topic}': {e}", exc_info=True)
                raise PublisherError(f"Unexpected publish error: {e}") from e
                
        raise PublisherError("Publish loop exited abnormally.")

    def publish_sync(self, topic: str, payload: dict[str, Any]) -> None:
        """
        Thread-safe synchronous bridging.
        Fire-and-forget logic for background threads that cannot await backoff loops.
        """
        try:
            event = Event(
                topic=topic,
                payload=payload,
                plugin_id=self._source if self._source != "core" else None
            )
            self._bus.publish_sync(event)
        except ValidationError as e:
            self._metrics.increment(f"publisher.validation_failed_sync.{topic}")
            self._logger.error(f"Sync validation failed for '{topic}': {e}")
```

---

# 3. Design Decisions

1. **Contextual Injections:** The `EventPublisher` is instantiated with a `source_id` (e.g., `core.scraper.leetcode`). When the Scraper calls `publisher.publish(topic="scraped")`, it doesn't have to constantly pass its own ID; the Publisher automatically tags the `.plugin_id` field in the Event envelope.
2. **OpenTelemetry Compliance:** If a plugin calls `publish()` without passing a `trace_id`, the Publisher automatically generates a UUIDv4. This establishes this event as the "Root" of a new workflow trace. Any downstream services responding to this event must extract that `trace_id` and pass it to their own Publisher, building a seamless parent-child chain.
3. **Queue Congestion Timeout (Backpressure Safety):** The `await self._bus.publish(event)` command eventually calls `asyncio.PriorityQueue.put()`. If the bus is full, `put()` blocks indefinitely. By wrapping it in `asyncio.wait_for(timeout=5.0)`, we effectively say: *"If the bus is so backed up that we can't submit a message for 5 seconds, back off and try again later."*
4. **Exponential Backoff:** If the timeout is hit, the Publisher waits 0.5s, then 1s, then 2s before dropping the message. This acts as a shock absorber. If the Workflow Engine experiences a sudden CPU spike and stops draining the Event Bus queue temporarily, the Publishers will automatically slow down and buffer their requests, completely preventing the pipeline from crashing.
