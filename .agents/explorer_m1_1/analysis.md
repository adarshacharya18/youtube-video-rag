# Milestone 1: Node Abstraction Design & State Ledger Integration (`src/core/workflow/node.py`)

## 1. Architectural Overview & Context

Phase 08 implements the synchronous, fault-tolerant execution engine for the Automated DSA Educational YouTube Video Pipeline. The pipeline executes sequential processing steps:
1. **Ingest**: Ingest problem statements and initial configuration.
2. **Plan**: Generate educational lesson plan and animation script structures.
3. **Script**: Generate script text and voice/narration timings.
4. **Render**: Render visual assets via Manim / FFmpeg.

To guarantee true pipeline idempotency, crash safety, resumeability, and component isolation, pipeline nodes must **strictly communicate via the SQLite State Ledger (`StateLedger`) using `run_id`**. Passing in-memory state objects or DTOs between node instances is prohibited.

`src/core/workflow/node.py` defines the foundational abstract base class `Node(ABC)` that all workflow nodes implement.

---

## 2. Abstract Node Contract (`Node(ABC)`)

### 2.1 Abstract Class Signature
`Node` inherits from `abc.ABC` to establish a mandatory interface for pipeline steps.

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from src.core.orchestrator.state_ledger import StateLedger, StepExecutionRecord, PipelineRunRecord
from src.core.exceptions import PipelineError, PipelineStageError
from src.core.logger import get_logger

logger = get_logger(__name__)

class Node(ABC):
    """
    Abstract Base Class for all workflow execution nodes in the pipeline.

    Nodes represent individual, modular pipeline stages (e.g., Ingest, Plan, Script, Render).
    Nodes are strictly stateless execution handlers; all input state must be retrieved from
    the SQLite StateLedger via run_id, and all output state must be returned as a JSON-serializable
    dictionary payload to be recorded in the StateLedger.
    """
```

### 2.2 Abstract Property `name`
Every concrete `Node` subclass must define a unique `name` string identifier.

```python
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique name identifier for the workflow node step.

        Used as the step_name key when recording step execution in StateLedger
        and when querying prior step outputs.

        Returns:
            str: The unique step name (e.g., 'ingest', 'plan', 'script', 'render').
        """
        pass
```

### 2.3 Abstract Execution Signature
The execution entrypoint for a node is `execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]`.

```python
    @abstractmethod
    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        """
        Execute the node's specific processing logic.

        Args:
            run_id: The unique identifier of the active pipeline run in SQLite StateLedger.
            ledger: The thread-safe StateLedger instance for querying run metadata and
                    outputs of previously completed steps.

        Returns:
            dict[str, Any]: Key-value output payload dictionary to be recorded in SQLite
                            StateLedger upon step completion.

        Raises:
            PipelineError: If step execution encounters an error.
            PipelineStageError: If required prior step outputs or run metadata are missing.
        """
        pass
```

---

## 3. State-Ledger-Only Communication Protocol

### 3.1 Elimination of In-Memory State Object Passing
Traditional pipeline frameworks often pass output objects directly down the execution chain (e.g. `node2.execute(node1_output)`). This introduces several critical failure modes:
- **Tight Coupling**: Node 2 relies directly on Node 1's transient in-memory objects.
- **No Crash Recovery**: If the process crashes mid-pipeline, Node 2 cannot resume because in-memory state is lost.
- **Non-Idempotent Execution**: Re-executing a single failed step requires re-executing all preceding steps in memory.

**State-Ledger Enforcement**:
- Nodes do **NOT** accept preceding step outputs via `__init__` or `execute()`.
- Nodes do **NOT** store transient cross-run state in instance variables (`self._state`).
- Nodes accept only `run_id: str` and `ledger: StateLedger`.
- Node output is returned exclusively as a JSON-serializable `dict[str, Any]`.

### 3.2 Reading Inputs from `StateLedger`
During execution, a node retrieves prior state using two `StateLedger` methods:

1. **Retrieving Run Metadata**:
   ```python
   run_record: PipelineRunRecord | None = ledger.get_run(run_id)
   ```
   Contains `pipeline_run_id`, `slug` (problem identifier), `status`, `created_at`, `updated_at`, and `metadata` (`dict[str, Any] | None`).

2. **Retrieving Prior Step Outputs**:
   ```python
   completed_steps: dict[str, StepExecutionRecord] = ledger.get_completed_steps(run_id)
   ```
   Returns a mapping of `step_name -> StepExecutionRecord`. Each `StepExecutionRecord` contains:
   - `step_name: str`
   - `status: StepStatus` (StepStatus.COMPLETED)
   - `input_payload: dict[str, Any] | None`
   - `output_payload: dict[str, Any] | None`

   To read the output of a prior step `ingest`:
   ```python
   ingest_record = completed_steps.get("ingest")
   if not ingest_record or not ingest_record.output_payload:
       raise PipelineStageError("Required step 'ingest' output missing from StateLedger")
   raw_data = ingest_record.output_payload.get("raw_data")
   ```

### 3.3 Returning Outputs to `WorkflowEngine`
When `node.execute(run_id, ledger)` finishes, it returns a `dict[str, Any]`.
`WorkflowEngine` manages step execution tracking:
1. Engine calls `ledger.record_step_start(run_id, node.name) -> step_execution_id`.
2. Engine executes `output = node.execute(run_id, ledger)`.
3. Engine calls `ledger.record_step_completion(step_execution_id, output_payload=output)`.
4. If an exception occurs, engine calls `ledger.record_step_failure(step_execution_id, error_message=str(e))`.

This separation of concerns keeps `Node` implementation simple: nodes concentrate purely on domain logic and state queries, while `WorkflowEngine` handles transaction logging and exception containment.

---

## 4. Helper Utility Methods on `Node`

To eliminate boilerplate across concrete nodes, `Node` provides built-in helper methods:

```python
    def get_run_record(self, run_id: str, ledger: StateLedger) -> PipelineRunRecord:
        """
        Fetch the PipelineRunRecord for the given run_id.

        Raises:
            PipelineStageError: If the run_id is not found in the ledger.
        """
        record = ledger.get_run(run_id)
        if record is None:
            raise PipelineStageError(f"Pipeline run '{run_id}' not found in StateLedger.")
        return record

    def get_step_output(self, run_id: str, ledger: StateLedger, step_name: str) -> dict[str, Any]:
        """
        Fetch the completed output_payload of a prior step.

        Args:
            run_id: Pipeline run identifier.
            ledger: StateLedger instance.
            step_name: Name of the prior step whose output is required.

        Returns:
            dict[str, Any]: The output payload dictionary.

        Raises:
            PipelineStageError: If prior step was not completed or output_payload is missing.
        """
        completed_steps = ledger.get_completed_steps(run_id)
        if step_name not in completed_steps:
            raise PipelineStageError(
                f"Node '{self.name}' requires output from prior step '{step_name}', "
                f"but step '{step_name}' is not recorded as completed for run '{run_id}'."
            )
        output = completed_steps[step_name].output_payload
        if output is None:
            raise PipelineStageError(
                f"Prior step '{step_name}' has null output_payload in StateLedger for run '{run_id}'."
            )
        return output
```

---

## 5. Complete Implementation Draft for `src/core/workflow/node.py`

```python
"""
Abstract Node Base Class for Phase 08 Workflow Engine.

