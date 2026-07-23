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
