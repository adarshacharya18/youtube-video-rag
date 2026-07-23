# Phase 07 / 11: Workflow Monitoring Implementation

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/workflow_monitoring.py`](#2-source-code-srccoreworkflow_monitoringpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Workflow Watchdog Daemon**. 

While the `WorkflowMetricsReporter` passively compiles system telemetry into a JSON dashboard, the `WorkflowWatchdog` is an active background daemon. It awakens every 10 seconds, queries the JSON report, and runs advanced heuristics to detect **Scheduler Bottlenecks**, **Plummeting Success Rates**, and **Hardware Resource Exhaustion (OOM Risks)**. 

If it detects anomalies, it triggers autonomous Webhook alerts, keeping system administrators aware of critical failures *before* the entire server crashes.

---

# 2. Source Code: `src/core/workflow_monitoring.py`

```python
"""
Workflow Monitoring Watchdog.

Active background daemon that continuously polls pipeline metrics.
Triggers autonomous alerts when Queue Depths explode, Success Rates plummet,
SQLite Checkpoints bloat, or Hardware Resources breach critical levels.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from src.core.exceptions import PipelineError
from src.core.workflow_metrics import WorkflowMetricsReporter


class WatchdogAlert(PipelineError):
    """Raised natively if an Alert callback fails."""
    pass


class WorkflowWatchdog:
    """
    Autonomous guardian of the Workflow Orchestrator.
    Monitors delta-changes and absolute thresholds to detect degradation in real-time.
    """

    def __init__(
        self, 
        reporter: WorkflowMetricsReporter, 
        alert_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
        check_interval_sec: float = 10.0
    ) -> None:
        self._reporter = reporter
        self._alert_callback = alert_callback
        self._interval = check_interval_sec
        self._logger = logging.getLogger("watchdog.workflow")
        
        # Core Analytical Thresholds
        self.min_success_rate = 95.0              # Warn if < 95% of pipelines succeed
        self.max_queue_time_ms = 60000.0          # 60 seconds max wait in Scheduler queue
        self.max_cpu_percent = 90.0               # Imminent Server Freeze Risk
        self.max_memory_percent = 90.0            # Imminent Out-Of-Memory (OOM) Risk
        self.max_checkpoints = 10000              # Warn to run Retention Pruner
        
        # State tracking for Delta/Derivative Analysis
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._last_failed = 0

    async def start(self) -> None:
        """Ignites the autonomous monitoring loop."""
        if self._running:
            return
        self._running = True
        
        # Reset state machine tracking
        self._last_failed = 0
        
        self._task = asyncio.create_task(self._monitor_loop())
        self._logger.info(f"Workflow Watchdog active. Polling every {self._interval}s.")

    async def stop(self) -> None:
        """Safely halts the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._logger.info("Workflow Watchdog stopped.")

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
                report = await self._reporter.generate_report()
                
                # 2. Run heuristics
                await self._analyze(report)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Watchdog internal crash: {e}", exc_info=True)
                
            await asyncio.sleep(self._interval)

    async def _analyze(self, report: dict[str, Any]) -> None:
        """Evaluates thresholds and calculates state deltas to trigger alerts."""
        
        # 1. Success Rate Analysis (Quality Degradation)
        success_rate = report["health"]["global_success_rate_percent"]
        total_completed = report["persistence"]["completed"]
        # Only alert if we have a statistically significant sample size (>10 runs)
        if success_rate < self.min_success_rate and total_completed > 10:
            await self._trigger_alert(
                "CRITICAL", 
                f"DEGRADATION: Global Success Rate fell to {success_rate}%. "
                f"Minimum acceptable threshold is {self.min_success_rate}%."
            )
            
        # 2. Scheduler Queue Bottlenecks
        queue_time = report["performance"]["global_queue_time_avg_ms"]
        if queue_time > self.max_queue_time_ms:
            await self._trigger_alert(
                "WARNING", 
                f"SCHEDULER BOTTLENECK: Pipelines are averaging {queue_time}ms in the Priority Queue. "
                "Consider increasing max_concurrent if hardware allows."
            )

        # 3. Delta Failure Detection (Executor Health)
        failed = report["persistence"]["failed"]
        if failed > self._last_failed:
            delta = failed - self._last_failed
            await self._trigger_alert(
                "ERROR",
                f"EXECUTION FAILURE: {delta} Pipelines FAILED and wrote terminal Checkpoints in the last {self._interval} seconds."
            )
        self._last_failed = failed

        # 4. Checkpoint Health (Disk Bloat)
        checkpoints = report["persistence"]["total_checkpoints_on_disk"]
        if checkpoints > self.max_checkpoints:
            await self._trigger_alert(
                "WARNING", 
                f"DISK BLOAT: SQLite Checkpoint table contains {checkpoints} rows. Run Retention Pruning immediately."
            )

        # 5. Hardware Resource Usage (OOM Protection)
        resources = report.get("resources", {})
        if "error" not in resources:
            cpu = resources.get("cpu_percent", 0)
            mem = resources.get("memory_percent", 0)
            
            if cpu > self.max_cpu_percent:
                await self._trigger_alert("CRITICAL", f"CPU EXHAUSTION: Usage at {cpu}%. Imminent thread lockup risk.")
            if mem > self.max_memory_percent:
                await self._trigger_alert("CRITICAL", f"MEMORY EXHAUSTION: Usage at {mem}%. Imminent OOM Crash risk.")
```

---

# 3. Design Decisions

1. **Delta/Derivative Analysis:** Metrics like "Total Failed Workflows" are ever-increasing absolute counters. The Watchdog does not trigger an alert if the total is `50`. It only triggers an alert if the total jumps from `50` to `52`. By tracking `self._last_failed` and calculating the exact `delta`, the daemon isolates and reports *current degradation events* rather than spamming historical data to your Slack channel.
2. **Statistically Significant Success Rates:** If the very first pipeline run of the day fails, the Success Rate drops to `0%`. The engine employs a statistical cutoff (`total_completed > 10`) before it evaluates the `min_success_rate`. This prevents false-positive panics during early boot phases.
3. **Pluggable Alerting Callback:** By accepting a standard Python `Callable[[str, str], Awaitable[None]]` in the constructor, the engine achieves absolute structural decoupling. This means an administrator can inject an Async Slack Bot, a Discord Webhook, or an AWS SNS Topic without modifying a single line of the Orchestrator code.
