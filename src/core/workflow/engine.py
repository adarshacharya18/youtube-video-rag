"""
Workflow Engine for Phase 08 Synchronous Batch Pipeline Execution.

Coordinates sequential execution of pipeline Nodes, enforcing strict state-ledger-only
communication, step idempotency, and crash-safe fault tolerance.
"""

from dataclasses import dataclass, field
import time
import traceback
from typing import Any, Optional, Sequence

from src.core.base import BasePipelineResult
from src.core.events import EventBus, NodeCompleted, NodeFailed, NodeStarted
from src.core.exceptions import PipelineError, PipelineStageError
from src.core.logger import get_logger
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow.node import Node

logger = get_logger(__name__)


@dataclass
class EngineResult:
    """
    Execution outcome container produced by WorkflowEngine.

    Attributes:
        success: True if all nodes completed or were skipped; False if a node failed.
        run_id: Unique pipeline run identifier in StateLedger.
        completed_steps: List of node names completed during or prior to this run.
        failed_step: Name of the node that failed, or None if successful.
        error: Error message string if execution failed, or None.
        execution_time_ms: Total engine execution time in milliseconds.
        status: Final StepStatus enum value (COMPLETED or FAILED).
        skipped_steps: List of node names skipped due to step idempotency.
        outputs: Dict mapping node name to node output payload dictionary.
    """

    success: bool
    run_id: str
    completed_steps: list[str] = field(default_factory=list)
    failed_step: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    status: StepStatus = StepStatus.COMPLETED
    skipped_steps: list[str] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)

    def to_base_result(self, data: Any = None) -> BasePipelineResult[Any]:
        """
        Convert EngineResult to a standard BasePipelineResult.

        Args:
            data: Optional payload override for BasePipelineResult.data.

        Returns:
            BasePipelineResult[Any]: Adapted result object.
        """
        payload = data or {
            "run_id": self.run_id,
            "completed_steps": self.completed_steps,
            "outputs": self.outputs,
        }
        err_obj = PipelineStageError(self.error) if self.error else None
        return BasePipelineResult(
            success=self.success,
            data=payload,
            error=err_obj,
            error_message=self.error,
            execution_time_ms=self.execution_time_ms,
        )


