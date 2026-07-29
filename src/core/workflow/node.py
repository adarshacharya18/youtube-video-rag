"""
Abstract Node Base Class for Phase 08 Workflow Engine.

Defines the contract for pipeline execution nodes and enforces strict
StateLedger-based state passing via run_id.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.core.exceptions import PipelineStageError
from src.core.logger import get_logger
from src.core.orchestrator.state_ledger import PipelineRunRecord, StateLedger

logger = get_logger(__name__)


class Node(ABC):
    """
    Abstract Base Class for all workflow nodes in the execution pipeline.

    Nodes execute modular processing steps (e.g., Ingest, Plan, Script, Render).
    They communicate strictly via the SQLite StateLedger using run_id to ensure
    idempotency, crash recovery, and component isolation. Passing in-memory state
    objects between node instances is prohibited.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique name identifier for the workflow node step.

        Used as step_name in StateLedger tracking and for prior step output lookups.

        Returns:
            str: Unique step identifier (e.g., 'ingest', 'plan', 'script', 'render').
        """
        pass

    @abstractmethod
    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        """
        Execute node processing logic for the specified run_id.

        Args:
            run_id: Unique pipeline run identifier.
            ledger: Thread-safe StateLedger instance for reading inputs and metadata.

        Returns:
            dict[str, Any]: Output dictionary payload to record in StateLedger.

        Raises:
            PipelineError: If step processing fails.
            PipelineStageError: If required prior step outputs or run records are missing.
        """
        pass

    def get_run_record(self, run_id: str, ledger: StateLedger) -> PipelineRunRecord:
        """
        Retrieve PipelineRunRecord for the run_id, raising PipelineStageError if not found.

        Args:
            run_id: Pipeline run identifier.
            ledger: Active StateLedger instance.

        Returns:
            PipelineRunRecord: The run record matching run_id.

        Raises:
            PipelineStageError: If the run_id is not found in StateLedger.
        """
        record = ledger.get_run(run_id)
        if record is None:
            logger.error("Pipeline run record not found", run_id=run_id, node=self.name)
            raise PipelineStageError(
                f"Pipeline run '{run_id}' not found in StateLedger for node '{self.name}'."
            )
        return record

    def get_completed_step_outputs(
        self, run_id: str, ledger: StateLedger
    ) -> dict[str, dict[str, Any]]:
        """
        Retrieve output payloads of all completed steps for the given run_id.

        Args:
            run_id: Pipeline run identifier.
            ledger: Active StateLedger instance.

        Returns:
            dict[str, dict[str, Any]]: Mapping of step_name to step output payload dict.
        """
        completed_steps = ledger.get_completed_steps(run_id)
        return {
            step_name: record.output_payload or {}
            for step_name, record in completed_steps.items()
        }

    def get_step_output(
        self, run_id: str, ledger: StateLedger, step_name: str
    ) -> dict[str, Any]:
        """
        Retrieve output payload dictionary of a specific previously completed step.

        Args:
            run_id: Pipeline run identifier.
            ledger: Active StateLedger instance.
            step_name: Name of prior completed step.

        Returns:
            dict[str, Any]: Output payload dictionary for the specified step.

        Raises:
            PipelineStageError: If step is missing or incomplete in StateLedger.
        """
        completed_steps = ledger.get_completed_steps(run_id)
        if step_name not in completed_steps:
            logger.error(
                "Missing required step completion",
                run_id=run_id,
                node=self.name,
                required_step=step_name,
            )
            raise PipelineStageError(
                f"Node '{self.name}' requires output from prior step '{step_name}', "
                f"but step '{step_name}' is not recorded as completed for run '{run_id}'."
            )

        step_record = completed_steps[step_name]
        return step_record.output_payload or {}
