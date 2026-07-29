# Phase 10 Event Bus & Workflow Engine Test Architecture Analysis

## 1. Overview
This analysis provides a comprehensive survey of the test infrastructure, pytest configuration, existing test patterns, mock object/listener conventions, and verification methods for `tests/events/test_bus.py` and `tests/workflow/test_engine.py`.

---

## 2. Pytest Configuration & Environment

- **Configuration File**: `pytest.ini` at project root.
- **Default Options (`addopts`)**: `--strict-markers --cov=src --cov-report=term-missing -v`
- **Test Root Directory**: `tests/`
- **Defined Markers**:
  - `unit`: Fast, isolated unit tests.
  - `integration`: Wiring multiple modules or filesystem access.
  - `e2e`: End-to-end pipeline execution tests.
  - `performance`: Performance/memory profiling tests.
- **Global Fixtures (`tests/conftest.py`)**:
  - Sets `os.environ["ENVIRONMENT"] = "testing"`.
  - `temp_data_dir`: Creates clean `tmp_path / "data"` directory.
  - `test_config`: Loads `PipelineConfig` pointed at `temp_data_dir`.
  - `mock_logger`: Patches `src.core.logger.get_logger` to prevent verbose log spam during test runs.
  - `mock_problem_factory`: Helper factory function for problem payload dictionaries.

---

## 3. Existing Test Conventions & Patterns

### 3.1 Directory Layout & Naming
- Tests mirror source code structure:
  - Source: `src/core/events/bus.py` → Test: `tests/events/test_bus.py`
  - Source: `src/core/workflow/engine.py` → Test: `tests/workflow/test_engine.py`
- Test functions use descriptive snake_case names starting with `test_` (e.g., `test_fault_tolerant_exception_suppression`).
- Docstrings are included in every test function stating the target behavior under test.

### 3.2 Mocking & Listener Patterns
- Standard library `unittest.mock.MagicMock` is preferred for mock listeners.
- **Fault Tolerance Testing**:
  - Listener failure simulation: `bad_listener = MagicMock(side_effect=RuntimeError("Intentional crash"))`.
  - Verification: Asserts that calling `publish()` or `engine.run()` does not raise `RuntimeError`, that `bad_listener` is invoked, and that execution proceeds uninterrupted for remaining listeners.
- **Mock Nodes for Workflow Engine**:
  - Concrete subclasses of `Node` (e.g., `MockIngestNode`, `FailingNode`, `MissingPriorStepNode`) are defined within test files to simulate node behaviors without network or heavy disk I/O.

### 3.3 Database Isolation
- `StateLedger(":memory:")` is passed into `WorkflowEngine` during unit tests to isolate tests from disk state and ensure fast execution.

---

## 4. Test Suite Breakdown

### 4.1 `tests/events/test_bus.py`
Contains unit tests verifying `EventBus` and event models (`BaseEvent`, `NodeStarted`, `NodeCompleted`, `NodeFailed`):
1. `test_event_models_initialization()`: Verifies event dataclass instantiation, timestamp generation, and payload field assignments.
2. `test_subscribe_and_publish()`: Verifies event dispatching to subscribed listener callables using `MagicMock.assert_called_once_with()`.
3. `test_unsubscribe()`: Verifies listener removal using `MagicMock.assert_not_called()`.
4. `test_inheritance_dispatch()`: Verifies polymorphic subscriptions (e.g. subscribing to `BaseEvent` receives `NodeStarted`, `NodeCompleted`, `NodeFailed`).
5. `test_fault_tolerant_exception_suppression()`: Verifies that an exception (`RuntimeError`) raised inside a mock listener is caught and logged, preventing publisher crash and allowing other subscribers to receive events.
6. `test_subscribe_any_type()`: Verifies wildcard/`Any` type subscriptions.
7. `test_clear_subscribers()`: Verifies clearing all subscribers from the bus.

### 4.2 `tests/workflow/test_engine.py`
Contains unit tests for `WorkflowEngine` and `Node` lifecycle execution:
1. `test_node_abstract_instantiation_raises()`: Abstract class enforcement.
2. `test_workflow_engine_empty_nodes_raises()`: Validates non-empty node sequence constraint.
3. `test_workflow_engine_invalid_run_id_raises()`: Validates invalid `run_id` handling.
4. `test_workflow_engine_successful_pipeline_execution()`: Sequential multi-node execution and `EngineResult` outputs.
5. `test_workflow_engine_idempotency_skipping()`: Checks step idempotency skipping logic via `StateLedger`.
6. `test_workflow_engine_node_failure_handling()`: Ensures engine short-circuits on node failure and records `FAILED` status.
7. `test_workflow_engine_missing_prior_step_error()`: Checks missing dependency error handling.
8. `test_workflow_engine_aliases()`: Verifies method aliases (`execute`, `run_pipeline`).
9. `test_workflow_engine_event_bus_lifecycle_emissions()`: Verifies emission of `NodeStarted`, `NodeCompleted`, and `NodeFailed` events with correct attributes (`run_id`, `node_name`, `step_id`, outputs, error details).
10. `test_workflow_engine_event_bus_listener_runtime_error_suppression()`: Verifies that when an attached `EventBus` listener raises `RuntimeError`, `WorkflowEngine.run()` completes successfully without crashing.

---

## 5. Summary of Verification Requirements

To verify the event bus and workflow engine tests:
```bash
pytest tests/events/test_bus.py tests/workflow/test_engine.py
```
- **Expected Result**: 17 passed tests in ~0.3s.
- **Coverage Output**: `src/core/events/bus.py` at 100% coverage, `src/core/workflow/engine.py` at 99% coverage.
