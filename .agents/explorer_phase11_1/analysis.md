# Core Node Abstraction & Execution Model Analysis

## Executive Summary
This document details the architecture, execution model, state management, schema definitions, error handling, and inheritance patterns of the core `Node` abstraction in the DSA YouTube Video Generation Pipeline. 

The pipeline uses a **synchronous, StateLedger-driven workflow engine** where nodes execute processing steps sequentially. Nodes communicate strictly via an SQLite database (`StateLedger`) using `run_id`, preventing in-memory object coupling between nodes.

---

## 1. Core `Node` Abstraction

The base `Node` class is defined in `src/core/workflow/node.py` as an Abstract Base Class (`ABC`).

### Class Definition & Signature
- **File Path**: `src/core/workflow/node.py` (Lines 18–131)
- **Class**: `class Node(ABC)`

```python
class Node(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name identifier for the workflow node step."""
        pass

    @abstractmethod
    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        """Execute node processing logic for the specified run_id."""
        pass
```

### Key Contract Rules
1. **Abstract Contract**: Every workflow node must implement the `name` property (returning a unique string identifier such as `"ingest"`, `"plan"`, or `"script"`) and the `execute` method. Direct instantiation or missing method implementations raise `TypeError`.
2. **State Ledger Communication**: Nodes receive `run_id` (a string UUID) and `ledger` (a `StateLedger` instance). In-memory state object passing between node instances is strictly prohibited.
3. **Return Type**: `execute` must return a `dict[str, Any]` output payload, which is recorded directly into SQLite `step_executions.output_payload`.

### Node Helper Methods
`Node` provides three built-in helper methods for reading database state safely:

| Helper Method | Signature | Purpose & Error Behavior | Evidence Reference |
|---|---|---|---|
| `get_run_record` | `(run_id: str, ledger: StateLedger) -> PipelineRunRecord` | Queries `ledger.get_run(run_id)`. Raises `PipelineStageError` if `run_id` is missing. | `src/core/workflow/node.py:59-79` |
| `get_completed_step_outputs` | `(run_id: str, ledger: StateLedger) -> dict[str, dict[str, Any]]` | Queries `ledger.get_completed_steps(run_id)` and returns map of `{step_name: output_payload}` for all completed steps. | `src/core/workflow/node.py:81-98` |
| `get_step_output` | `(run_id: str, ledger: StateLedger, step_name: str) -> dict[str, Any]` | Queries `ledger.get_completed_steps(run_id)`. Raises `PipelineStageError` if `step_name` is incomplete or missing. Returns step output dict. | `src/core/workflow/node.py:100-131` |

---

## 2. Workflow Execution Model & Lifecycle (`WorkflowEngine`)

The workflow execution engine is defined in `src/core/workflow/engine.py`.

### Architectural Components
- **File Path**: `src/core/workflow/engine.py` (Lines 75–268)
- **Class**: `class WorkflowEngine`
- **Container**: `EngineResult` (Lines 23–72)

```python
class WorkflowEngine:
    def __init__(
        self,
        nodes: Sequence[Node],
        ledger: Optional[StateLedger] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None
```

### Sequential Execution Flow & Event Lifecycle
For each `Node` in `self.nodes`:

1. **Idempotency Skipping Check**:
   - Queries `completed_steps_map = self.ledger.get_completed_steps(run_id)`.
   - If `node.name` is in `completed_steps_map` with status `COMPLETED`:
     - Skips node execution.
     - Appends `node.name` to `skipped_steps` and `completed_steps`.
     - Loads stored output payload into `outputs[node.name]`.
   - Evidence: `src/core/workflow/engine.py:146-158`

2. **Step Start & Event Emission**:
   - Calls `step_id = self.ledger.record_step_start(run_id, node.name)`.
   - If `event_bus` is present, publishes `NodeStarted(run_id=run_id, node_name=node.name, step_id=step_id)`.
   - Evidence: `src/core/workflow/engine.py:160-165`

3. **Node Execution**:
   - Invokes `node_output = node.execute(run_id, self.ledger)`.
   - If `node_output` is `None`, defaults to `{}`.

4. **Step Completion & Event Emission**:
   - On success, calls `self.ledger.record_step_completion(step_id, node_output)`.
   - If `event_bus` is present, publishes `NodeCompleted(run_id=run_id, node_name=node.name, step_id=step_id, output=node_output)`.
   - Appends `node.name` to `completed_steps` and records `outputs[node.name] = node_output`.
   - Evidence: `src/core/workflow/engine.py:168-185`

