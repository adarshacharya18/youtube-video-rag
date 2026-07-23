# Phase04/09_Runtime_Metrics.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Target Environment:** Intel Core Ultra 7 155H · Ubuntu 25.10 LTS · Python 3.12 · Intel Arc GPU  
**Document Version:** 2.0.0  
**Status:** Canonical — Supersedes v1.0.0 after architectural audit.

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code Specification: `src/core/logger.py`](#2-source-code-specification-srccoreloggerpy)
3. [Structured Log Key Conventions & Metrics Format](#3-structured-log-key-conventions--metrics-format)
4. [Design Decisions & Architecture Compliance](#4-design-decisions--architecture-compliance)
5. [Change Log](#5-change-log)

---

# 1. Executive Summary

This document specifies the **Observability & Metrics Specification** implemented via structured logging in `src/core/logger.py`.

The pipeline avoids custom metric registries, Prometheus push-gateways, background telemetry daemons, or system monitoring packages. Observability is achieved entirely through structured `structlog` log events written to standard streams and log files.

### Core Observability Principles
- **Execution Timing:** Timings are calculated using standard Python `time.perf_counter()` inside stage code and decorators.
- **Structured JSON Formatting:** Output logs emit standard key-value pairs formatted as structured JSON for easy parsing.
- **Context Binding:** Key contextual fields (e.g., `slug`, `module`, `stage`) are bound to loggers at the composition root or within specific modules. No global `RuntimeContext` object is used.
- **Diagnostic Logging:** Retry warnings and failure events include detailed diagnostics without changing application flow.

---

# 2. Source Code Specification: `src/core/logger.py`

```python
"""
Structured Logging and Observability Module.

Configures structlog for structured JSON logging and metrics reporting.
Provides context-bound loggers for transparent execution tracing.
"""

import logging
import sys
from typing import Any
import structlog
from structlog.stdlib import BoundLogger

from src.core.config import PipelineConfig


def configure_logging(config: PipelineConfig) -> None:
    """
    Initializes structlog configuration and log formatting.

    Args:
        config: Root pipeline configuration instance.
    """
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


def get_logger(name: str, **initial_values: Any) -> BoundLogger:
    """
    Returns a structlog context-bound logger.

    Args:
        name: Logger name (typically __name__).
        **initial_values: Context key-value pairs to bind.

    Returns:
        BoundLogger: Configured structured logger.
    """
    return structlog.get_logger(name).bind(**initial_values)
```

---

# 3. Structured Log Key Conventions & Metrics Format

### 3.1 Stage Execution Timing Metrics
Stage execution durations are logged using standard JSON keys when a stage finishes. This occurs directly in the orchestrator or module methods, explicitly passing the `slug`:

```python
import time

start_time = time.perf_counter()
# Execute pipeline stage (e.g., Voice Synthesis)
elapsed_sec = round(time.perf_counter() - start_time, 3)

self.logger.info(
    "stage_completed",
    stage="voice",
    duration_sec=elapsed_sec,
    slug=slug,
)
```

**JSON Log Output:**
```json
{
  "event": "stage_completed",
  "stage": "voice",
  "duration_sec": 12.458,
  "slug": "two-sum",
  "level": "info",
  "logger": "src.orchestrator.pipeline",
  "timestamp": "2026-07-23T12:00:00.123456Z"
}
```

### 3.2 Transient Retry Warnings (`@retry`)
When retrying transient operations, the retry decorator emits structured warnings. The `logger` is bound locally or injected:

```python
logger.warning(
    "stage_retry",
    stage="scraper",
    attempt=attempt_num,
    delay_sec=delay,
    exception=str(exc)
)
```

**JSON Log Output:**
```json
{
  "event": "stage_retry",
  "stage": "scraper",
  "attempt": 2,
  "delay_sec": 4.0,
  "exception": "HTTP 503 Service Unavailable",
  "level": "warning",
  "logger": "src.core.retry",
  "timestamp": "2026-07-23T12:00:04.654321Z"
}
```

### 3.3 Overall Pipeline Metrics
Upon pipeline completion, a final metric summary is logged by the orchestrator:

```python
self.logger.info(
    "pipeline_completed",
    slug=slug,
    total_duration_sec=round(total_elapsed, 3),
    output_path=str(final_video_path),
    status="SUCCESS",
)
```

---

# 4. Design Decisions & Architecture Compliance

1. **Zero External Daemon Dependencies:** Metrics ingestion relies on standard JSON log streams parsed by log collectors (e.g., Vector, Fluent Bit, Loki), eliminating metric agent overhead. This strictly avoids `Prometheus` and `Grafana` dependencies per canonical rules.
2. **No MetricsRegistry:** The architecture deliberately rejects `MetricsRegistry` or `HealthMonitor` singletons. All telemetry is localized to standard `structlog` calls.
3. **High Precision:** Timing measurements use `time.perf_counter()` to provide sub-millisecond precision.
4. **No RuntimeContext:** Removed the use of a unified `PipelineContext` object. Loggers receive explicit variables like `slug` directly as method parameters or via constructor injection (`logger = get_logger("module", slug="two-sum")`).
5. **Clean Code Layout:** All logging setup resides strictly in `src/core/logger.py`, maintaining the canonical 7-file constraint for `src/core/`.

---

# 5. Change Log

- **Removed `RuntimeContext` Dependency:** `context.pipeline_run_id` and `context.slug` were removed from logs. Data is now explicitly passed down. This aligns with the rule: "No `RuntimeContext`. Modules receive `config` and `logger` via constructor injection."
- **Removed `MetricsRegistry`:** Explicitly documented the removal of custom metrics classes, gauges, counters, and telemetry daemon hooks.
- **Removed External Monitoring Tools:** Removed any references to `psutil`, Prometheus, or Grafana integration, confirming pure dependency on structured JSON logging.
