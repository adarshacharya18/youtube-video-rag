"""
Event Monitoring Watchdog.

Active background daemon that continuously polls pipeline metrics.
Triggers autonomous alerts when Queue Backpressure, Slow Consumers, 
or Data Drops exceed critical structural thresholds.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from src.core.event_metrics import EventMetricsReporter
from src.core.exceptions import PipelineError


class WatchdogAlert(PipelineError):
    """Raised natively if an Alert callback fails."""
    pass


class EventWatchdog:
    """
    Autonomous guardian of the Event Bus.
    Monitors delta-changes in telemetry to detect degradation in real-time.
    """

    def __init__(
        self, 
        reporter: EventMetricsReporter, 
        alert_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
        check_interval_sec: float = 5.0
    ) -> None:
        self._reporter = reporter
        self._alert_callback = alert_callback
        self._interval = check_interval_sec
        self._logger = logging.getLogger("watchdog.events")
        
        # Core Analytical Thresholds
        self.max_queue_depth = 4000      # Assumes a master EventBus limit of 5000
        self.max_latency_ms = 15000.0    # 15 seconds max execution per subscriber
        
        # State tracking for Delta/Derivative Analysis
        self._running = False
        self._task: asyncio.Task[None] | None = None
        
        self._last_dropped = 0
        self._last_crashes = 0
        self._last_dlq = 0

    async def start(self) -> None:
        """Ignites the autonomous monitoring loop."""
        if self._running:
            return
        self._running = True
        
        # Reset state machine tracking
        self._last_dropped = 0
        self._last_crashes = 0
        self._last_dlq = 0
        
        self._task = asyncio.create_task(self._monitor_loop())
        self._logger.info(f"Event Watchdog active. Polling every {self._interval}s.")

    async def stop(self) -> None:
        """Safely halts the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._logger.info("Event Watchdog stopped.")

    async def _trigger_alert(self, severity: str, message: str) -> None:
        """Emits a structured log and fires the external alerting hook (e.g., Slack/Discord)."""
        self._logger.error(f"[WATCHDOG ALERT: {severity}] {message}")
        if self._alert_callback:
            try:
                await self._alert_callback(severity, message)
            except Exception as e:
                self._logger.critical(f"Failed to execute external alert callback: {e}")

    async def _monitor_loop(self) -> None:
        """The heartbeat daemon logic."""
        while self._running:
            try:
                # 1. Fetch current Pipeline State
                report = self._reporter.generate_report()
                
                # 2. Run heuristics
                await self._analyze(report)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Watchdog internal crash: {e}", exc_info=True)
                
            await asyncio.sleep(self._interval)

    async def _analyze(self, report: dict[str, Any]) -> None:
        """Evaluates thresholds and calculates state deltas to trigger alerts."""
        
        # 1. Backpressure & Resource Analysis
        queue_depth = report["health"]["active_queue_depth"]
        if queue_depth >= self.max_queue_depth:
            await self._trigger_alert(
                "CRITICAL", 
                f"SEVERE BACKPRESSURE: Event Queue is at {queue_depth} capacity. System chokepoint detected."
            )
            
        # 2. Slow Consumer Analysis
        latencies = report["performance_ms"]
        for topic, avg_ms in latencies.items():
            if avg_ms > self.max_latency_ms:
                await self._trigger_alert(
                    "WARNING",
                    f"SLOW CONSUMER: Topic '{topic}' is averaging {avg_ms:.2f}ms per execution."
                )
                
        # 3. Data Loss (Delta)
        dropped = report["throughput"]["dropped_events"]
        if dropped > self._last_dropped:
            delta = dropped - self._last_dropped
            await self._trigger_alert(
                "CRITICAL",
                f"DATA LOSS: {delta} events were permanently dropped due to bus congestion."
            )
        self._last_dropped = dropped

        # 4. Subscriber Instability (Delta)
        crashes = report["reliability"]["subscriber_crashes"]
        if crashes > self._last_crashes:
            delta = crashes - self._last_crashes
            await self._trigger_alert(
                "WARNING", 
                f"INSTABILITY: {delta} subscriber exceptions occurred in the last interval."
            )
        self._last_crashes = crashes
        
        # 5. Dead Letter Queue Poisoning (Delta)
        dlq = report["reliability"]["dlq_routed"]
        if dlq > self._last_dlq:
            delta = dlq - self._last_dlq
            await self._trigger_alert(
                "ERROR", 
                f"POISONED MESSAGES: {delta} events failed all retries and were routed to DLQ."
            )
        self._last_dlq = dlq
