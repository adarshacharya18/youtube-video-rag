"""
Persistence Metrics Reporter.

Background daemon that scans physical storage directories, calculates SQLite file sizes,
computes Cache Hit Rates, and pushes telemetry into the core MetricsRegistry.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Optional

from src.core.metrics import MetricsRegistry


class PersistenceMetricsReporter:
    """
    Active Telemetry Scanner for the OS Storage Layer.
    """

    def __init__(
        self,
        metrics: MetricsRegistry,
        storage_dirs: list[str],
        interval_seconds: int = 60
    ) -> None:
        self._metrics = metrics
        self._storage_dirs = [Path(d).resolve() for d in storage_dirs]
        self._interval = interval_seconds
        self._logger = logging.getLogger(__name__)
        
        self._task: Optional[asyncio.Task[None]] = None
        self._running = False
        
        # Stateful Gauges (Current Point-in-Time values)
        self._gauges: dict[str, float] = {
            "storage.total_bytes": 0.0,
            "cache.hit_rate_percent": 0.0
        }

    def start(self) -> None:
        """Boots the continuous scanning loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._report_loop())
        self._logger.info(f"PersistenceMetricsReporter daemon started. (Interval: {self._interval}s)")

    async def stop(self) -> None:
        """Gracefully halts the scanner."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._logger.info("PersistenceMetricsReporter daemon stopped.")

    async def _report_loop(self) -> None:
        """The core sleep loop. Protects the main Event Loop via strict exception catching."""
        while self._running:
            try:
                await self._collect_storage_usage()
                self._calculate_cache_rates()
                
                # Transaction Counts and Latency are passively tracked 
                # in real-time by the StorageManager's UoW Context Block.
                
            except Exception as e:
                self._logger.error(f"Scanner crashed during persistence metrics collection: {e}")
                
            await asyncio.sleep(self._interval)

    async def _collect_storage_usage(self) -> None:
        """
        Calculates total bytes consumed across all registered Storage Boundaries.
        Prevents OS 'Disk Full' lockups.
        """
        def _get_size() -> float:
            total_size = 0.0
            for directory in self._storage_dirs:
                if not directory.exists():
                    continue
                for root, _, files in os.walk(directory):
                    for name in files:
                        filepath = Path(root) / name
                        try:
                            total_size += filepath.stat().st_size
                        except Exception:
                            # Safely ignore OS Permission locks on temp files
                            pass
            return total_size
            
        total_bytes = await asyncio.to_thread(_get_size)
        self._gauges["storage.total_bytes"] = total_bytes
        
        # Log if we cross a 10GB threshold (Warning system)
        mb = total_bytes / (1024 * 1024)
        if mb > 10000:
            self._logger.warning(f"HIGH STORAGE USAGE: Current consumption is at {mb:.2f} MB!")

    def _calculate_cache_rates(self) -> None:
        """
        Computes rolling Cache Hit Rates from the raw Core Counters.
        Useful for Auto-Scaling the RAM LRU limits if the hit rate drops below 50%.
        """
        counters = self._metrics.get_counters()
        
        # Aggregate all dimensional counters
        mem_hits = sum(v for k, v in counters.items() if "cache." in k and ".memory_hit" in k)
        disk_hits = sum(v for k, v in counters.items() if "cache." in k and ".disk_hit" in k)
        misses = sum(v for k, v in counters.items() if "cache." in k and ".miss" in k)
        
        total_requests = mem_hits + disk_hits + misses
        
        if total_requests > 0:
            hit_rate = ((mem_hits + disk_hits) / total_requests) * 100.0
            self._gauges["cache.hit_rate_percent"] = hit_rate
            
            # Periodically emit to standard out for visual monitoring
            if total_requests % 500 == 0:
                self._logger.info(f"Global Cache Hit Rate: {hit_rate:.1f}% ({total_requests} requests)")

    def get_report(self) -> dict[str, Any]:
        """
        Generates the unified JSON telemetry payload.
        Merged with Core Metrics for Prometheus or Grafana scraping.
        """
        return {
            "gauges": self._gauges,
            "counters": {k: v for k, v in self._metrics.get_counters().items() if "storage." in k or "cache." in k},
            "latency": {k: v for k, v in self._metrics.get_timers().items() if "storage." in k},
            "status": "HEALTHY" if self._running else "STOPPED"
        }