Defines the contract for pipeline execution nodes and enforces strict
StateLedger-based state passing via run_id.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.core.exceptions import PipelineError, PipelineStageError
from src.core.logger import get_logger
from src.core.orchestrator.state_ledger import PipelineRunRecord, StateLedger, StepExecutionRecord

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
        """
        record = ledger.get_run(run_id)
        if record is None:
            logger.error("Pipeline run record not found", run_id=run_id, node=self.name)
            raise PipelineStageError(f"Pipeline run '{run_id}' not found in StateLedger for node '{self.name}'.")
        return record

    def get_step_output(self, run_id: str, ledger: StateLedger, step_name: str) -> dict[str, Any]:
        """
        Retrieve output payload dictionary of a previously completed step.

        Args:
            run_id: Pipeline run identifier.
            ledger: StateLedger instance.
            step_name: Name of prior completed step.

        Returns:
            dict[str, Any]: Output payload dictionary.

        Raises:
            PipelineStageError: If step is missing, incomplete, or output is null.
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
                f"Node '{self.name}' requires step '{step_name}' completion, "
                f"but '{step_name}' was not completed for run '{run_id}'."
            )

        step_record = completed_steps[step_name]
        if step_record.output_payload is None:
            logger.error(
                "Step output payload is null",
                run_id=run_id,
                node=self.name,
                required_step=step_name,
            )
            raise PipelineStageError(
                f"Prior step '{step_name}' has null output_payload in StateLedger for run '{run_id}'."
            )

        return step_record.output_payload
```

---

## 6. Concrete Example Usage (Mock Nodes for Testing & Pipeline Setup)

```python
class MockIngestNode(Node):
    @property
    def name(self) -> str:
        return "ingest"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        run = self.get_run_record(run_id, ledger)
        return {
            "slug": run.slug,
            "raw_problem": f"Problem content for {run.slug}",
            "ingested_at": "2026-07-29T12:00:00Z",
        }


class MockPlanNode(Node):
    @property
    def name(self) -> str:
        return "plan"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        ingest_output = self.get_step_output(run_id, ledger, "ingest")
        return {
            "plan_title": f"Educational Plan for {ingest_output['slug']}",
            "steps": ["Introduction", "Algorithm", "Code", "Complexity"],
        }
```

---

## 7. Verification Strategy for Implementer

1. **Unit Test Suite**: `tests/workflow/test_node.py`
   - Test subclassing `Node` without defining `name` raises `TypeError` (can't instantiate abstract class).
   - Test subclassing `Node` without defining `execute` raises `TypeError`.
   - Test `get_run_record` returns `PipelineRunRecord` or raises `PipelineStageError` when invalid `run_id` is passed.
   - Test `get_step_output` returns `output_payload` dictionary when step is completed in `StateLedger`.
   - Test `get_step_output` raises `PipelineStageError` when prior step was not executed or failed.
2. **Integration with WorkflowEngine**:
   - Verify `WorkflowEngine` can iterate through a sequence of `Node` instances, invoking `node.execute(run_id, ledger)` and updating `StateLedger`.