5. **Fault-Tolerant Exception Short-Circuiting**:
   - If `node.execute()` raises an exception `e`:
     - Extracts `error_msg = str(e)` and `error_details = {"error_type": type(e).__name__, "traceback": traceback.format_exc()}`.
     - Calls `self.ledger.record_step_failure(step_id, error_msg, error_details)`, updating step status and parent run status to `FAILED`.
     - If `event_bus` is present, publishes `NodeFailed(run_id=run_id, node_name=node.name, step_id=step_id, error_message=error_msg, error_details=error_details)`.
     - Immediately halts pipeline execution and returns `EngineResult(success=False, status=StepStatus.FAILED, failed_step=node.name, error=error_msg, ...)` without executing subsequent nodes.
   - Evidence: `src/core/workflow/engine.py:192-238`

### Engine Result & Adapter
`EngineResult` captures execution telemetry (`success`, `run_id`, `completed_steps`, `skipped_steps`, `failed_step`, `error`, `execution_time_ms`, `status`, `outputs`). Method `to_base_result()` converts it to a standard `BasePipelineResult[Any]`.

---

## 3. Data Dictionary & Schema Definitions

The pipeline uses dictionaries for input/output payloads across state ledger persistence, node execution, and plugin integration.

### Node Input / Output Dictionaries
- **Node Input**: Retrieved via `ledger` helper methods (`get_step_output` or `get_completed_step_outputs`). Outputs are returned as Python `dict[str, Any]` and stored in SQLite as JSON strings in `step_executions.output_payload`.
- **State Ledgers Records**:
  - `PipelineRunRecord` (`src/core/orchestrator/state_ledger.py:39-46`): `pipeline_run_id`, `slug`, `status`, `created_at`, `updated_at`, `metadata`.
  - `StepExecutionRecord` (`src/core/orchestrator/state_ledger.py:50-61`): `step_execution_id`, `pipeline_run_id`, `step_name`, `status`, `input_payload`, `output_payload`, `error_message`, `error_details`.

### Plugin Input Context Dictionary
When external plugins are run via `PluginNodeAdapter` (`src/core/workflow/plugin_loader.py:38-103`), the adapter constructs a sanitized input dictionary for `plugin.process(inputs)`:

```python
inputs: dict[str, Any] = {
    "run_id": run_id,
    "slug": run_record.slug,
    "metadata": run_record.metadata or {},
    "steps": completed_outputs,         # step_name -> output_payload dict
    "prior_outputs": completed_outputs, # Alias mapping
}
```

The adapter verifies that `plugin.process(inputs)` returns a valid `dict`, raising `PluginValidationError` if a non-dict is returned (`src/core/workflow/plugin_loader.py:98-101`).

### Pydantic Schema Integration for LLM Generation
For nodes utilizing structured LLM output (such as prompt generation or script generation):
- Provider base class `BaseLLMProvider` (`src/core/llm/provider.py:130-184`) uses `chat_model.with_structured_output(response_model)` to enforce Pydantic models.
- Returns populated Pydantic model instances which nodes can serialize to dictionaries via `.model_dump()` or `.dict()`.

---

## 4. Error Handling & Retry Mechanics

Error handling exists across three distinct layers:

### Layer 1: WorkflowEngine Execution Layer
- Catches any unhandled `Exception` originating from `node.execute()`.
- Prevents process crashes, updates `StateLedger` status to `FAILED`, emits `NodeFailed` event, and short-circuits execution (`src/core/workflow/engine.py:192-238`).

### Layer 2: LLM Provider Layer (`BaseLLMProvider`)
- Defined in `src/core/llm/provider.py:157-216`.
- Categorizes exceptions into operational classifications via `_translate_exception()` (`src/core/exceptions.py`):
  - `RetryableError`: `RateLimitError` (HTTP 429), `NetworkError` (HTTP 5xx, timeouts, connection failures).
  - `FatalError`: `AuthenticationError` (HTTP 401/403), `ValidationError` (schema/parsing failures), `FatalError` (unclassified).
- For `RetryableError`, executes exponential backoff retries with random jitter up to `max_retries` (`_calculate_backoff_delay`, `src/core/llm/provider.py:210-216`).

### Layer 3: Node-Level Schema Validation & Error-Feedback Loop (Phase 11 Pattern)
For nodes requiring strict JSON schema adherence (e.g. `ScriptGeneratorNode` in Phase 11):
- The node executes LLM generation wrapped in a try/except block catching `ValidationError`, `PipelineValidationError`, or `JSONDecodeError`.
- Upon catching a schema validation error, the node constructs a retry prompt including the explicit validation error message text, instructing the LLM to correct the invalid JSON fields.

