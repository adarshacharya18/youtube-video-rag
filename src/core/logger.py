"""
Centralized structured logging using structlog and stdlib logging.

Provides JSON-formatted logs for files (with log rotation), colored 
console output for local development, context-variable binding for 
pipeline IDs, and a performance timer context manager.
"""

import logging
import logging.handlers
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import structlog

from src.core.config import PipelineConfig


def configure_logging(config: PipelineConfig, pipeline_id: str | None = None) -> None:
    """
    Configure the global structlog and standard library logging handlers.

    Args:
        config: The root PipelineConfig containing log levels and data directories.
        pipeline_id: A unique UUID for the current pipeline run. If provided,
                     it will be bound to every log emitted in this context.
    """
    # 1. Determine log level from configuration
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers to prevent duplicate logs during tests
    root_logger.handlers.clear()

    # 2. Define shared processors (data injected into every log entry)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,     # Bind contextvars (like pipeline_id)
        structlog.stdlib.add_logger_name,            # Bind module name
        structlog.stdlib.add_log_level,              # Bind severity level
        structlog.processors.TimeStamper(fmt="iso"), # ISO 8601 timestamps
        structlog.processors.StackInfoRenderer(),    # Add stack trace if requested
        structlog.processors.format_exc_info,        # Parse exception data
        structlog.processors.UnicodeDecoder(),       # Ensure UTF-8
    ]

    # 3. Configure Console Handler (Human-readable, Colored)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processor=structlog.dev.ConsoleRenderer(colors=True),
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 4. Configure File Handler (JSON, Rotating)
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "pipeline.log",
        maxBytes=50 * 1024 * 1024,  # 50 MB
        backupCount=5,              # Keep 5 historical archives
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    json_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processor=structlog.processors.JSONRenderer(),
    )
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    # 5. Configure structlog to wrap stdlib
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # 6. Bind global context variables
    if pipeline_id:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(pipeline_id=pipeline_id)


def get_logger(module_name: str) -> structlog.BoundLogger:
    """
    Get a bound logger for a specific module.
    
    Args:
        module_name: Normally passed as `__name__` from the calling module.
        
    Returns:
        A structlog.BoundLogger instance.
    """
    return structlog.get_logger(module_name)


@contextmanager
def log_execution_time(logger: structlog.BoundLogger, task_name: str) -> Generator[None, None, None]:
    """
    Context manager to profile and log the execution time of a code block.
    
    Args:
        logger: The bound logger for the calling module.
        task_name: A brief description of the task being timed.
    """
    start_time = time.perf_counter()
    logger.info(f"Started: {task_name}")
    try:
        yield
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        logger.exception(f"Failed: {task_name}", elapsed_sec=round(elapsed, 4))
        raise
    else:
        elapsed = time.perf_counter() - start_time
        logger.info(f"Completed: {task_name}", elapsed_sec=round(elapsed, 4))
