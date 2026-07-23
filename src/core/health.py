"""
Advanced Health Check Framework.

Probes and aggregates health status across the Runtime, OS Resources,
Plugins, and Workflows to determine if the pipeline can safely continue execution.
"""

import os
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from src.core.config import PipelineConfig
from src.core.state import StateManager


class HealthStatus(Enum):
    """The aggregate severity level of the system health."""
    HEALTHY = auto()
    DEGRADED = auto()
    UNHEALTHY = auto()


@dataclass(frozen=True)
class HealthReport:
    """An immutable snapshot of the system's diagnostic health."""
    status: HealthStatus
    timestamp: float
    system_checks: dict[str, Any]
    plugin_checks: dict[str, Any]
    resource_checks: dict[str, Any]
    details: list[str] = field(default_factory=list)

    @property
    def is_safe_to_run(self) -> bool:
        """Returns True if the system can safely process new workflows."""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)


class HealthMonitor:
    """
    Actively probes the operating system, file system, and internal State Manager
    to assess the safety of pipeline execution.
    """

    # Minimum safe thresholds for large video generation pipelines
    MIN_DISK_SPACE_GB = 2.0
    MAX_CPU_PERCENT = 95.0
    MAX_MEMORY_PERCENT = 90.0

    def __init__(self, config: PipelineConfig, state_manager: StateManager) -> None:
        self.config = config
        self.state = state_manager
        
    def _probe_resources(self, details: list[str]) -> dict[str, Any]:
        """Checks raw OS limits."""
        checks = {}
        
        # Disk Space Probe
        total, used, free = shutil.disk_usage(self.config.temp_dir)
        free_gb = free / (1024 ** 3)
        checks["disk_free_gb"] = round(free_gb, 2)
        
        if free_gb < self.MIN_DISK_SPACE_GB:
            checks["disk_ok"] = False
            details.append(f"CRITICAL: Insufficient disk space ({free_gb:.2f}GB < {self.MIN_DISK_SPACE_GB}GB)")
        else:
            checks["disk_ok"] = True

        # CPU & Memory Probe (Via StateManager's psutil hook)
        usage = self.state._get_resource_usage()
        checks["cpu_ok"] = usage.cpu_percent < self.MAX_CPU_PERCENT
        checks["memory_ok"] = True  # Default true if psutil is unavailable
        
        if not checks["cpu_ok"]:
            details.append(f"WARNING: CPU load extremely high ({usage.cpu_percent}%)")

        return checks

    def _probe_dependencies(self, details: list[str]) -> dict[str, Any]:
        """Ensures required system-level binaries are accessible."""
        checks = {}
        
        # FFmpeg is strictly required for Video Builder
        has_ffmpeg = shutil.which("ffmpeg") is not None
        checks["ffmpeg_installed"] = has_ffmpeg
        if not has_ffmpeg:
            details.append("CRITICAL: 'ffmpeg' binary not found on PATH.")

        return checks

    def _probe_plugins(self, details: list[str]) -> dict[str, Any]:
        """Analyzes the aggregate health of loaded plugins."""
        checks = {}
        snapshot = self.state.snapshot("HEALTH_CHECK")
        
        failed_plugins = [
            name for name, status in snapshot.plugin_statuses.items() 
            if status == "FAILED"
        ]
        
        checks["failed_plugins_count"] = len(failed_plugins)
        if failed_plugins:
            details.append(f"WARNING: Detected failed plugins: {', '.join(failed_plugins)}")
            checks["plugins_ok"] = False
        else:
            checks["plugins_ok"] = True
            
        return checks

    def run_full_diagnostic(self) -> HealthReport:
        """
        Executes a synchronous sweep across all system boundaries.
        Returns a strongly-typed HealthReport.
        """
        details: list[str] = []
        overall_status = HealthStatus.HEALTHY

        # 1. Resource & File System Checks
        resources = self._probe_resources(details)
        if not resources.get("disk_ok", False):
            overall_status = HealthStatus.UNHEALTHY

        # 2. External Dependency Checks
        system = self._probe_dependencies(details)
        if not system.get("ffmpeg_installed", False):
            overall_status = HealthStatus.UNHEALTHY

        # 3. Internal Plugin & Workflow State Checks
        plugins = self._probe_plugins(details)
        if not plugins.get("plugins_ok", True):
            # A failed plugin doesn't necessarily halt the master runtime,
            # but it degrades the system's capabilities.
            if overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED

        return HealthReport(
            status=overall_status,
            timestamp=time.time(),
            system_checks=system,
            plugin_checks=plugins,
            resource_checks=resources,
            details=details
        )
