"""
Unit tests for core structured logging utilities.
"""

import logging
import pytest
from src.core.config import PipelineConfig
from src.core.logger import configure_logging, get_logger, log_execution_time


def test_get_logger() -> None:
    """Test get_logger returns a valid logger instance."""
    logger = get_logger("test_module")
    assert logger is not None


def test_configure_logging() -> None:
    """Test configure_logging sets root logger level based on PipelineConfig."""
    config = PipelineConfig(log_level="DEBUG")
    configure_logging(config, pipeline_id="test-run-123")
    
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG


def test_log_execution_time_success() -> None:
    """Test log_execution_time context manager runs without errors on success."""
    logger = get_logger("test_timer")
    executed = False
    with log_execution_time(logger, "test task"):
        executed = True
    assert executed is True


def test_log_execution_time_failure() -> None:
    """Test log_execution_time context manager logs and re-raises exception on failure."""
    logger = get_logger("test_timer_failure")
    with pytest.raises(ValueError, match="simulated failure"):
        with log_execution_time(logger, "failing task"):
            raise ValueError("simulated failure")