---

## 5. How Existing Nodes Inherit & Implement `Node`

There are two primary inheritance and implementation patterns in the codebase:

### Pattern A: Direct Subclassing (`Node`)

Nodes directly subclass `src.core.workflow.Node` and implement `name` and `execute`.

Example from test suite (`tests/workflow/test_engine.py:15-38`):

```python
from typing import Any
from src.core.workflow import Node
from src.core.orchestrator.state_ledger import StateLedger

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
```

### Pattern B: Adapter Subclassing (`PluginNodeAdapter`)

External plugins subclass `PluginNode` (`src/sdk/plugin_base.py:13-56`), which defines `name` and `process(inputs: dict)`. 

`PluginNodeAdapter` (`src/core/workflow/plugin_loader.py:38-103`) subclasses core `Node` and bridges `PluginNode` to `WorkflowEngine`:

```python
class PluginNodeAdapter(Node):
    def __init__(self, plugin: PluginNode) -> None:
        if not isinstance(plugin, PluginNode):
            raise PluginValidationError(...)
        self.plugin = plugin

    @property
    def name(self) -> str:
        return self.plugin.name

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        run_record = self.get_run_record(run_id, ledger)
        completed_outputs = self.get_completed_step_outputs(run_id, ledger)

        inputs = {
            "run_id": run_id,
            "slug": run_record.slug,
            "metadata": run_record.metadata or {},
            "steps": completed_outputs,
            "prior_outputs": completed_outputs,
        }

        output = self.plugin.process(inputs)
        if not isinstance(output, dict):
            raise PluginValidationError(...)
        return output
```

---

## 6. Implementation Template for Phase 11 `ScriptGeneratorNode`

Based on the verified codebase patterns, the Phase 11 Script Generator Node (`src/pipeline/nodes/script_generator_node.py`) must follow this structure:

```python
from typing import Any
from pydantic import BaseModel, ValidationError
from src.core.workflow import Node
from src.core.orchestrator.state_ledger import StateLedger
from src.core.exceptions import PipelineStageError, ValidationError as CoreValidationError

class ScriptGeneratorNode(Node):
    """
    Workflow Engine Node for Phase 11 Script & Narration Generation.
    Uses LLM Provider & Prompt Library to convert DSA problem into timed YouTube script.
    """

    def __init__(self, llm_provider: Any = None, prompt_loader: Any = None, max_retries: int = 3):
        self.llm_provider = llm_provider
        self.prompt_loader = prompt_loader
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return "script"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        # 1. Retrieve prior step outputs (e.g., ingest / plan)
        run_record = self.get_run_record(run_id, ledger)
        # Prior step output lookups:
        # prior_output = self.get_step_output(run_id, ledger, "ingest")

        # 2. Render prompt & execute LLM call with Error-Feedback Retry Loop
        # Catch ValidationError / JSONDecodeError and retry by passing error text to prompt

        # 3. Return dictionary output payload
        return {
            "script": {...},
            "narration": [...],
        }
```

---

## 7. Verification Evidence Summary

| Component | File Path | Line Range | Verification Method | Status |
|---|---|---|---|---|
| Core `Node(ABC)` | `src/core/workflow/node.py` | 18–131 | `pytest tests/workflow/test_engine.py` | Verified (Passes 100%) |
| `WorkflowEngine` & EngineResult | `src/core/workflow/engine.py` | 23–268 | `pytest tests/workflow/test_engine.py` | Verified (Passes 100%) |
| `StateLedger` & Schema | `src/core/orchestrator/state_ledger.py` | 24–430 | `pytest tests/orchestrator/test_state_ledger.py` | Verified |
| `PluginNodeAdapter` & Loader | `src/core/workflow/plugin_loader.py` | 38–220 | `pytest tests/workflow/test_plugin_loader.py` | Verified (Passes 100%) |
| `PluginNode(ABC)` | `src/sdk/plugin_base.py` | 13–56 | `pytest tests/workflow/test_plugin_loader.py` | Verified (Passes 100%) |
| `BaseLLMProvider` Structured LLM | `src/core/llm/provider.py` | 32–279 | Code inspection & unit tests | Verified |
| Central Exceptions | `src/core/exceptions.py` | 13–165 | Code inspection | Verified |
