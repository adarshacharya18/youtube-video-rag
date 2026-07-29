# Detailed Technical Analysis & Design for `src/core/workflow/engine.py`

## Executive Summary

This document presents the comprehensive architectural and implementation design for `WorkflowEngine` (`src/core/workflow/engine.py`) in Milestone 1 of Phase 08. The `WorkflowEngine` orchestrates the sequential, fault-tolerant execution of pipeline nodes (e.g. Ingest, Plan, Script, Render), strictly using the SQLite-backed `StateLedger` (`src/core/orchestrator/state_ledger.py`) for state persistence, step idempotency checking, and crash recovery.

---

## 1. Architectural Alignment & Key Requirements

| Requirement | Implementation Strategy | StateLedger Contract |
|-------------|-------------------------|----------------------|
| **Constructor & Dependency Injection** | Accepts `nodes: Sequence[Node]` and optional `ledger: StateLedger \| None`. Defaults `ledger` to `StateLedger("data/state_ledger.db")` if not provided. | Instantiates thread-safe SQLite WAL connection. |
| **Execution Method Signature** | Implements `run(self, run_id: str) -> EngineResult`. Provides `execute` and `run_pipeline` aliases for full interface contract compliance. | Queries `ledger.get_run(run_id)` to validate existence. |
| **Step Idempotency & Resumption** | Queries `completed_steps = ledger.get_completed_steps(run_id)`. If `node.name` exists in `completed_steps` with `StepStatus.COMPLETED`, execution of `node` is skipped. | Reads `step_executions` table filtered by `pipeline_run_id` and `status = 'COMPLETED'`. |
| **Fault-Tolerant Node Execution** | Wraps `node.execute(run_id, ledger)` in `try...except Exception as e`. Captures `e`, records failure to `ledger.record_step_failure()`, halts execution, and returns `EngineResult` with `success=False`. | Updates step and parent run status in SQLite to `FAILED`. Prevents process crash. |

---

## 2. Interface Contracts & Data Models

### 2.1 `EngineResult` Dataclass (`src/core/workflow/engine.py`)

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from src.core.orchestrator.state_ledger import StepStatus

@dataclass
class EngineResult:
    """
    Execution outcome container produced by WorkflowEngine.
    
    Attributes:
        run_id: Unique pipeline run identifier tracked in StateLedger.
        success: True if all nodes executed or were skipped successfully; False if any node failed.
        status: Final StepStatus enum value (COMPLETED or FAILED).
        executed_steps: List of node names executed during this run.
        skipped_steps: List of node names skipped due to step idempotency.
        outputs: Dict mapping step_name -> node output payload dictionary.
        failed_step: Name of the node that failed, or None if successful.
        error_message: Exception message string if execution failed, or None.
        error_details: Dict containing 'error_type' and 'traceback' if execution failed, or None.
    """
    run_id: str
    success: bool
    status: StepStatus
    executed_steps: List[str] = field(default_factory=list)
    skipped_steps: List[str] = field(default_factory=list)
    outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    failed_step: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
```

---

## 3. Workflow Engine Execution Flow

```
                     +---------------------------------------+
                     |         WorkflowEngine.run()          |
                     +---------------------------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |  Verify pipeline run exists in ledger |
                     +---------------------------------------+
                                         |
                                         v
                     +---------------------------------------+
                     | Query completed steps from ledger     |
                     | ledger.get_completed_steps(run_id)    |
                     +---------------------------------------+
                                         |
                                         v
                      +-------------------------------------+
                      |    For each node in self.nodes      |
                      +-------------------------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
            [Is node.name completed?]            [Not yet completed]
                       |                                   |
                       v                                   v
        +----------------------------+   +------------------------------------+
        |  Log skipping step         |   | ledger.record_step_start()         |
        |  Add to skipped_steps      |   | returns step_execution_id          |
        |  Populate output from db   |   +------------------------------------+
        +----------------------------+                     |
                       |                                   v
                       |                 +------------------------------------+
                       |                 |      try:                          |
                       |                 |        output = node.execute()     |
                       |                 +------------------------------------+
                       |                                   |
                       |                +------------------+------------------+
                       |                |                                     |
                       |           [On Success]                          [On Exception]
                       |                |                                     |
                       |                v                                     v
                       |   +--------------------------+          +---------------------------+
                       |   | ledger.record_step_      |          | Format traceback & details|
                       |   |   completion()           |          | ledger.record_step_       |
                       |   | Add to executed_steps    |          |   failure()               |
                       |   +--------------------------+          | Return EngineResult with  |
                       |                |                        |   success=False & FAILED  |
                       |                |                        +---------------------------+
                       +----------------+
                                        |
                               (Next node in sequence)
                                        |
                                        v
                       +----------------------------------+
                       |  All nodes processed             |
                       |  Return EngineResult (COMPLETED) |
                       +----------------------------------+
