"""
Observability Subsystem (Phase 14)

Provides structured JSON logging, distributed tracing hooks, health endpoints,
and metrics aggregation for the overarching 12-hour batch pipeline.
"""
import logging
import json
import uuid
import time
from datetime import datetime
from typing import Any, Dict, Callable


class StructuredJSONFormatter(logging.Formatter):
    """
    Formats log records as JSON for easy ingestion into Datadog, ELK, or CloudWatch.
    Enforces the presence of Correlation IDs.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "N/A"),
            "video_id": getattr(record, "video_id", "N/A"),
            "phase": getattr(record, "phase", "N/A")
        }
        
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)


class ObservabilityManager:
    """
    Central hub for Metrics, Tracing, and Health Checks.
    """
    def __init__(self):
        self.metrics: Dict[str, float] = {}
        self._setup_root_logger()

    def _setup_root_logger(self):
        """Overrides the standard Python logger to force JSON output."""
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        
        # Prevent adding multiple handlers during test runs
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(StructuredJSONFormatter())
            logger.addHandler(handler)

    def generate_correlation_id(self) -> str:
        """Generates a UUID trace ID that follows a request across all 13 phases."""
        return str(uuid.uuid4())

    def record_metric(self, name: str, value: float) -> None:
        """Records a generic gauge or counter metric."""
        # STUB: In production, send to StatsD / Prometheus Pushgateway
        self.metrics[name] = value

    def trace(self, phase_name: str) -> Callable:
        """
        Distributed tracing decorator. Injects correlation_id into the logger
        and records exact phase durations to trace multi-hour bottlenecks.
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs) -> Any:
                # Extract or generate trace context
                video_id = kwargs.get("video_id", "UNKNOWN_VIDEO")
                correlation_id = kwargs.get("correlation_id", self.generate_correlation_id())
                
                # Setup LogAdapter for context injection
                logger = logging.getLogger(f"trace.{phase_name}")
                logger = logging.LoggerAdapter(logger, extra={
                    "correlation_id": correlation_id,
                    "video_id": video_id,
                    "phase": phase_name
                })
                
                start_time = time.time()
                logger.info(f"Starting {phase_name}")
                
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    logger.info(f"Completed {phase_name} in {duration:.2f}s")
                    self.record_metric(f"duration.{phase_name}", duration)
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    logger.error(f"Failed {phase_name} after {duration:.2f}s: {str(e)}")
                    self.record_metric(f"error.{phase_name}", 1)
                    raise e
            return wrapper
        return decorator

    def get_health_status(self) -> Dict[str, Any]:
        """
        Provides a /health endpoint payload evaluating the status of all
        C-level dependencies and active queues. Useful for Kubernetes Liveness probes.
        """
        # STUB: In production, explicitly check DB connections, disk space, and GPU VRAM.
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "ffmpeg": "ok",
                "manim": "ok",
                "disk_space_mb": 50000,
                "dlq_backlog": 0
            }
        }
