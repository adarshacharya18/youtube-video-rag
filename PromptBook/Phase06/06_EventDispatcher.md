# Phase06/06_EventDispatcher.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/dispatcher.py`](#2-source-code-srccoredispatcherpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Event Dispatcher**. 

In earlier steps, we embedded a simple `_dispatch_loop` directly inside the `EventBus`. However, following the Single Responsibility Principle, we have extracted the heavy routing logic into a standalone `EventDispatcher` class.

The Dispatcher is responsible for pulling from the `PriorityQueue`, deciding between **Parallel vs. Sequential** delivery, executing local **Exponential Backoff Retries** for isolated subscribers that fail, and seamlessly routing irreversibly poisoned messages to the **Dead Letter Queue (DLQ)**.

---

# 2. Source Code: `src/core/dispatcher.py`

```python
"""
Event Dispatcher Engine.

Pulls events from the core priority queue and executes routing.
Handles parallel vs sequential delivery modes, isolated subscriber retry loops, 
and Dead Letter Queue (DLQ) integration for poisoned messages.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from src.core.events import Event
from src.core.exceptions import PipelineError
from src.core.metrics import MetricsRegistry

SubscriberCallback = Callable[[Event], Awaitable[None]]


class DispatcherError(PipelineError):
    """Raised on critical internal routing failures."""
    pass


class EventDispatcher:
    """
    Dedicated routing engine. 
    Continuously polls the EventBus queue and manages complex delivery mechanics.
    """

    def __init__(
        self,
        queue: asyncio.PriorityQueue[tuple[int, float, Event]],
        routing_table: dict[str, list[SubscriberCallback]],
        metrics: MetricsRegistry,
        dlq: Optional[Any] = None,  # Will type hint to DeadLetterQueue when built
        max_retries: int = 3
    ) -> None:
        self._queue = queue
        self._routes = routing_table
        self._metrics = metrics
        self._dlq = dlq
        self._max_retries = max_retries
        self._logger = logging.getLogger(__name__)
        
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Boots the dispatcher polling loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self._logger.info("Event Dispatcher started.")

    async def stop(self) -> None:
        """Safely halts the polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._logger.info("Event Dispatcher stopped.")

    async def _run_loop(self) -> None:
        """The core polling loop running asynchronously in the background."""
        while self._running:
            try:
                # 1. Block until the highest priority message is available
                priority, ts, event = await self._queue.get()
                
                # 2. Execute complex routing
                await self._dispatch(event)
                
                # 3. Mark the queue slot as resolved
                self._queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Critical dispatcher crash: {e}", exc_info=True)

    async def _dispatch(self, event: Event) -> None:
        """
        Determines the execution strategy (Parallel vs Sequential) and routes
        the event to all registered listeners.
        """
        callbacks = self._get_callbacks(event.topic)
        if not callbacks:
            self._metrics.increment(f"dispatcher.unrouted.{event.topic}")
            return
            
        # Inspect metadata for strict ordering requirements
        is_sequential = event.metadata.get("delivery_mode") == "sequential"
        
        if is_sequential:
            # Sequential Delivery: Guaranteed ordered execution.
            # E.g., Database write must complete BEFORE Logger triggers
            for cb in callbacks:
                await self._safe_execute(cb, event)
        else:
            # Parallel Delivery (Default): Fire all listeners concurrently
            tasks = [asyncio.create_task(self._safe_execute(cb, event)) for cb in callbacks]
            await asyncio.gather(*tasks)

    def _get_callbacks(self, topic: str) -> list[SubscriberCallback]:
        """Resolves exact matches and trailing wildcard ('*') matches."""
        matched = []
        for sub_topic, callbacks in self._routes.items():
            if sub_topic == topic:
                matched.extend(callbacks)
            elif sub_topic.endswith(".*") and topic.startswith(sub_topic[:-2]):
                matched.extend(callbacks)
        return matched

    async def _safe_execute(self, callback: SubscriberCallback, event: Event) -> None:
        """
        Executes a subscriber callback with localized retry logic.
        If it fails the maximum number of times, routes the payload to the DLQ.
        """
        attempt = 0
        backoff = 1.0
        
        while attempt <= self._max_retries:
            try:
                with self._metrics.measure_time(f"dispatcher.execute.{event.topic}"):
                    await callback(event)
                return  # Success
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                attempt += 1
                self._logger.warning(
                    f"Subscriber crashed processing '{event.topic}'. "
                    f"Attempt {attempt}/{self._max_retries}. Error: {e}"
                )
                self._metrics.increment("dispatcher.subscriber_error")
                
                if attempt > self._max_retries:
                    self._logger.error(f"Event {event.event_id} failed max retries. Routing to DLQ.")
                    if self._dlq:
                        # Attempt to push to the Dead Letter Queue, but do not crash the Dispatcher
                        # if the DLQ itself fails.
                        try:
                            # We pass the underlying exception string for admin inspection later
                            await self._dlq.push(event, error_message=str(e))
                            self._metrics.increment("dispatcher.dlq_routed")
                        except Exception as dlq_err:
                            self._logger.critical(f"DLQ Failure: Could not persist dead letter: {dlq_err}")
                    return
                
                # Exponential backoff before re-attempting this specific subscriber
                await asyncio.sleep(backoff)
                backoff *= 2
```

---

# 3. Design Decisions

1. **Isolated Retry Loops:** If 5 subscribers are listening to `plugin.started`, and Subscriber #3 crashes, we *cannot* simply push the Event back onto the main `PriorityQueue`. Doing so would cause Subscribers 1, 2, 4, and 5 to process the event twice, violating idempotency. By putting the `while attempt <= max_retries:` loop inside `_safe_execute`, we ensure only the failed subscriber experiences the retry sequence.
2. **Delivery Mode Metadata:** By default, the `EventDispatcher` wraps all matching callbacks in `asyncio.gather()` for blazing-fast parallel execution. However, some pipelines demand **Ordering Guarantees** (e.g., you must create the folder *before* you render the video into it). If a Publisher sets `event.metadata["delivery_mode"] = "sequential"`, the Dispatcher drops out of `gather()` and `awaits` the callbacks sequentially in a `for` loop.
3. **Dead Letter Queue (DLQ) Fallback:** If a subscriber throws an exception 3 times in a row, the Dispatcher officially gives up on it. However, it does not throw the data away. It passes the `Event` payload and the raw string of the Exception to the `_dlq.push()` method. This allows human operators to manually inspect the broken message and run it again later after fixing the bug.
