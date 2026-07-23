"""
Global Runtime State Management.

Provides centralized, thread-safe tracking of the entire system's health,
queue depths, active workflows, and error metrics.
"""

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None  # Fallback gracefully if psutil is not installed


@dataclass(frozen=True)
class ResourceUsage:
    """Immutable snapshot of OS-level resource consumption."""
    cpu_percent: float
    memory_mb: float
    active_threads: int


@dataclass(frozen=True)
class RuntimeStateSnapshot:
    """
    A strictly immutable, point-in-time snapshot of the entire application.
    Suitable for serialization and transmission to monitoring APIs or CLI dashboards.
    """
    runtime_status: str
    active_pipelines: list[str]
    plugin_statuses: dict[str, str]
    workflow_statuses: dict[str, str]
    queue_lengths: dict[str, int]
    error_count: int
    warning_count: int
    resources: ResourceUsage
    uptime_seconds: float


class StateManager:
    """
    Thread-safe telemetry registry.
    Acts as a sink for all subsystems to report their operational status.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._start_time = time.time()
        
        # System State
        self._active_pipelines: set[str] = set()
        self._plugin_statuses: dict[str, str] = {}
        self._workflow_statuses: dict[str, str] = {}
        self._queue_lengths: dict[str, int] = {}
        
        # Telemetry
        self._error_count = 0
        self._warning_count = 0

    def add_pipeline(self, pipeline_id: str) -> None:
        """Registers a new active pipeline workflow."""
        with self._lock:
            self._active_pipelines.add(pipeline_id)

    def remove_pipeline(self, pipeline_id: str) -> None:
        """Deregisters a completed or failed pipeline."""
        with self._lock:
            self._active_pipelines.discard(pipeline_id)

    def update_plugin_state(self, plugin_name: str, state_name: str) -> None:
        """Records the current lifecycle state of a plugin."""
        with self._lock:
            self._plugin_statuses[plugin_name] = state_name

    def update_workflow_state(self, workflow_name: str, state_name: str) -> None:
        """Records the current execution node/state of a workflow."""
        with self._lock:
            self._workflow_statuses[workflow_name] = state_name

    def set_queue_length(self, queue_name: str, length: int) -> None:
        """Updates the backlog size for a specific Event Bus topic or DLQ."""
        with self._lock:
            self._queue_lengths[queue_name] = length

    def increment_error(self) -> None:
        """Records a caught exception/error."""
        with self._lock:
            self._error_count += 1

    def increment_warning(self) -> None:
        """Records a non-fatal warning."""
        with self._lock:
            self._warning_count += 1

    def _get_resource_usage(self) -> ResourceUsage:
        """Retrieves raw OS metrics (requires psutil for deep accuracy)."""
        cpu = 0.0
        mem = 0.0
        if psutil:
            process = psutil.Process()
            # Non-blocking CPU measurement
            cpu = process.cpu_percent(interval=None)
            mem = process.memory_info().rss / (1024 * 1024)
            
        return ResourceUsage(
            cpu_percent=cpu,
            memory_mb=mem,
            active_threads=threading.active_count()
        )

    def snapshot(self, runtime_status: str) -> RuntimeStateSnapshot:
        """
        Locks the registry momentarily to generate a perfectly cohesive 
        snapshot of all metrics at this exact millisecond.
        """
        with self._lock:
            return RuntimeStateSnapshot(
                runtime_status=runtime_status,
                # Create shallow copies to prevent the snapshot from 
                # changing asynchronously after it is returned.
                active_pipelines=list(self._active_pipelines),
                plugin_statuses=self._plugin_statuses.copy(),
                workflow_statuses=self._workflow_statuses.copy(),
                queue_lengths=self._queue_lengths.copy(),
                error_count=self._error_count,
                warning_count=self._warning_count,
                resources=self._get_resource_usage(),
                uptime_seconds=time.time() - self._start_time
            )
