"""
Unit tests for core structural protocols and BasePipelineResult.
"""

from datetime import datetime, timezone
import pytest
from src.core.base import BasePipelineResult, PipelineModule, Service, Repository


def test_base_pipeline_result_success() -> None:
    """Test successful BasePipelineResult instantiation."""
    result: BasePipelineResult[str] = BasePipelineResult(
        success=True,
        data="processed_output",
        execution_time_ms=12.5,
    )
    assert result.success is True
    assert result.data == "processed_output"
    assert result.error is None
    assert result.error_message is None
    assert result.execution_time_ms == 12.5
    assert isinstance(result.timestamp, datetime)


def test_base_pipeline_result_failure() -> None:
    """Test failure BasePipelineResult instantiation."""
    err = ValueError("Invalid input data")
    result: BasePipelineResult[dict] = BasePipelineResult(
        success=False,
        error=err,
        error_message=str(err),
    )
    assert result.success is False
    assert result.data is None
    assert result.error is err
    assert result.error_message == "Invalid input data"


def test_pipeline_module_protocol_compliance() -> None:
    """Test runtime checkable behavior of PipelineModule protocol."""

    class ConcreteModule:
        def execute(self, payload: str) -> int:
            return len(payload)

    class InvalidModule:
        pass

    assert isinstance(ConcreteModule(), PipelineModule)
    assert not isinstance(InvalidModule(), PipelineModule)
