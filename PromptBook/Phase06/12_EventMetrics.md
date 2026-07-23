# Phase06/12_EventMetrics.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/event_metrics.py`](#2-source-code-srccoreevent_metricspy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Event Metrics Reporter**. 

Throughout Phase 06, we instrumented the Publisher, Dispatcher, and Subscriber layers with `self._metrics.increment()` and `self._metrics.measure_time()`. The `EventMetricsReporter` acts as a centralized dashboard aggregator. It parses the global `MetricsRegistry`, extracts Event-Bus-specific telemetry, calculates average latencies, and produces a highly structured JSON report. 

This JSON report can be instantly queried via the REST API or CLI (`agy event stats`) to monitor the health, queue depths, and bottleneck rates of the entire Video Rendering pipeline in real-time.

---

# 2. Source Code: `src/core/event_metrics.py`

```python
"""
Event Metrics Engine.

Aggregates all telemetry data emitted by the Publishers, Event Bus, Dispatcher, 
and Subscribers into a unified, queryable dashboard interface.
"""

from typing import Any

from src.core.event_bus import EventBus
from src.core.metrics import MetricsRegistry


class EventMetricsReporter:
    """
    Dashboard Compiler for the Event Bus.
    Extracts unstructured metrics from the Global Registry and formats them
    into strict JSON schema for CLI and API consumers.
    """

    def __init__(self, metrics: MetricsRegistry, event_bus: EventBus) -> None:
        self._metrics = metrics
        self._bus = event_bus

    def generate_report(self) -> dict[str, Any]:
        """
        Compiles the real-time pipeline telemetry into a structured JSON dictionary.
        Tracks throughput, queue backpressure, error rates, and subscriber latencies.
        """
        # Fetch the raw, unformatted global telemetry
        counters = self._metrics.get_counters()
        timers = self._metrics.get_timers()
        
        # Fetch physical stats directly from the Dispatcher Queue
        bus_health = self._bus.health()

        # ==========================================
        # 1. Throughput Calculations
        # ==========================================
        published_async = sum(
            v for k, v in counters.items() if k.startswith("event_bus.published.")
        )
        published_sync = sum(
            v for k, v in counters.items() if k.startswith("event_bus.published_sync.")
        )
        
        # Publisher Facade drops due to Event Bus Backpressure timeouts
        dropped_publisher = sum(
            v for k, v in counters.items() if k.startswith("publisher.dropped.")
        )
        
        # Synchronous bridging drops (Queue Full)
        dropped_sync = counters.get("event_bus.dropped_messages", 0)

        # ==========================================
        # 2. Performance (Latency Averages)
        # ==========================================
        # Extract the processing times for every specific topic
        subscriber_times = {
            k.replace("dispatcher.execute.", ""): v 
            for k, v in timers.items() 
            if k.startswith("dispatcher.execute.")
        }

        avg_latencies: dict[str, float] = {}
        for topic, timer_data in subscriber_times.items():
            if timer_data.count > 0:
                # timer_data.total_time is in seconds. We multiply by 1000 for milliseconds.
                avg_ms = (timer_data.total_time / timer_data.count) * 1000
                avg_latencies[topic] = round(avg_ms, 2)
            else:
                avg_latencies[topic] = 0.0

        # ==========================================
        # 3. Compile Dashboard JSON
        # ==========================================
        return {
            "health": {
                "bus_running": bus_health["is_running"],
                "active_queue_depth": bus_health["queue_size"],
                "total_subscribers": bus_health["total_subscriptions"]
            },
            "throughput": {
                "published_async": published_async,
                "published_sync": published_sync,
                "total_published": published_async + published_sync,
                "unrouted_events": sum(
                    v for k, v in counters.items() if k.startswith("dispatcher.unrouted.")
                ),
                "dropped_events": dropped_publisher + dropped_sync
            },
            "reliability": {
                "backoff_retries": sum(
                    v for k, v in counters.items() if k.startswith("publisher.retries.")
                ),
                "subscriber_crashes": counters.get("dispatcher.subscriber_error", 0) + 
                                      counters.get("event_bus.subscriber_failures", 0),
                "dlq_routed": counters.get("dispatcher.dlq_routed", 0),
                "schema_validation_failures": sum(
                    v for k, v in counters.items() if "validation_failed" in k
                )
            },
            "performance_ms": avg_latencies
        }
```

---

# 3. Design Decisions

1. **O(N) Aggregation over Global State:** Rather than tightly coupling the `EventBus` to a Database just to write performance metrics, the Bus utilizes the global `MetricsRegistry`. The `EventMetricsReporter` executes a simple `startswith()` string search across the registry to extract Event-specific metrics, preserving the pipeline's memory-light footprint.
2. **Backpressure Telemetry (Dropped Events):** The `throughput.dropped_events` metric accurately merges `publisher.dropped` (events that timed out due to backpressure) and `event_bus.dropped_messages` (sync events dropped instantly due to Queue limits). If an administrator sees this number rise above `0`, it is a mathematically guaranteed indicator that the Workflow Engine CPU is failing to drain the queue fast enough to keep up with the Scraper.
3. **Sub-millisecond Averages:** The `Performance` block automatically calculates the average execution time in milliseconds (`avg_ms`) per topic. If the `avg_ms` for `video.rendering.start` spikes from `400ms` to `12,000ms`, the system provides instant observability without needing heavy external tools like Prometheus or DataDog (though those can be attached via Middleware later).
