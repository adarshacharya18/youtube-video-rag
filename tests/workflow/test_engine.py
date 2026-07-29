"""
Unit tests for WorkflowEngine and Node abstraction in src/core/workflow.
"""

from typing import Any
import pytest

from src.core.exceptions import PipelineError, PipelineStageError
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow import EngineResult, Node, WorkflowEngine


class MockIngestNode(Node):
    @property
    def name(self) -> str:
        return "ingest"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        run = self.get_run_record(run_id, ledger)
        return {
            "slug": run.slug,
            "raw_problem": f"Problem content for {run.slug}",
        }


class MockPlanNode(Node):
    @property
    def name(self) -> str:
        return "plan"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        ingest_output = self.get_step_output(run_id, ledger, "ingest")
        return {
            "plan_title": f"Plan for {ingest_output['slug']}",
            "steps": ["Intro", "Solution"],
        }


class FailingNode(Node):
    @property
    def name(self) -> str:
        return "failing_step"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        raise RuntimeError("Intentional mock node failure")


class MissingPriorStepNode(Node):
    @property
    def name(self) -> str:
        return "dependent_step"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        # Tries to access a non-existent step output
        return self.get_step_output(run_id, ledger, "non_existent_step")


def test_node_abstract_instantiation_raises():
    """Verify that instantiating abstract Node directly or incomplete subclasses raises TypeError."""
    with pytest.raises(TypeError):
        Node()  # type: ignore[abstract]

    class IncompleteNode(Node):
        @property
        def name(self) -> str:
            return "incomplete"

    with pytest.raises(TypeError):
        IncompleteNode()  # type: ignore[abstract]


def test_workflow_engine_empty_nodes_raises():
    """Verify WorkflowEngine raises ValueError when initialized with an empty sequence of nodes."""
    ledger = StateLedger(":memory:")
    with pytest.raises(ValueError, match="requires a non-empty sequence"):
        WorkflowEngine([], ledger)


def test_workflow_engine_invalid_run_id_raises():
    """Verify WorkflowEngine.run raises PipelineError when given an invalid run_id."""
    ledger = StateLedger(":memory:")
    engine = WorkflowEngine([MockIngestNode()], ledger)
    with pytest.raises(PipelineError, match="not found in StateLedger"):
        engine.run("invalid_run_123")


def test_workflow_engine_successful_pipeline_execution():
    """Verify successful execution of a multi-node workflow sequence."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("two-sum")

    engine = WorkflowEngine([MockIngestNode(), MockPlanNode()], ledger)
    result = engine.run(run_id)

    assert result.success is True
    assert result.status == StepStatus.COMPLETED
    assert result.run_id == run_id
    assert result.completed_steps == ["ingest", "plan"]
    assert result.skipped_steps == []
    assert result.failed_step is None
    assert result.error is None
    assert result.execution_time_ms > 0.0

    assert "ingest" in result.outputs
    assert result.outputs["ingest"]["slug"] == "two-sum"
    assert "plan" in result.outputs
    assert result.outputs["plan"]["plan_title"] == "Plan for two-sum"

    # Test to_base_result conversion
    base_res = result.to_base_result()
    assert base_res.success is True
    assert base_res.error is None
    assert base_res.data["run_id"] == run_id


def test_workflow_engine_idempotency_skipping():
    """Verify that completed steps are skipped on subsequent runs."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("binary-search")

    engine = WorkflowEngine([MockIngestNode(), MockPlanNode()], ledger)
    result1 = engine.run(run_id)
    assert result1.success is True
    assert result1.completed_steps == ["ingest", "plan"]
    assert result1.skipped_steps == []

    # Re-running same engine for same run_id
    result2 = engine.run(run_id)
    assert result2.success is True
    assert result2.completed_steps == ["ingest", "plan"]
    assert result2.skipped_steps == ["ingest", "plan"]
    assert result2.outputs["ingest"]["slug"] == "binary-search"


def test_workflow_engine_node_failure_handling():
    """Verify engine handles node exception, updates ledger to FAILED, and short-circuits."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("failing-slug")

    engine = WorkflowEngine([MockIngestNode(), FailingNode(), MockPlanNode()], ledger)
    result = engine.run(run_id)

    assert result.success is False
    assert result.status == StepStatus.FAILED
    assert result.failed_step == "failing_step"
    assert "Intentional mock node failure" in str(result.error)
    assert result.completed_steps == ["ingest"]

    # Check state ledger record for run and step
    run_record = ledger.get_run(run_id)
    assert run_record is not None
    assert run_record.status == StepStatus.FAILED

    # Base result conversion
    base_res = result.to_base_result()
    assert base_res.success is False
    assert base_res.error_message == result.error
    assert isinstance(base_res.error, PipelineStageError)


def test_workflow_engine_missing_prior_step_error():
    """Verify node helper get_step_output raises PipelineStageError when prior step is missing."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("missing-step-slug")

    engine = WorkflowEngine([MissingPriorStepNode()], ledger)
    result = engine.run(run_id)

    assert result.success is False
    assert result.failed_step == "dependent_step"
    assert "requires output from prior step" in str(result.error)


def test_workflow_engine_aliases():
    """Verify execute and run_pipeline method aliases on WorkflowEngine."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("alias-test")
    engine = WorkflowEngine([MockIngestNode()], ledger)

    res1 = engine.execute(run_id)
    assert res1.success is True

    run_id2 = ledger.create_run("alias-test-2")
    res2 = engine.run_pipeline(run_id2)
    assert res2.success is True