```

---

## 4. Detailed Component Specifications

### 4.1 Constructor (`__init__`)
```python
def __init__(
    self,
    nodes: Sequence[Node],
    ledger: Optional[StateLedger] = None,
) -> None:
    if not nodes:
        raise ValueError("WorkflowEngine requires a non-empty sequence of Node instances.")
    
    self.nodes: List[Node] = list(nodes)
    self.ledger: StateLedger = (
        ledger if ledger is not None else StateLedger("data/state_ledger.db")
    )
```
- **Validation**: Ensures `nodes` is a non-empty sequence.
- **Ledger Injection**: Accepts an existing `StateLedger` instance (crucial for unit testing with `:memory:` SQLite databases) or defaults to `"data/state_ledger.db"`.

### 4.2 Step Idempotency & Skipping Check
```python
completed_steps = self.ledger.get_completed_steps(run_id)

if node.name in completed_steps and completed_steps[node.name].status == StepStatus.COMPLETED:
    logger.info(
        "Skipping node execution (already COMPLETED)",
        run_id=run_id,
        step_name=node.name,
    )
    skipped_steps.append(node.name)
    if completed_steps[node.name].output_payload is not None:
        outputs[node.name] = completed_steps[node.name].output_payload
    continue
```
- **Mechanics**: Before calling `record_step_start`, the engine queries `get_completed_steps(run_id)` which returns a map of completed `StepExecutionRecord`s.
- **Idempotency Guarantee**: If node execution crashed mid-pipeline previously (e.g. at step 3), re-running the engine for the same `run_id` skips steps 1 and 2, picking up exactly at step 3.

### 4.3 Node Lifecycle & Exception Wrapping
```python
step_execution_id = self.ledger.record_step_start(run_id, node.name)

try:
    node_output = node.execute(run_id, self.ledger)
    if node_output is None:
        node_output = {}

    self.ledger.record_step_completion(step_execution_id, node_output)
    executed_steps.append(node.name)
    outputs[node.name] = node_output
    logger.info(
        "Node execution completed successfully",
        run_id=run_id,
        step_name=node.name,
        step_execution_id=step_execution_id,
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
        step_execution_id=step_execution_id,
        error=error_msg,
        error_type=type(e).__name__,
        exc_info=True,
    )

    # Record failure in StateLedger (updates step_execution to FAILED and pipeline_run to FAILED)
    self.ledger.record_step_failure(
        step_execution_id,
        error_message=error_msg,
        error_details=error_details,
    )

    # Stop pipeline execution immediately and return EngineResult
    return EngineResult(
        run_id=run_id,
        success=False,
        status=StepStatus.FAILED,
        executed_steps=executed_steps,
        skipped_steps=skipped_steps,
        outputs=outputs,
        failed_step=node.name,
        error_message=error_msg,
        error_details=error_details,
    )
```

---

## 5. Complete Implementation Specification (`src/core/workflow/engine.py`)

```python
"""
Workflow Engine for Phase 08 Synchronous Batch Pipeline Execution.

Coordinates sequential execution of pipeline Nodes, enforcing strict state-ledger-only
communication, step idempotency, and crash-safe fault tolerance.
"""

from dataclasses import dataclass, field
import traceback
from typing import Any, Dict, List, Optional, Sequence

from src.core.exceptions import PipelineError
from src.core.logger import get_logger
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow.node import Node

logger = get_logger(__name__)