class WorkflowEngine:
    """
    Synchronous, fault-tolerant execution engine for video pipeline workflows.

    Iterates through a sequence of Node instances, ensuring step idempotency by
    checking completed steps in SQLite StateLedger and capturing all node runtime
    exceptions without allowing process crashes.
    """

    def __init__(
        self,
        nodes: Sequence[Node],
        ledger: Optional[StateLedger] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        """
        Initialize WorkflowEngine.

        Args:
            nodes: Non-empty sequence of Node instances to execute in order.
            ledger: Optional StateLedger instance. Defaults to StateLedger("data/state_ledger.db") if None.
            event_bus: Optional EventBus instance to publish node lifecycle events to.

        Raises:
            ValueError: If nodes sequence is empty.
        """
        if not nodes:
            raise ValueError("WorkflowEngine requires a non-empty sequence of Node instances.")

        self.nodes: list[Node] = list(nodes)
        self.ledger: StateLedger = (
            ledger if ledger is not None else StateLedger("data/state_ledger.db")
        )
        self.event_bus: Optional[EventBus] = event_bus

    def run(self, run_id: str) -> EngineResult:
        """
        Execute the pipeline node sequence for the given run_id.

        Args:
            run_id: Pipeline run identifier in StateLedger.

        Returns:
            EngineResult detailing execution outcome, steps executed/skipped, and output payloads.

        Raises:
            PipelineError: If run_id does not exist in StateLedger.
        """
        start_time = time.perf_counter()

        run_record = self.ledger.get_run(run_id)
        if run_record is None:
            logger.error("Pipeline run not found in StateLedger", run_id=run_id)
            raise PipelineError(f"Pipeline run ID '{run_id}' not found in StateLedger.")

        completed_steps: list[str] = []
        skipped_steps: list[str] = []
        outputs: dict[str, Any] = {}

        # Query completed steps from StateLedger for idempotency check
        completed_steps_map = self.ledger.get_completed_steps(run_id)

        logger.info(
            "Starting workflow engine execution",
            run_id=run_id,
            total_nodes=len(self.nodes),
            already_completed=list(completed_steps_map.keys()),
        )

        for node in self.nodes:
            # Step Idempotency Check: Skip node if already COMPLETED in StateLedger
            if (
                node.name in completed_steps_map
                and completed_steps_map[node.name].status == StepStatus.COMPLETED
            ):
                logger.info(
                    "Skipping node execution (already COMPLETED)",
                    run_id=run_id,
                    step_name=node.name,
                )
                skipped_steps.append(node.name)
                completed_steps.append(node.name)
                outputs[node.name] = completed_steps_map[node.name].output_payload or {}
                continue

            # Record step execution start in StateLedger
            step_id = self.ledger.record_step_start(run_id, node.name)
            if self.event_bus is not None:
                self.event_bus.publish(
                    NodeStarted(run_id=run_id, node_name=node.name, step_id=step_id)
                )

            # Fault-tolerant execution wrapper
            try:
                node_output = node.execute(run_id, self.ledger)
                if node_output is None:
                    node_output = {}

                self.ledger.record_step_completion(step_id, node_output)
                if self.event_bus is not None:
                    self.event_bus.publish(
                        NodeCompleted(
                            run_id=run_id,
                            node_name=node.name,
                            step_id=step_id,
                            output=node_output,
                        )
                    )
                completed_steps.append(node.name)
                outputs[node.name] = node_output

                logger.info(
                    "Node execution completed successfully",
                    run_id=run_id,
                    step_name=node.name,
                    step_id=step_id,
                )
            except Exception as e:
                error_msg = str(e)
                error_details = {
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                }
                logger.error(
                    "Node execution failed with exception",
                    run_id=run_id,
                    step_name=node.name,
                    step_id=step_id,
                    error=error_msg,
                    error_type=type(e).__name__,
                    exc_info=True,
                )

                # Record step failure in StateLedger (updates step execution and parent run status to FAILED)
                self.ledger.record_step_failure(
                    step_id,
                    error_message=error_msg,
                    error_details=error_details,
                )
                if self.event_bus is not None:
                    self.event_bus.publish(
                        NodeFailed(
                            run_id=run_id,
                            node_name=node.name,
                            step_id=step_id,
                            error_message=error_msg,
                            error_details=error_details,
                        )
                    )

                elapsed_ms = (time.perf_counter() - start_time) * 1000.0

                # Stop pipeline execution immediately and return EngineResult with FAILED status
                return EngineResult(
                    success=False,
                    run_id=run_id,
                    completed_steps=completed_steps,
                    failed_step=node.name,
                    error=error_msg,
                    execution_time_ms=elapsed_ms,
                    status=StepStatus.FAILED,
                    skipped_steps=skipped_steps,
                    outputs=outputs,
                )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if hasattr(self.ledger, "record_run_completion"):
            self.ledger.record_run_completion(run_id, StepStatus.COMPLETED)

        logger.info(
            "Workflow engine completed all nodes successfully",
            run_id=run_id,
            completed_count=len(completed_steps),
            skipped_count=len(skipped_steps),
            execution_time_ms=elapsed_ms,
        )

        return EngineResult(
            success=True,
            run_id=run_id,
            completed_steps=completed_steps,
            failed_step=None,
            error=None,
            execution_time_ms=elapsed_ms,
            status=StepStatus.COMPLETED,
            skipped_steps=skipped_steps,
            outputs=outputs,
        )

    def execute(self, run_id: str) -> EngineResult:
        """Alias for run(run_id)."""
        return self.run(run_id)

    def run_pipeline(self, run_id: str) -> EngineResult:
        """Alias for run(run_id) matching PROJECT.md interface contract."""
        return self.run(run_id)
