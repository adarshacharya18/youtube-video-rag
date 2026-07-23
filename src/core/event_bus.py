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
