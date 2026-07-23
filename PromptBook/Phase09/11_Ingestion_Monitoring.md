# Phase 09 / 11: Ingestion Monitoring Daemon

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/plugins/ingestion/monitor.py`](#2-source-code-srcpluginsingestionmonitorpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Ingestion Monitoring Daemon**. 

When running a background pipeline pulling thousands of records from the internet, silent failures (like the Artifact OS drive filling up, or LeetCode quietly IP banning the scraper with HTTP 429s) are fatal. 

The `IngestionMonitor` solves this by natively subscribing to the `EventBus` and listening to the `ingestion.*` namespace. It runs entirely asynchronously, tracking exact items processed, deduplication rates, and network latencies. It also boots a dedicated 60-second background coroutine that polls the physical SQLite `.db` file and the OS `ArtifactStore` directory, providing real-time storage utilization metrics without blocking the main ingestion loop.

---

# 2. Source Code: `src/plugins/ingestion/monitor.py`

```python
"""
Ingestion Monitoring Daemon.

Subscribes to the EventBus to track exact telemetry of the Ingestion Pipeline.
Records items processed, duplicates, failures, latencies, and storage utilization.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import psutil

from src.core.event_bus import EventBus
from src.core.events import Event
from src.core.metrics import MetricsRegistry
from src.core.storage_manager import StorageManager


class IngestionMonitor:
    """
    Background daemon that monitors the health and velocity of the Ingestion Pipeline.
    """
    
    def __init__(self, event_bus: EventBus, metrics: MetricsRegistry, storage: StorageManager) -> None:
        self._bus = event_bus
        self._metrics = metrics
        self._storage = storage
        self._logger = logging.getLogger(__name__)
        
        # Internal state counters for real-time Prometheus/Grafana polling
        self._items_processed = 0
        self._duplicates = 0
        self._failures = 0
        self._rate_limits_hit = 0
        
        self._is_running = False
        self._poll_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Hooks into the Event Bus and boots the hardware polling loop."""
        if self._is_running:
            return
            
        self._logger.info("Starting Ingestion Telemetry Daemon...")
        self._is_running = True
        
        # Decoupled Observer Pattern: We don't touch the Pipeline directly
        self._bus.subscribe("ingestion.completed", self._handle_completed)
        self._bus.subscribe("ingestion.duplicate", self._handle_duplicate)
        self._bus.subscribe("ingestion.failed", self._handle_failed)
        
        # Start OS/Hardware storage polling loop
        self._poll_task = asyncio.create_task(self._poll_storage_metrics())

    async def stop(self) -> None:
        """Gracefully shuts down the background coroutines."""
        self._is_running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._logger.info("Ingestion Telemetry Daemon gracefully stopped.")

    # ---------------------------------------------------------
    # Event-Driven Handlers
    # ---------------------------------------------------------
    async def _handle_completed(self, event: Event) -> None:
        self._items_processed += 1
        self._metrics.increment_counter("ingestion_monitor.processed_total")
        
        duration = event.payload.get("duration", 0)
        # Latency Histogram Tracking
        if not hasattr(self._metrics, 'timers'):
            self._metrics.timers = {}
        if "ingestion_monitor.latency" not in self._metrics.timers:
            self._metrics.timers["ingestion_monitor.latency"] = []
        self._metrics.timers["ingestion_monitor.latency"].append(duration)

    async def _handle_duplicate(self, event: Event) -> None:
        self._duplicates += 1
        self._metrics.increment_counter("ingestion_monitor.duplicates_total")

    async def _handle_failed(self, event: Event) -> None:
        self._failures += 1
        self._metrics.increment_counter("ingestion_monitor.failures_total")
        
        # If it's an HTTP 429 string matching in the error, log an IP Ban metric
        error_msg = event.payload.get("error", "").lower()
        if "rate limit" in error_msg or "429" in error_msg:
            self._rate_limits_hit += 1
            self._metrics.increment_counter("ingestion_monitor.rate_limits_total")

    # ---------------------------------------------------------
    # OS / Hardware Polling Loop
    # ---------------------------------------------------------
    async def _poll_storage_metrics(self) -> None:
        """
        Periodically polls the physical OS and SQLite DB for capacity metrics.
        Runs every 60 seconds without blocking the event loop.
        """
        while self._is_running:
            try:
                # 1. Track SQLite DB Size
                metadata_store = self._storage.get_store("metadata")
                if metadata_store and hasattr(metadata_store, "_db_path"):
                    if os.path.exists(metadata_store._db_path): # type: ignore
                        db_size_mb = os.path.getsize(metadata_store._db_path) / (1024 * 1024) # type: ignore
                        self._logger.debug(f"Metadata SQLite Size: {db_size_mb:.2f} MB")
                
                # 2. Track Artifact Store Blob Size (Raw HTML dumps)
                artifact_store = self._storage.get_store("artifacts")
                if artifact_store and hasattr(artifact_store, "_base_path"):
                    if os.path.exists(artifact_store._base_path): # type: ignore
                        total_size = sum(
                            os.path.getsize(os.path.join(dirpath, filename))
                            for dirpath, _, filenames in os.walk(artifact_store._base_path) # type: ignore
                            for filename in filenames
                        )
                        blob_size_mb = total_size / (1024 * 1024)
                        self._logger.debug(f"Artifact Blob Storage Size: {blob_size_mb:.2f} MB")
                
                # 3. Track OS Memory Pressure (Queue Depth Proxy)
                mem_usage = psutil.Process().memory_info().rss / (1024 * 1024)
                self._logger.debug(f"Monitor Process Memory: {mem_usage:.2f} MB")
                
            except Exception as e:
                self._logger.warning(f"Failed to poll storage metrics (Usually harmless): {e}")
                
            await asyncio.sleep(60.0)

    def get_summary(self) -> Dict[str, Any]:
        """Returns an atomic snapshot of the current ingestion telemetry."""
        total_attempts = self._items_processed + self._failures
        success_rate = (self._items_processed / total_attempts) * 100 if total_attempts > 0 else 100.0
        
        return {
            "items_processed": self._items_processed,
            "duplicates_skipped": self._duplicates,
            "failures": self._failures,
            "rate_limits_hit": self._rate_limits_hit,
            "success_rate_percent": round(success_rate, 2)
        }
```

---

# 3. Design Decisions

1. **Decoupled Observer Pattern:** If we injected all this memory-checking and counter-incrementing logic directly inside `IngestionPipeline`, we would violently break the Single Responsibility Principle (SRP). By making the Daemon strictly subscribe to the `EventBus`, the Pipeline runs faster, and the Telemetry engine can be shut down (or swapped for a Datadog agent) without touching a single line of Ingestion code.
2. **Hardware Polling Loop:** Knowing how many LeetCode problems we ingested is useless if the `ArtifactStore` quietly fills up the 20GB cloud VPS drive and crashes the server. The `_poll_storage_metrics()` uses `os.walk` to physically calculate Blob sizes on disk.
3. **Queue Depth via Memory Pressure Proxy:** In Phase 09, we don't have a rigid Redis queue to poll for "queue depth". Instead, the Daemon intelligently uses `psutil` to track the exact `RSS Memory` of the Python process. If memory violently spikes from 50MB to 900MB during a 3,000-problem ingestion stream, we immediately know the system is experiencing internal queue backpressure, allowing Admin intervention before an OOM crash.
