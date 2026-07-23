"""
Runtime Metrics Registry.

A centralized telemetry sink for quantitative data: counters, gauges, and timers.
Designed for high-throughput, thread-safe asynchronous updates.
"""

import collections
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator


@dataclass(frozen=True)
class MetricsSnapshot:
    """Immutable export of all active metrics."""
    counters: dict[str, int]
    gauges: dict[str, float]
    timers_avg: dict[str, float]
    timers_max: dict[str, float]


class MetricsRegistry:
    """
    Thread-safe numeric telemetry aggregator.
    Mimics a Prometheus-style exporter in-memory.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        
        # Counters increment only (e.g., total_failures)
        self._counters: collections.defaultdict[str, int] = collections.defaultdict(int)
        
        # Gauges can go up and down (e.g., queue_depth, cpu_percent)
        self._gauges: dict[str, float] = {}
        
        # Timers track execution durations
        # To prevent infinite memory growth, we store only a sliding window of floats
        self._timers: collections.defaultdict[str, list[float]] = collections.defaultdict(list)
        self._TIMER_WINDOW_SIZE = 1000

    def increment(self, name: str, value: int = 1) -> None:
        """Increments a monotonic counter (e.g., retries, errors)."""
        with self._lock:
            self._counters[name] += value

    def set_gauge(self, name: str, value: float) -> None:
        """Sets an absolute value representing a current state (e.g., cpu, memory)."""
        with self._lock:
            self._gauges[name] = float(value)

    def record_time(self, name: str, duration: float) -> None:
        """Records a discrete time execution metric."""
        with self._lock:
            window = self._timers[name]
            if len(window) >= self._TIMER_WINDOW_SIZE:
                window.pop(0)  # Evict oldest
            window.append(duration)

    @contextmanager
    def measure_time(self, name: str) -> Generator[None, None, None]:
        """
        Context manager to easily wrap blocks of code.
        Example:
            with metrics.measure_time("plugin_load_time"):
                plugin.initialize()
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record_time(name, time.perf_counter() - start)

    def snapshot(self) -> MetricsSnapshot:
        """
        Locks the registry momentarily to calculate rolling averages 
        and return an immutable snapshot.
        """
        with self._lock:
            timers_avg = {}
            timers_max = {}
            
            for name, times in self._timers.items():
                if times:
                    timers_avg[name] = sum(times) / len(times)
                    timers_max[name] = max(times)
                else:
                    timers_avg[name] = 0.0
                    timers_max[name] = 0.0

            return MetricsSnapshot(
                counters=dict(self._counters),
                gauges=self._gauges.copy(),
                timers_avg=timers_avg,
                timers_max=timers_max
            )
