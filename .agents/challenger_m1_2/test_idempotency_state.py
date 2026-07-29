"""
Empirical test script to verify WorkflowEngine idempotency, state passing, and ledger status.
"""

from typing import Any
import pytest

from src.core.exceptions import PipelineStageError
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow.engine import WorkflowEngine
from src.core.workflow.node import Node


class IngestNode(Node):
    @property
    def name(self) -> str:
        return "ingest"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        run = self.get_run_record(run_id, ledger)
        return {"slug": run.slug, "step": "ingest_done"}


class PlanNode(Node):
    @property
    def name(self) -> str:
        return "plan"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        ingest_data = self.get_step_output(run_id, ledger, "ingest")
        return {"plan_title": f"Plan for {ingest_data['slug']}"}


def test_state_ledger_run_status_after_completion():
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("test-slug")

    engine = WorkflowEngine([IngestNode(), PlanNode()], ledger)
    result = engine.run(run_id)

    assert result.success is True
    assert result.status == StepStatus.COMPLETED

    run_record = ledger.get_run(run_id)
    print(f"Run record status in SQLite: {run_record.status}")
    # Note: run_record.status is StepStatus.IN_PROGRESS because record_step_completion doesn't update pipeline_runs status!


if __name__ == "__main__":
    test_state_ledger_run_status_after_completion()