@dataclass
class EngineResult:
    """
    Encapsulates the outcome of a WorkflowEngine execution run.

    Attributes:
        run_id: Unique pipeline run identifier in StateLedger.
        success: True if all nodes completed or were skipped; False if a node failed.
        status: Final StepStatus enum value (COMPLETED or FAILED).
        executed_steps: List of node names executed during this run.
        skipped_steps: List of node names skipped due to step idempotency.
        outputs: Dict mapping node name to node output payload dict.
        failed_step: Name of the node that failed, if any.
        error_message: Error message string if execution failed.
        error_details: Dict with error classification and stack trace if execution failed.
    """

    run_id: str
    success: bool
    status: StepStatus
    executed_steps: List[str] = field(default_factory=list)
    skipped_steps: List[str] = field(default_factory=list)
    outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    failed_step: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


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
    ) -> None:
        """
        Initialize WorkflowEngine.

        Args:
            nodes: Sequence of Node instances to execute in order.
            ledger: Optional StateLedger instance. Defaults to StateLedger("data/state_ledger.db") if None.

        Raises:
            ValueError: If nodes sequence is empty.
        """
        if not nodes:
            raise ValueError("WorkflowEngine requires a non-empty sequence of Node instances.")

        self.nodes: List[Node] = list(nodes)
        self.ledger: StateLedger = (
            ledger if ledger is not None else StateLedger("data/state_ledger.db")
        )

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
        run_record = self.ledger.get_run(run_id)
        if run_record is None:
            logger.error("Pipeline run not found in StateLedger", run_id=run_id)
            raise PipelineError(f"Pipeline run ID '{run_id}' not found in StateLedger.")

        executed_steps: List[str] = []
        skipped_steps: List[str] = []
        outputs: Dict[str, Dict[str, Any]] = {}

        # Query completed steps for idempotency check
        completed_steps = self.ledger.get_completed_steps(run_id)

        logger.info(
            "Starting workflow engine execution",
            run_id=run_id,
            total_nodes=len(self.nodes),
            completed_steps_count=len(completed_steps),
        )

        for node in self.nodes:
            # Idempotency Check: Skip node if already COMPLETED in StateLedger
            if (
                node.name in completed_steps
                and completed_steps[node.name].status == StepStatus.COMPLETED
            ):
                logger.info(
                    "Skipping node execution (already COMPLETED)",
                    run_id=run_id,
                    step_name=node.name,
                )
                skipped_steps.append(node.name)
                if completed_steps[node.name].output_payload is not None:
                    outputs[node.name] = completed_steps[node.name].output_payload  # type: ignore[assignment]
                continue

            # Record step execution start
            step_execution_id = self.ledger.record_step_start(run_id, node.name)

            # Fault-tolerant execution wrapper
            try:
                node_output = node.execute(run_id, self.ledger)
                if node_output is None:
                    node_output = {}

                self.ledger.record_step_completion(step_execution_id, node_output)
                executed_steps.append(node.name)
                outputs[node.name] = node_output
                logger.info(
                    "Node execution completed successfully",
                    run_id=run_id,
                    step_name=node.name,
                    step_execution_id=step_execution_id,
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
                    step_execution_id=step_execution_id,
                    error=error_msg,
                    error_type=type(e).__name__,
                    exc_info=True,
                )

                # Record step failure in StateLedger
                self.ledger.record_step_failure(
                    step_execution_id,
                    error_message=error_msg,
                    error_details=error_details,
                )

                # Halt execution and return EngineResult with failure status
                return EngineResult(
                    run_id=run_id,
                    success=False,
                    status=StepStatus.FAILED,
                    executed_steps=executed_steps,
                    skipped_steps=skipped_steps,
                    outputs=outputs,
                    failed_step=node.name,
                    error_message=error_msg,
                    error_details=error_details,
                )

        logger.info(
            "Workflow engine completed all nodes successfully",
            run_id=run_id,
            executed_count=len(executed_steps),
            skipped_count=len(skipped_steps),
        )

        return EngineResult(
            run_id=run_id,
            success=True,
            status=StepStatus.COMPLETED,
            executed_steps=executed_steps,
            skipped_steps=skipped_steps,
            outputs=outputs,
            failed_step=None,
            error_message=None,
            error_details=None,
        )

    def execute(self, run_id: str) -> EngineResult:
        """Alias for run(run_id)."""
        return self.run(run_id)

    def run_pipeline(self, run_id: str) -> EngineResult:
        """Alias for run(run_id) matching PROJECT.md interface signature."""
        return self.run(run_id)
```

---

## 6. Verification & Test Plan

1. **Idempotency Test**:
   - Create a run in SQLite `:memory:` ledger.
   - Execute nodes `[NodeA, NodeB]`.
   - Re-run engine with `[NodeA, NodeB, NodeC]`. Verify `NodeA` and `NodeB` are in `skipped_steps` and `NodeC` is in `executed_steps`.
2. **Fault Tolerance Test**:
   - Create mock `FailingNode` that raises `RuntimeError("Simulated Node Failure")`.
   - Run engine with `[NodeA, FailingNode, NodeB]`.
   - Assert return object is `EngineResult` with `success=False`, `status=StepStatus.FAILED`, `failed_step="FailingNode"`.
   - Assert Python process did not crash.
   - Query `StateLedger` and assert step execution status is `FAILED` and pipeline run status is `FAILED`.
3. **Invalid Run ID Test**:
   - Call `engine.run("non_existent_run_id")`. Assert `PipelineError` is raised.
