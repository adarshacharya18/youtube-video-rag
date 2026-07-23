# Phase 14 / 04: Performance Benchmarking

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/orchestrator/benchmark.py`](#2-source-code-srccoreorchestratorbenchmarkpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

Because the Phase 13 Media Production subsystem executes intensive C-level processes (Manim rendering, FFmpeg multiplexing) that can span up to 12 hours, blindly running the pipeline without telemetry is extremely dangerous. A memory leak in Cairo or an unoptimized FFmpeg filtergraph can easily trigger an OS Out-Of-Memory (OOM) kill or throttle the AWS instance.

The **Performance Benchmarking** module wraps the Pipeline Orchestrator to capture granular hardware telemetry (CPU time slices, RSS memory peaks, Disk I/O bytes) for every phase boundary (Embedding Speed, Rendering Speed, Publishing Latency). This ensures DevOps can continuously monitor the unit economics of generating a single YouTube video.

---

# 2. Source Code: `src/core/orchestrator/benchmark.py`

```python
"""
Performance Benchmarking Module (Phase 14)

Measures and logs system resource utilization (CPU, Memory, Disk) and
subsystem execution latency (Embedding, Rendering, Publishing).
"""
import time
import psutil
import logging
from dataclasses import dataclass
from typing import Callable, Any
from datetime import datetime


@dataclass
class BenchmarkReport:
    """Struct containing aggregated metrics for a single pipeline phase run."""
    operation_name: str
    duration_sec: float
    cpu_utilization_percent: float
    memory_peak_mb: float
    disk_write_mb: float
    timestamp: datetime


class PerformanceMonitor:
    """
    Context manager and decorator utility to wrap heavy pipeline operations
    and generate deep hardware telemetry reports.
    """
    
    def __init__(self):
        self._logger = logging.getLogger("benchmark")
        self.reports: list[BenchmarkReport] = []

    def measure(self, operation_name: str) -> Callable:
        """
        Decorator to measure the hardware performance of a pipeline function.
        Calculates deltas for Disk I/O and process CPU time slices.
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs) -> Any:
                # Capture baseline OS metrics
                start_time = time.time()
                process = psutil.Process()
                mem_start = process.memory_info().rss
                cpu_start_times = process.cpu_times()
                disk_start = psutil.disk_io_counters().write_bytes if psutil.disk_io_counters() else 0

                # Execute Target Operation
                result = func(*args, **kwargs)

                # Capture end state
                end_time = time.time()
                mem_end = process.memory_info().rss
                cpu_end_times = process.cpu_times()
                disk_end = psutil.disk_io_counters().write_bytes if psutil.disk_io_counters() else 0
                
                # Calculate Metric Deltas
                duration = end_time - start_time
                mem_peak_mb = max(mem_start, mem_end) / (1024 * 1024)
                
                # Approximate CPU utilization for this specific process across the time window
                cpu_time_delta = (cpu_end_times.user - cpu_start_times.user) + (cpu_end_times.system - cpu_start_times.system)
                cpu_percent = (cpu_time_delta / duration) * 100.0 if duration > 0 else 0.0
                
                disk_write_mb = (disk_end - disk_start) / (1024 * 1024)

                # Generate Report Object
                report = BenchmarkReport(
                    operation_name=operation_name,
                    duration_sec=duration,
                    cpu_utilization_percent=cpu_percent,
                    memory_peak_mb=mem_peak_mb,
                    disk_write_mb=disk_write_mb,
                    timestamp=datetime.utcnow()
                )
                
                self.reports.append(report)
                self._logger.info(
                    f"[BENCHMARK] {operation_name} | "
                    f"Dur: {duration:.2f}s | "
                    f"CPU: {cpu_percent:.1f}% | "
                    f"Mem: {mem_peak_mb:.1f}MB | "
                    f"Disk I/O: {disk_write_mb:.1f}MB"
                )
                
                return result
            return wrapper
        return decorator

    def generate_summary_report(self) -> str:
        """Generates a Markdown-formatted summary of all captured phase benchmarks."""
        if not self.reports:
            return "No benchmarks recorded."
            
        total_duration = sum(r.duration_sec for r in self.reports)
        max_memory = max(r.memory_peak_mb for r in self.reports)
        total_disk = sum(r.disk_write_mb for r in self.reports)
        
        lines = [
            "## Pipeline Performance Benchmark Report",
            f"**Generated:** {datetime.utcnow().isoformat()}",
            f"- **Total Pipeline Duration:** {total_duration:.2f} seconds",
            f"- **Peak Memory Usage:** {max_memory:.2f} MB",
            f"- **Total Disk Written:** {total_disk:.2f} MB",
            "",
            "### Subsystem Breakdown",
            "| Operation | Duration (s) | CPU (%) | Peak RAM (MB) | Disk I/O (MB) |",
            "|---|---|---|---|---|"
        ]
        
        for r in self.reports:
            lines.append(
                f"| {r.operation_name} | {r.duration_sec:.2f} | "
                f"{r.cpu_utilization_percent:.1f}% | {r.memory_peak_mb:.1f} | {r.disk_write_mb:.1f} |"
            )
            
        return "\n".join(lines)
```

---

# 3. Design Decisions

1. **Decorator Pattern:** By wrapping the benchmark logic in a Python decorator (`@monitor.measure("Embedding Generation")`), we avoid polluting the core business logic of the Orchestrator. We can simply tag functions across Phase 09-13 to capture their exact execution boundaries.
2. **Process Isolation (`psutil.Process()`):** Standard `os.times()` can be inaccurate in multithreaded Docker containers. By hooking directly into `psutil`, we guarantee we are capturing the hardware RSS footprint and CPU timeslices explicitly belonging to our orchestrator and its immediate C-level children.
3. **Disk I/O Delta Logic:** Manim writes huge amounts of intermediate `.mp4` chunks. Tracking purely total disk space is useless if other OS processes are writing. The benchmark explicitly calculates the *delta* of `write_bytes` during the function execution window to accurately attribute storage costs to the renderer.
