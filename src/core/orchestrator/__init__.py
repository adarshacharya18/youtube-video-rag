"""
Orchestrator Core Module for Pipeline Runtime and State Ledger.
"""

from src.core.orchestrator.state_ledger import (
    PipelineRunRecord,
    PipelineStatus,
    RunStatus,
    StateLedger,
    Status,
    StepExecutionRecord,
    StepStatus,
)


def __getattr__(name: str):
    """Lazy-load PipelineRunner to break circular import with pipeline.nodes."""
    if name == "PipelineRunner":
        from src.core.orchestrator.pipeline_runner import PipelineRunner
        return PipelineRunner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "PipelineRunner",
    "StateLedger",
    "StepStatus",
    "PipelineStatus",
    "RunStatus",
    "Status",
    "PipelineRunRecord",
    "StepExecutionRecord",
]
