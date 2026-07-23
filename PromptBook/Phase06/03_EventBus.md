# Phase06/03_EventBus.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/event_bus.py`](#2-source-code-srccoreevent_buspy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Core Event Bus Engine**. It acts as the high-performance, mathematically sound message broker bridging all subsystems together.

It natively supports `asyncio.PriorityQueue` to route `CRITICAL` signals (e.g., Shutdown) ahead of `LOW` priority signals. It implements **Backpressure** by bounding the queue limit—if the Pipeline produces messages faster than they can be processed, asynchronous publishers will be gracefully blocked (`await`) until capacity frees up, preventing out-of-memory (OOM) crashes.

Crucially, it supports `publish_sync()`, allowing standard blocking Python threads (e.g., a background FFmpeg subprocess wrapper) to safely inject events into the master asynchronous loop without causing thread contention.

---

# 2. Source Code: `src/core/event_bus.py`

```python
"""
Core Event Bus Engine.

A high-performance, async Pub/Sub dispatcher.
Supports thread-safe publishing, backpressure via bounded queues,
priority routing, and wildcard topic subscriptions.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from src.core.events import Event
from src.core.exceptions import PipelineError
from src.core.metrics import MetricsRegistry

# Type alias for standard subscribers
SubscriberCallback = Callable[[Event], Awaitable[None]]


class EventBusError(PipelineError):
    """Raised on critical dispatcher failures."""
    pass


class EventBus:
    """
    Central Message Broker. 
    Decouples subsystems via asynchronous Publish/Subscribe routing.
    """

    def __init__(self, metrics: MetricsRegistry, max_queue_size: int = 5000) -> None:
        self._metrics = metrics
        self._logger = logging.getLogger(__name__)
        
        # Bounded Priority Queue: Stores tuples of (priority_int, timestamp, Event)
        # Bounding the maxsize implements native Backpressure to prevent OOM errors.
        self._queue: asyncio.PriorityQueue[tuple[int, float, Event]] = asyncio.PriorityQueue(maxsize=max_queue_size)
        
        # Subscription Routing Table: topic_name -> list_of_async_callbacks
        self._subscribers: dict[str, list[SubscriberCallback]] = defaultdict(list)
        
        # Lifecycle Management
        self._running = False
        self._dispatcher_task: asyncio.Task[None] | None = None
        self._loop = asyncio.get_event_loop()

    async def start(self) -> None:
        """Boots the background dispatch daemon."""
        if self._running:
            return
        self._running = True
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())
        self._logger.info("Event Bus Dispatcher initialized and running.")

    async def stop(self) -> None:
        """Safely halts dispatching and cancels the daemon."""
        self._running = False
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
        self._logger.info("Event Bus Dispatcher stopped.")

    def subscribe(self, topic: str, callback: SubscriberCallback) -> None:
        """
        Registers a callback listener. Supports wildcards.
        e.g., subscribe("plugin.*", callback)
        """
        self._subscribers[topic].append(callback)
        self._logger.debug(f"Subscribed callback to topic: '{topic}'")

    def unsubscribe(self, topic: str, callback: SubscriberCallback) -> None:
        """Removes a listener from the routing table."""
        if topic in self._subscribers and callback in self._subscribers[topic]:
            self._subscribers[topic].remove(callback)

    async def publish(self, event: Event) -> None:
        """
        Standard Asynchronous Publisher.
        If the queue hits max_queue_size, this method blocks (awaits), naturally
        creating Backpressure down the pipeline.
        """
        if not self._running:
            self._logger.warning(f"Attempted to publish event to stopped bus: {event.event_id}")
            return
            
        # The tuple is used by PriorityQueue for sorting:
        # 1. priority.value (CRITICAL=0 gets dequeued before NORMAL=2)
        # 2. timestamp.timestamp() (FIFO tie-breaker for identical priorities)
        item = (event.priority.value, event.timestamp.timestamp(), event)
        await self._queue.put(item)
        
        self._metrics.increment(f"event_bus.published.{event.topic}")

    def publish_sync(self, event: Event) -> None:
        """
        Thread-Safe Synchronous Publisher.
        Called by external blocking threads to inject events into the master event loop.
        """
        if not self._running:
            return
            
        def _inject() -> None:
            try:
                item = (event.priority.value, event.timestamp.timestamp(), event)
                # put_nowait throws QueueFull if we hit backpressure, serving as a safety valve.
                self._queue.put_nowait(item)
                self._metrics.increment(f"event_bus.published_sync.{event.topic}")
            except asyncio.QueueFull:
                self._logger.error(f"Event Bus Queue is FULL! Dropping synchronous event: {event.event_id}")
                self._metrics.increment("event_bus.dropped_messages")
                
        # Schedules the injection safely into the main asyncio loop
        self._loop.call_soon_threadsafe(_inject)

    async def _dispatch_loop(self) -> None:
        """The core background daemon running continuously to route messages."""
        while self._running:
            try:
                # 1. Pull the highest priority, oldest message from the queue
                priority, ts, event = await self._queue.get()
                
                # 2. Route it
                await self._broadcast(event)
                
                # 3. Mark the queue slot as resolved
                self._queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Event Bus dispatch loop suffered critical crash: {e}", exc_info=True)

    async def _broadcast(self, event: Event) -> None:
        """Concurrently fires all subscriber callbacks mapped to this topic."""
        callbacks = self._get_callbacks_for_topic(event.topic)
        if not callbacks:
            self._metrics.increment(f"event_bus.unrouted.{event.topic}")
            return
            
        # Fire all matching subscribers concurrently to avoid single-subscriber bottlenecking
        tasks = [asyncio.create_task(self._safe_execute(cb, event)) for cb in callbacks]
        await asyncio.gather(*tasks)
        
    def _get_callbacks_for_topic(self, topic: str) -> list[SubscriberCallback]:
        """Resolves exact matches and trailing wildcard ('*') matches."""
        matched = []
        for sub_topic, callbacks in self._subscribers.items():
            if sub_topic == topic:
                matched.extend(callbacks)
            elif sub_topic.endswith(".*") and topic.startswith(sub_topic[:-2]):
                matched.extend(callbacks)
        return matched

    async def _safe_execute(self, callback: SubscriberCallback, event: Event) -> None:
        """Executes a subscriber payload, swallowing and tracking internal errors."""
        try:
            with self._metrics.measure_time(f"event_bus.processing_time.{event.topic}"):
                await callback(event)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._logger.error(f"Subscriber failed processing event {event.event_id}: {e}", exc_info=True)
            self._metrics.increment("event_bus.subscriber_failures")

    def health(self) -> dict[str, Any]:
        """Returns physical stats for the global Health Monitor checks."""
        return {
            "is_running": self._running,
            "queue_size": self._queue.qsize(),
            "total_subscriptions": sum(len(cbs) for cbs in self._subscribers.values())
        }
```

