"""
Unit tests for core exception hierarchy.
"""

import pytest
from src.core.exceptions import (
    ConfigurationError,
    FatalError,
    NetworkError,
    PipelineError,
    PipelineStageError,
    PipelineValidationError,
    RetryableError,
    ValidationError,
)


def test_exception_hierarchy() -> None:
    """Test inheritance relationship for custom pipeline exceptions."""
    assert issubclass(RetryableError, PipelineError)
    assert issubclass(FatalError, PipelineError)
    assert issubclass(ConfigurationError, FatalError)
    assert issubclass(PipelineValidationError, ValidationError)
    assert issubclass(ValidationError, FatalError)
    assert issubclass(PipelineStageError, FatalError)
    assert issubclass(NetworkError, RetryableError)


def test_raising_exceptions() -> None:
    """Test instantiating and raising core exceptions."""
    with pytest.raises(PipelineError) as exc_info:
        raise PipelineStageError("Stage 1 failed")
    assert "Stage 1 failed" in str(exc_info.value)
