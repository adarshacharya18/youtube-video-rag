"""
Metrics Registry for pipeline telemetry.
"""
from typing import Any, Dict, Optional


class MetricsRegistry:
    """In-memory metrics collector for telemetry and performance monitoring."""

    def __init__(self) -> None:
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list[float]] = {}

    def counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        self._counters[name] = self._counters.get(name, 0.0) + value

    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        self._gauges[name] = value

    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

    def record(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        self.counter(name, value, labels)

    def get(self, name: str) -> Optional[float]:
        if name in self._counters:
            return self._counters[name]
        if name in self._gauges:
            return self._gauges[name]
        return None

    def clear(self) -> None:
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


__all__ = ["MetricsRegistry"]
