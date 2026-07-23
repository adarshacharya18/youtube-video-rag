# Phase06/05_EventSubscriber.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/subscriber.py`](#2-source-code-srccoresubscriberpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Event Subscriber Facade**. 

Just as the `EventPublisher` protects the core `EventBus` from publishing errors, the `EventSubscriber` acts as a shield for consuming events. It allows Plugins to register standard Python functions (both `async` and `sync`) without worrying about thread-safety. 

The Facade automatically enforces strict execution timeouts (preventing a hanging DB write from freezing the Event Loop), evaluates custom `filter_func` lambdas, and tracks deep execution metrics.

---

# 2. Source Code: `src/core/subscriber.py`

```python
"""
Event Subscriber Facade.

Provides a high-level API for registering event handlers with the Event Bus.
Wraps user-defined callbacks in strict timeouts, handles sync-to-async bridging,
and supports dynamic payload filtering.
"""

import asyncio
import inspect
import logging
from typing import Any, Callable, Optional

from src.core.event_bus import EventBus
from src.core.events import Event
from src.core.exceptions import PipelineError
from src.core.metrics import MetricsRegistry


class SubscriberError(PipelineError):
    """Raised when an event handler crashes or exceeds its execution timeout."""
    pass


class EventSubscriber:
    """
    A localized facade injected into Plugins and Subsystems.
    Wraps raw callbacks in safety bounds (Timeouts, Threading, Metrics) before 
    registering them with the master Event Bus.
    """

    def __init__(self, event_bus: EventBus, metrics: MetricsRegistry, subscriber_id: str) -> None:
        self._bus = event_bus
        self._metrics = metrics
        self._id = subscriber_id
        self._logger = logging.getLogger(f"subscriber.{self._id}")
        
        # Track active registrations so we can cleanly unsubscribe later (e.g., Hot-Reloading)
        self._active_subscriptions: list[tuple[str, Callable[[Event], Any]]] = []

    def subscribe(
        self,
        topic: str,
        handler: Callable[[Event], Any],
        timeout_sec: float = 10.0,
        filter_func: Optional[Callable[[Event], bool]] = None
    ) -> None:
        """
        Registers a handler to a topic.
        Automatically bridges synchronous handlers to run in `asyncio.to_thread`.
        Enforces execution timeouts and conditional filtering.
        """
        # Determine if the developer provided an 'async def' or a standard 'def'
        is_async = inspect.iscoroutinefunction(handler)
        
        async def _wrapper(event: Event) -> None:
            # 1. Dynamic Payload Filtering
            if filter_func:
                try:
                    if not filter_func(event):
                        self._logger.debug(f"Event {event.event_id} dropped by filter.")
                        return
                except Exception as e:
                    self._logger.error(f"Filter function crashed: {e}")
                    return

            # 2. Execution with Strict Timeouts
            self._logger.debug(f"Handling '{event.topic}' [Trace: {event.trace_id}]")
            try:
                with self._metrics.measure_time(f"subscriber.{self._id}.handle_time"):
                    if is_async:
                        # Natively await async handlers
                        await asyncio.wait_for(handler(event), timeout=timeout_sec)
                    else:
                        # Safely bridge synchronous heavy workloads (e.g., blocking DB writes or I/O)
                        # by pushing them to a background thread pool.
                        await asyncio.wait_for(
                            asyncio.to_thread(handler, event), 
                            timeout=timeout_sec
                        )
            except asyncio.TimeoutError:
                self._metrics.increment(f"subscriber.{self._id}.timeout")
                self._logger.error(f"Handler timed out after {timeout_sec}s for event {event.event_id}")
                # We raise so the Master EventBus Dispatcher can catch it for Dead Letter routing
                raise SubscriberError(f"Execution timeout ({timeout_sec}s)")
            except Exception as e:
                self._metrics.increment(f"subscriber.{self._id}.error")
                self._logger.error(f"Handler crashed for event {event.event_id}: {e}", exc_info=True)
                raise SubscriberError(f"Handler crashed: {e}") from e

        # Register the strongly-typed wrapper with the core bus
        self._bus.subscribe(topic, _wrapper)
        self._active_subscriptions.append((topic, _wrapper))
        self._logger.info(f"Registered handler for topic '{topic}' (Async: {is_async})")

    def unsubscribe_all(self) -> None:
        """
        Removes all listeners associated with this subscriber.
        Crucial for Graceful Shutdowns and Plugin Hot-Reloading.
        """
        for topic, wrapper in self._active_subscriptions:
            self._bus.unsubscribe(topic, wrapper)
        self._active_subscriptions.clear()
        self._logger.info("Unsubscribed from all topics.")
```

---

# 3. Design Decisions

1. **Intelligent Async Bridging:** A third-party Plugin developer might write a synchronous handler (`def handle_event(e): time.sleep(5)`). If we blindly awaited this in the master Event Loop, it would freeze the entire pipeline. The Subscriber uses `inspect.iscoroutinefunction()` to detect sync methods and automatically wraps them in `asyncio.to_thread()`, preserving the pipeline's concurrency with zero required effort from the developer.
2. **Strict Timeouts (No Zombies):** Every handler execution is wrapped in `asyncio.wait_for(..., timeout=timeout_sec)`. This guarantees that a deadlocked subscriber cannot hold memory indefinitely. If the handler exceeds its limit (default 10s), it is instantly killed and a `SubscriberError` is thrown back to the bus.
3. **Pre-Execution Filtering:** If a subscriber only cares about `VideoRendered` events where `resolution == 1080p`, they can pass a `filter_func`. The wrapper evaluates this *before* attempting to schedule the task, saving CPU cycles and context-switching overhead.
4. **Hot-Reload Support (`unsubscribe_all`):** Because we track every wrapper we inject into the `EventBus`, when a Plugin needs to be upgraded or hot-reloaded, it can simply call `unsubscribe_all()`. This cleanly severs all ties to the Event Bus without leaving zombie callbacks in memory.
