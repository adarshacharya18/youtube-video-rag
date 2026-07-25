## 2026-07-25T15:06:48Z
You are Worker 1 for Phase 04 of the Automated DSA Educational YouTube Video Pipeline.
Your Working Directory: /home/adarsh/Documents/Youtube-Channel/.agents/worker_impl_1
Request File: /home/adarsh/Documents/Youtube-Channel/.agents/ORIGINAL_REQUEST.md

Exclusive Write Ownership: `src/core/orchestrator/state_ledger.py` (and creating directory `src/core/orchestrator/` if it does not exist). Do NOT modify tests or documentation files.

Task:
Implement `src/core/orchestrator/state_ledger.py` using pure standard library `sqlite3`.

Requirements:
1. Status states: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED` (using standard Python `Enum` or `StrEnum`).
2. Dataclasses: `PipelineRunRecord`, `StepExecutionRecord` for state representations.
3. Database Initialization: `init_db()` creating `pipeline_runs` and `step_executions` tables if they don't exist.
4. Explicit PRAGMA statements on connection creation:
   - `PRAGMA journal_mode=WAL;`
   - `PRAGMA synchronous=NORMAL;`
   - `PRAGMA foreign_keys=ON;`
   - `PRAGMA busy_timeout=5000;`
5. Methods to implement:
   - `__init__(db_path: str | Path)`
   - `init_db() -> None`
   - `create_run(slug: str, metadata: dict | None = None) -> str` (returns pipeline_run_id)
   - `get_run(pipeline_run_id: str) -> PipelineRunRecord | None`
   - `get_run_by_slug(slug: str) -> PipelineRunRecord | None`
   - `record_step_start(pipeline_run_id: str, step_name: str, input_payload: dict | None = None) -> str` (returns step_execution_id)
   - `record_step_completion(step_execution_id: str, output_payload: dict | None = None) -> None`
   - `record_step_failure(step_execution_id: str, error_message: str, error_details: dict | None = None) -> None`
   - `get_completed_steps(pipeline_run_id: str) -> dict[str, StepExecutionRecord]`
   - `get_step_execution(step_execution_id: str) -> StepExecutionRecord | None`
   - `close() -> None`
6. Thread-safety: Protect SQLite write transactions with a `threading.Lock()`.
7. Logging and Exception handling: Use `src.core.logger` (`get_logger`) and `src.core.exceptions` (`PipelineError`).