---

# 3. Design Decisions

1. **Native Backpressure:** The `asyncio.PriorityQueue` is instantiated with `maxsize=5000`. If an aggressive Scraping pipeline fires 10,000 events instantly, the `await self._queue.put()` method will natively pause the executing publisher task once it hits 5,000. This physically throttles the system, preventing massive Out-Of-Memory (OOM) crashes without writing custom rate-limiting algorithms.
2. **Thread-Safe Bridging:** Plugins doing heavy blocking math (e.g., Matrix multiplications in NumPy) will run on separate Python threads via `asyncio.to_thread`. Standard `asyncio` objects are mathematically unsafe to modify from external threads. `publish_sync()` safely utilizes `loop.call_soon_threadsafe()` to teleport the event across the thread boundary, completely eliminating Race Conditions.
3. **Wildcard Routing:** The `_get_callbacks_for_topic` engine supports trailing wildcards. If a UI Dashboard subscribes to `plugin.*`, it will automatically receive `plugin.scraper.started` and `plugin.rag.failed` without having to register 50 independent hardcoded subscriptions.
4. **Concurrent Dispatch:** In `_broadcast()`, if 5 different metrics/logging subscribers are listening to an event, we wrap them in `asyncio.create_task` and fire them concurrently. A slow logger writing to disk will never block the master Workflow Engine from receiving the exact same event milliseconds later.
