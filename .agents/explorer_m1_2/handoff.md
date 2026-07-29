# Handoff Report: Workflow Engine Implementation Design (`src/core/workflow/engine.py`)

## 1. Observation

Direct observations from codebase inspection:
- **`src/core/orchestrator/state_ledger.py`**:
  - Defines `StateLedger` class, `StepStatus` enum (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`), `PipelineRunRecord`, and `StepExecutionRecord`.
  - `record_step_start(pipeline_run_id: str, step_name: str, input_payload: dict | None = None) -> str` returns `step_execution_id: str`. Automatically updates parent pipeline run status to `IN_PROGRESS` if status is `PENDING`.
  - `record_step_completion(step_execution_id: str, output_payload: dict | None = None) -> None` updates step execution status to `COMPLETED` and stores `output_payload`.
  - `record_step_failure(step_execution_id: str, error_message: str, error_details: dict | None = None) -> None` updates step execution status to `FAILED` AND updates parent `pipeline_runs` status to `FAILED`.
  - `get_completed_steps(pipeline_run_id: str) -> dict[str, StepExecutionRecord]` returns a dictionary mapping `step_name -> StepExecutionRecord` for all steps in the run where status is `COMPLETED`.
  - `get_run(pipeline_run_id: str) -> PipelineRunRecord | None` returns the run record or `None` if invalid.
- **`ORIGINAL_REQUEST.md` (Phase 08 R2)**:
  - Requires `src/core/workflow/engine.py` to wrap every node execution in a try/except block that gracefully captures exceptions and updates the SQLite ledger to `FAILED` if a node crashes, without letting exception crash python.
- **`.agents/orchestrator_phase08/PROJECT.md` (Milestone M1)**:
  - `WorkflowEngine` constructor signature: `WorkflowEngine(nodes: Sequence[Node], ledger: Optional[StateLedger] = None)`.
  - Primary execution method: `run(self, run_id: str) -> EngineResult` (with `execute` and `run_pipeline` aliases).
- **`PromptBook/Phase01/01_Global_Rules.md`**:
  - PEP 8, strict typing, structural logging via `structlog.get_logger(__name__)`.

---

## 2. Logic Chain

1. **StateLedger Contract Alignment**: `WorkflowEngine` requires a `nodes: Sequence[Node]` sequence and an optional `ledger: StateLedger`. If `ledger` is omitted, it defaults to `StateLedger("data/state_ledger.db")`.
2. **Pipeline Run Validation**: At the start of `run(run_id: str)`, `engine` queries `ledger.get_run(run_id)`. If `None`, raises `PipelineError` indicating an invalid or non-existent run ID.
3. **Idempotency Checking**: Engine retrieves `completed_steps = ledger.get_completed_steps(run_id)`.
   - Before executing each node in `self.nodes`, engine checks if `node.name in completed_steps` and `completed_steps[node.name].status == StepStatus.COMPLETED`.
   - If match found, execution of `node` is skipped. The engine logs step skipping, appends `node.name` to `skipped_steps`, populates `outputs[node.name]` from `completed_steps[node.name].output_payload`, and continues to the next node.
4. **Node Execution Lifecycle & Fault Tolerance**:
   - For non-skipped nodes, engine calls `step_execution_id = ledger.record_step_start(run_id, node.name)`.
   - Encloses `output = node.execute(run_id, ledger)` inside `try...except Exception as e`.
   - **On Success**: Calls `ledger.record_step_completion(step_execution_id, output)`, appends `node.name` to `executed_steps`, stores `output` in `outputs[node.name]`.
   - **On Exception (`e`)**: Extracts `error_message = str(e)` and formats traceback details (`traceback.format_exc()`). Calls `ledger.record_step_failure(step_execution_id, error_message, error_details)`. Halts further node loop execution immediately and returns `EngineResult` with `success=False`, `status=StepStatus.FAILED`, `failed_step=node.name`, `error_message`, `error_details`. This prevents python runtime crash while persisting failure context in SQLite.
5. **Execution Outcome Encapsulation**: Upon completing all nodes in sequence without failure, returns `EngineResult` with `success=True` and `status=StepStatus.COMPLETED`.

---

## 3. Caveats

1. **`Node` Module Dependency**: `src/core/workflow/engine.py` imports `Node` from `src.core.workflow.node`, which is being designed concurrently by `explorer_m1_1`. Both designs use `Node` signature `execute(self, run_id: str, ledger: StateLedger) -> Dict[str, Any]`.
2. **Return Type of `record_step_start`**: Note that `StateLedger.record_step_start` returns the string `step_execution_id` (a `str`), not a dataclass record. The engine uses this string for `record_step_completion` and `record_step_failure`.
3. **StateLedger Run Status Update**: `StateLedger.record_step_failure` automatically sets the parent `pipeline_run` record status to `FAILED` in SQLite. For successful execution, `EngineResult` reports `status=StepStatus.COMPLETED`.

---

## 4. Conclusion

The implementation design for `src/core/workflow/engine.py` is fully specified in `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_2/analysis.md`. It satisfies all Milestone 1 requirements, providing:
1. `WorkflowEngine` constructor with `nodes: Sequence[Node]` and optional `ledger: StateLedger`.
2. `run(self, run_id: str) -> EngineResult` method (with `execute` and `run_pipeline` aliases).
3. Step skipping idempotency check against `ledger.get_completed_steps(run_id)`.
4. Execution lifecycle wrapping node execution in `try...except Exception as e` with step start/completion/failure recording in `StateLedger`, halting on failure and returning `EngineResult(success=False, status=FAILED)` without crashing the Python process.

---

## 5. Verification Method

Once implemented in `src/core/workflow/engine.py`:
1. Run unit test suite: `pytest tests/workflow/test_engine.py`.
2. Validate mock exception handling:
   - Create mock node that raises `RuntimeError("Mock exception")`.
   - Run `engine.run(run_id)`.
   - Verify process does NOT raise/crash, return object is `EngineResult` with `success is False`, `status == StepStatus.FAILED`, `failed_step == mock_node.name`.
   - Inspect SQLite database or in-memory `StateLedger` to verify `step_executions` record has status `FAILED` and error details populated.
3. Validate idempotency check:
   - Run pipeline with 2 nodes. Re-run pipeline with same `run_id`.
   - Verify `EngineResult.skipped_steps` contains both node names and no node methods were re-executed.
