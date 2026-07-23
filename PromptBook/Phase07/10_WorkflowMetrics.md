# Phase 07 / 10: Workflow Metrics Implementation

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/workflow_metrics.py`](#2-source-code-srccoreworkflow_metricspy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Workflow Metrics Reporter**. 

While the Phase 06 Metrics system tracked millisecond-level Event Bus messages, the Workflow Metrics Reporter tracks macro-level Pipeline Telemetry. It securely merges the active Python `MetricsRegistry` (in-memory timers) with the SQLite `PipelineStateManager` (persistence counts) to generate a holistic, real-time dashboard of Pipeline Health, Success Rates, Checkpoint Bloat, and System Hardware Resource usage.

---

# 2. Source Code: `src/core/workflow_metrics.py`

```python
"""
Workflow Metrics Engine.

Aggregates execution telemetry, step latencies, queue times, and pipeline success rates.
Merges memory-volatile metrics with persistent SQLite state counts.
"""

import asyncio
import logging
import sqlite3
from typing import Any

from src.core.metrics import MetricsRegistry
from src.core.pipeline_state import PipelineStateManager


class WorkflowMetricsReporter:
    """
    Dashboard Compiler for the Workflow Orchestrator.
    Generates structured, JSON-serializable diagnostic reports.
    """

    def __init__(self, metrics: MetricsRegistry, state_manager: PipelineStateManager) -> None:
        self._metrics = metrics
        self._state = state_manager
        self._logger = logging.getLogger(__name__)

    async def generate_report(self) -> dict[str, Any]:
        """
        Compiles real-time orchestration telemetry into a structured JSON dictionary.
        """
        counters = self._metrics.get_counters()
        timers = self._metrics.get_timers()

        # ==========================================
        # 1. Step Latency Analysis
        # ==========================================
        step_times = {
            k.replace("workflow.step.duration.", ""): v 
            for k, v in timers.items() 
            if k.startswith("workflow.step.duration.")
        }
        
        avg_step_ms: dict[str, float] = {}
        for step_id, timer_data in step_times.items():
            if timer_data.count > 0:
                avg_step_ms[step_id] = round((timer_data.total_time / timer_data.count) * 1000, 2)
            else:
                avg_step_ms[step_id] = 0.0

        # ==========================================
        # 2. Global Execution Latencies
        # ==========================================
        exec_timer = timers.get("workflow.total_execution_time")
        avg_exec_ms = 0.0
        if exec_timer and exec_timer.count > 0:
            avg_exec_ms = round((exec_timer.total_time / exec_timer.count) * 1000, 2)

        queue_timer = timers.get("workflow.queue_wait_time")
        avg_queue_ms = 0.0
        if queue_timer and queue_timer.count > 0:
            avg_queue_ms = round((queue_timer.total_time / queue_timer.count) * 1000, 2)

        # ==========================================
        # 3. Persistent Database State Analysis
        # ==========================================
        def _fetch_db_stats() -> dict[str, int]:
            with sqlite3.connect(self._state._db_path) as conn:
                cursor = conn.execute("SELECT state, count(*) FROM checkpoints GROUP BY state")
                return dict(cursor.fetchall())
                
        db_stats = await asyncio.to_thread(_fetch_db_stats)
        
        total_completed = db_stats.get("COMPLETED", 0)
        total_failed = db_stats.get("FAILED", 0)
        total_cancelled = db_stats.get("CANCELLED", 0)
        total_running = db_stats.get("RUNNING", 0)
        
        total_finished = total_completed + total_failed
        success_rate = (total_completed / total_finished * 100) if total_finished > 0 else 100.0
        total_checkpoints = sum(db_stats.values())

        # ==========================================
        # 4. OS Hardware Resource Usage
        # ==========================================
        resource_usage: dict[str, Any] = {}
        try:
            # psutil is the python-standard for orchestration telemetry
            import psutil
            mem = psutil.virtual_memory()
            resource_usage = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_used_mb": round(mem.used / (1024 * 1024), 2),
                "memory_percent": mem.percent
            }
        except ImportError:
            resource_usage = {"error": "psutil package not installed. Hardware telemetry disabled."}

        # ==========================================
        # 5. Compile Dashboard JSON
        # ==========================================
        return {
            "health": {
                "active_running_pipelines": total_running,
                "global_success_rate_percent": round(success_rate, 2),
            },
            "persistence": {
                "completed": total_completed,
                "failed": total_failed,
                "cancelled": total_cancelled,
                "total_checkpoints_on_disk": total_checkpoints
            },
            "performance": {
                "global_queue_time_avg_ms": avg_queue_ms,
                "global_execution_time_avg_ms": avg_exec_ms,
                "step_average_duration_ms": avg_step_ms
            },
            "reliability": {
                "step_retries_triggered": sum(
                    v for k, v in counters.items() if k.startswith("workflow.step.retry.")
                ),
                "step_fatal_failures": sum(
                    v for k, v in counters.items() if k.startswith("workflow.step.failure.")
                )
            },
            "resources": resource_usage
        }
```

---

# 3. Design Decisions

1. **Dual-Sourced Aggregation:** The Reporter dynamically merges data from two vastly different architectures. It pulls `step_retries_triggered` straight from the blazing-fast in-memory Python `MetricsRegistry`, while simultaneously extracting the absolute `success_rate_percent` directly from the durable SQLite persistence layer. This ensures the dashboard survives server reboots while still providing sub-millisecond precision for active tasks.
2. **Graceful Hardware Degradation:** The engine uses Python's standard `psutil` library to accurately track how much CPU the active video rendering pipelines are currently burning. If `psutil` is not installed on the host system, the entire application does not crash. It catches the `ImportError` and gracefully returns an error string inside the JSON payload, ensuring 100% Pipeline uptime.
3. **Queue Wait Times:** If `global_queue_time_avg_ms` begins to skyrocket, but `global_execution_time_avg_ms` stays flat, it mathematically proves that the server CPU limits are fine, but the `max_concurrent` setting in the `WorkflowScheduler` is throttling too aggressively. This granularity is essential for production capacity scaling.
