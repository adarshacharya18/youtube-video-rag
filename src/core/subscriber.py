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
