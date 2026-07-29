# Phase 08: Workflow Engine Test Suite & Testing Patterns Analysis Report

## Executive Summary
This report presents a thorough survey of the existing test suite, testing conventions, pytest configuration, SQLite StateLedger integration, and design specifications for **Phase 08: The Workflow Engine**. 

Currently, `src/core/workflow/` and `tests/workflow/` do not exist. To fulfill Phase 08 requirements and acceptance criteria, `src/core/workflow/` must implement `node.py` (abstract `Node` base class) and `engine.py` (fault-tolerant execution engine). The test suite `tests/workflow/test_engine.py` must verify fault-tolerant execution, idempotency, and explicit exception catching where failing mock nodes intentionally raise exceptions and trigger SQLite StateLedger updates to `FAILED`.

---

## 1. Existing Test Suite Structure & Organization

### 1.1 Directory Structure
The repository test suite is located in `tests/`, structured as follows:
```
tests/
├── conftest.py                   # Root pytest configuration and global fixtures
├── core/                         # Base, Config, Exception, Logger tests
│   ├── test_base.py
│   ├── test_config.py
│   ├── test_exceptions.py
│   └── test_logger.py
├── models/                       # Pydantic V2 models & validation tests
│   └── test_validation.py
├── llm/                          # LLM provider & Jinja2 prompt loader tests
│   ├── test_providers.py
│   └── test_prompt_loader.py
├── orchestrator/                 # SQLite StateLedger tests
│   └── test_state_ledger.py
├── ingestion/                    # Parser tests
│   └── test_parser.py
├── integration/                  # End-to-end pipeline tests
│   └── test_end_to_end_pipeline.py
└── fixtures/                     # Test sample files (Markdown, HTML, JSON)
```

### 1.2 Pytest Configuration
- **`pytest.ini`**:
  - `addopts = --strict-markers --cov=src --cov-report=term-missing -v`
  - `testpaths = tests`
  - Custom markers: `unit`, `integration`, `e2e`, `performance`.
- **`pyproject.toml`**:
  - Sets `pythonpath = ["."]`.
  - Configures `addopts = "-v --tb=short"`.

---

## 2. Test Suite Conventions, Fixtures & Mocking Patterns

### 2.1 Global Fixtures (`tests/conftest.py`)
- **Environment Pinning**: `os.environ["ENVIRONMENT"] = "testing"` executed automatically on import.
- **`temp_data_dir`**: Isolated temporary directory created via `tmp_path / "data"`.
- **`test_config`**: Returns deterministic `PipelineConfig` instance re-routed to `temp_data_dir`.
- **`mock_logger`**: Mocks `src.core.logger.get_logger` via `pytest-mock` (`mocker`).
- **`mock_problem_factory`**: Factory fixture generating dummy problem payload dictionaries.

### 2.2 Core Testing Conventions
1. **Strict Type Hinting**: All test functions use explicit return types (`-> None`).
2. **Isolation & Persistence**: Disk operations use pytest's built-in `tmp_path` fixture to guarantee zero state leakage across test runs.
3. **SQLite WAL Verification**: Tests verify SQLite `PRAGMA journal_mode=WAL;`, `synchronous=NORMAL;`, `foreign_keys=ON;`, and `busy_timeout=5000;`.
4. **Mocking External APIs**:
   - `unittest.mock.patch` and `MagicMock` are used extensively to mock LangChain LLM clients (`ChatOpenAI`, `ChatAnthropic`).
   - Exceptions (`RateLimitError`, `NetworkError`, `AuthenticationError`, `ValidationError`) are intentionally simulated using `.side_effect`.
5. **Pydantic V2 Validation Testing**: Tests feed valid data and malformed JSON (missing fields, wrong types, non-finite floats, empty/whitespace strings) asserting `pytest.raises(ValidationError)`.

---

## 3. Workflow Engine Integration with SQLite StateLedger

### 3.1 `StateLedger` Architecture (`src/core/orchestrator/state_ledger.py`)
The Workflow Engine interacts directly with `StateLedger`. Key methods and data structures include:

