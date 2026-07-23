"""
Event Scheduler Engine.

Provides an asynchronous timer loop to publish Delayed, Scheduled, 
and Recurring events to the central Event Bus.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.core.event_bus import EventBus
from src.core.events import Event
from src.core.exceptions import PipelineError
from src.core.metrics import MetricsRegistry


class SchedulerError(PipelineError):
    """Raised on critical scheduling failures."""
    pass


class ScheduledTask:
    """Internal tracking object representing a delayed Event."""
    def __init__(
        self,
        task_id: str,
        event: Event,
        execute_at: datetime,
        interval_sec: Optional[float] = None
    ) -> None:
        self.task_id = task_id
        self.event = event
        self.execute_at = execute_at
        self.interval_sec = interval_sec
        self.is_cancelled = False


class EventScheduler:
    """
    Chronological daemon that buffers events in memory and releases them
    to the master Event Bus precisely when their designated UTC time matures.
    """

    def __init__(self, event_bus: EventBus, metrics: MetricsRegistry) -> None:
        self._bus = event_bus
        self._metrics = metrics
        self._logger = logging.getLogger(__name__)
        
        # O(1) dictionary mapping for instant task cancellation
        self._tasks: dict[str, ScheduledTask] = {}
        
        self._running = False
        self._loop_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Boots the chron-polling loop."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._scheduler_loop())
        self._logger.info("Event Scheduler started. Polling at 0.5s intervals.")

    async def stop(self) -> None:
        """Safely halts the chron daemon."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        self._logger.info("Event Scheduler stopped.")

    def schedule(self, event: Event, execute_at: datetime) -> str:
        """
        Schedules a one-off event at a specific, absolute UTC datetime.
        Example: Release video exactly at Friday 10:00 AM UTC.
        """
        task_id = str(uuid.uuid4())
        # Enforce UTC timezone awareness
        if execute_at.tzinfo is None:
            execute_at = execute_at.replace(tzinfo=timezone.utc)
            
        self._tasks[task_id] = ScheduledTask(task_id, event, execute_at)
        self._logger.debug(f"Scheduled [{event.topic}] for {execute_at.isoformat()}")
        self._metrics.increment("scheduler.registered.absolute")
        return task_id

    def schedule_delayed(self, event: Event, delay_sec: float) -> str:
        """
        Schedules a one-off event after a relative delay.
        Example: YouTube API Quota Hit -> Retry in 14,400 seconds.
        """
        execute_at = datetime.now(timezone.utc) + timedelta(seconds=delay_sec)
        self._metrics.increment("scheduler.registered.delayed")
        return self.schedule(event, execute_at)

    def schedule_recurring(self, event: Event, interval_sec: float) -> str:
        """
        Schedules an event to fire repeatedly (like a chron job).
        Example: Ping the YouTube Analytics API every 3600 seconds.
        """
        task_id = str(uuid.uuid4())
        execute_at = datetime.now(timezone.utc) + timedelta(seconds=interval_sec)
        
        self._tasks[task_id] = ScheduledTask(task_id, event, execute_at, interval_sec=interval_sec)
        self._logger.debug(f"Scheduled RECURRING [{event.topic}] every {interval_sec}s")
        self._metrics.increment("scheduler.registered.recurring")
        
        return task_id

    def cancel(self, task_id: str) -> bool:
        """
        Instantly halts a scheduled or recurring task. 
        O(1) operation due to dictionary tracking.
        """
        if task_id in self._tasks:
            self._tasks[task_id].is_cancelled = True
            del self._tasks[task_id]
            self._logger.info(f"Cancelled scheduled task: {task_id}")
            self._metrics.increment("scheduler.cancelled")
            return True
        return False

    async def _scheduler_loop(self) -> None:
        """
        The background daemon. Awakens every 0.5s, sweeps the active tasks,
        and pushes matured events into the master Event Bus.
        """
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                to_execute = []
                
                # 1. Sweep active tasks (O(N) iteration is negligible for < 10,000 tasks)
                for task_id, task in list(self._tasks.items()):
                    if task.is_cancelled:
                        continue
                    if now >= task.execute_at:
                        to_execute.append(task)
                        
                # 2. Execution phase
                for task in to_execute:
                    # Fire into the master event bus
                    await self._bus.publish(task.event)
                    self._metrics.increment(f"scheduler.fired.{task.event.topic}")
                    
                    if task.interval_sec:
                        # If it's a recurring chron job, mathematically recalculate the next tick
                        # relative to 'now' to prevent time-drift buildup.
                        task.execute_at = now + timedelta(seconds=task.interval_sec)
                    else:
                        # If it's a one-off, instantly delete it to free memory
                        if task.task_id in self._tasks:
                            del self._tasks[task.task_id]
                            
                # Sleep briefly to yield the CPU back to the master Event Loop
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Scheduler loop crashed: {e}", exc_info=True)
                await asyncio.sleep(1.0)