- **Statuses (`StepStatus`)**: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`.
- **Run Creation**: `ledger.create_run(slug: str, metadata: dict | None) -> str` (returns `pipeline_run_id`).
- **Step Execution Start**: `ledger.record_step_start(pipeline_run_id, step_name, input_payload) -> str` (returns `step_execution_id` and transitions run status to `IN_PROGRESS`).
- **Step Execution Completion**: `ledger.record_step_completion(step_execution_id, output_payload)`.
- **Step Execution Failure**: `ledger.record_step_failure(step_execution_id, error_message, error_details)`.
  - Automatically updates `step_executions.status = 'FAILED'`.
  - Automatically updates parent `pipeline_runs.status = 'FAILED'`.
- **State Lookup**: `ledger.get_completed_steps(pipeline_run_id) -> dict[str, StepExecutionRecord]` (enables pipeline idempotency by identifying already executed steps).

---

## 4. Phase 08 Requirements & Architecture Overview

### 4.1 Required Components
1. **`src/core/workflow/node.py`**:
   - Base abstract class `Node` (or `BaseNode`).
   - Property `name: str` identifying the step (e.g. `"ingest"`, `"plan"`, `"script"`, `"render"`).
   - Method `execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]` (or `run(...)`).
   - Nodes **must not** accept or return in-memory state down the pipeline chain; they communicate strictly by reading prior step outputs from `ledger` using `run_id` and writing new outputs to `ledger`.

2. **`src/core/workflow/engine.py`**:
   - Class `WorkflowEngine`.
   - Method `run(self, run_id: str, nodes: list[Node]) -> dict[str, Any]`.
   - Iterates through `nodes`:
     - Checks idempotency: if step is already `COMPLETED` in `ledger.get_completed_steps(run_id)`, skips execution.
     - Calls `step_id = ledger.record_step_start(run_id, node.name, input_payload)`.
     - Wraps `node.execute(run_id, ledger)` in a `try...except Exception as e` block.
     - On Success: calls `ledger.record_step_completion(step_id, output_payload)`.
     - On Exception:
       - Catches `e`.
       - Calls `ledger.record_step_failure(step_id, error_message=str(e), error_details={"exception_type": type(e).__name__})`.
       - Prevents application crash (does not let unhandled exception propagate out of engine execution).
       - Halts subsequent node execution and returns workflow summary with status `FAILED`.

---

## 5. Test Suite Specifications for `tests/workflow/test_engine.py`

### 5.1 Test Fixtures
`tests/workflow/test_engine.py` should define or import the following fixtures:
```python
@pytest.fixture
def workflow_ledger(tmp_path: Path) -> StateLedger:
    """Provides a fresh isolated SQLite StateLedger instance for workflow testing."""
    db_path = tmp_path / "test_workflow_ledger.db"
    ledger = StateLedger(db_path)
    yield ledger
    ledger.close()
```

### 5.2 Concrete Mock Nodes for Testing
```python
class SuccessfulMockNode(Node):
    def __init__(self, name: str, output_data: dict[str, Any] | None = None):
        self.name = name
        self.output_data = output_data or {"status": "success", "node": name}

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        return self.output_data

class FailingMockNode(Node):
    def __init__(self, name: str, exception_to_raise: Exception | None = None):
        self.name = name
        self.exception_to_raise = exception_to_raise or RuntimeError(f"Simulated failure in node '{name}'")

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        raise self.exception_to_raise
```

### 5.3 Mandatory Test Cases

#### Test Case 1: Acceptance Criteria Exception Handling Test (`test_engine_catches_exception_and_updates_ledger_failed`)
- **Objective**: Verify requirement: "The test suite MUST use mock nodes that intentionally throw exceptions, explicitly verifying that the engine catches them, prevents application crash, and correctly updates the mock SQLite ledger to 'FAILED'."
- **Setup**:
  1. Create run `run_id = ledger.create_run(slug="failing-test-slug")`.
  2. Instantiate Node 1 (`SuccessfulMockNode("ingest")`) and Node 2 (`FailingMockNode("plan", RuntimeError("LLM API Timeout"))`).
  3. Instantiate Node 3 (`SuccessfulMockNode("script")`).
- **Execution**: `engine.run(run_id, [node1, node2, node3])`.
- **Assertions**:
  1. Engine returns without raising an unhandled exception (prevents application crash).
  2. Node 1 execution in ledger is `StepStatus.COMPLETED`.
  3. Node 2 execution in ledger is `StepStatus.FAILED`.
  4. Node 2 `error_message` in ledger matches `"LLM API Timeout"`.
  5. Parent pipeline run status in ledger is `StepStatus.FAILED`.
  6. Node 3 was **not** executed (pipeline halted upon Node 2 failure).

#### Test Case 2: Successful End-to-End Execution (`test_engine_successful_workflow`)
- **Objective**: Verify full sequence of successful nodes.
- **Assertions**: All steps transition to `COMPLETED`, parent run status transitions to `COMPLETED` (or remains `IN_PROGRESS`/`COMPLETED`), ledger records output payloads.

#### Test Case 3: Idempotency & Resumption (`test_engine_skips_already_completed_nodes`)
- **Objective**: Verify engine skips nodes already completed in ledger.
- **Assertions**: Re-running workflow with completed nodes does not re-execute completed nodes.

#### Test Case 4: State Communication via Ledger (`test_nodes_communicate_strictly_via_ledger`)
- **Objective**: Verify nodes pass data exclusively via SQLite ledger lookups and `run_id`.
- **Assertions**: Node 2 reads Node 1's output from `ledger.get_completed_steps(run_id)`.

---

## 6. Summary Matrix of Requirements & Test Verification

| Requirement | Module/File | Key Test Function | Verification Method |
|---|---|---|---|
| Abstract Node Interface | `src/core/workflow/node.py` | `test_node_abstraction` | Subclass `Node`, attempt direct instantiation (should raise TypeError) |
| Fault-Tolerant Engine | `src/core/workflow/engine.py` | `test_engine_catches_exception_and_updates_ledger_failed` | Run `FailingMockNode`, assert process doesn't crash & ledger marked `FAILED` |
| Ledger Data Isolation | `src/core/workflow/node.py` | `test_nodes_communicate_strictly_via_ledger` | Pass only `run_id` & `ledger` to `execute()`, assert no in-memory payload passed |
| Workflow Idempotency | `src/core/workflow/engine.py` | `test_engine_skips_already_completed_nodes` | Pre-populate completed step in `StateLedger`, execute engine |
| Pytest Command Execution | `tests/workflow/test_engine.py` | Full suite execution | `pytest tests/workflow/test_engine.py` exits 0 |
