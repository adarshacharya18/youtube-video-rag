# Project: Phase 04 Runtime Architecture & State Ledger

## Architecture
- Core module: `src/core/orchestrator/state_ledger.py`
- Tests: `tests/orchestrator/test_state_ledger.py`
- Documentation: `PromptBook/Phase04/01_Runtime_Architecture.md`

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | State Ledger DDL & SQLite Setup | Pure sqlite3, WAL mode PRAGMA, schema initialization for pipeline_runs and step_executions | M1 | R1 |
| 2 | Step Status Management | Support status states (PENDING, IN_PROGRESS, COMPLETED, FAILED) with thread-safe atomic transitions | M1 | R1 |
| 3 | Idempotency & Crash Recovery Logic | Query disk state by run_id/slug, retrieve completed step results, enable pipeline resume | M1 | R2 |
| 4 | Crash Recovery Test Suite | Pytest programmatically simulating artificial crash & resuming operation from SQLite disk file | M2 | Acceptance Criteria |
| 5 | Runtime Architecture Documentation | Document State Ledger schema, recovery state machine, WAL PRAGMA details, and Synchronous Batch-Pipeline paradigm in PromptBook/Phase04/01_Runtime_Architecture.md | M3 | R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | State Ledger Implementation | Implement `src/core/orchestrator/state_ledger.py` with pure sqlite3, WAL PRAGMAs, thread locks, status enums, and state machine methods | none | DONE |
| 2 | Idempotency & Crash Recovery Testing | Implement `tests/orchestrator/test_state_ledger.py` with programmatic crash simulation and recovery assertions | M1 | DONE |
| 3 | Runtime Architecture Documentation | Update `PromptBook/Phase04/01_Runtime_Architecture.md` with State Ledger schema, recovery logic, and Synchronous Batch-Pipeline paradigm | M1 | DONE |

## Interface Contracts
### `StateLedger` API
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

## Code Layout
- Implementation: `/home/adarsh/Documents/Youtube-Channel/src/core/orchestrator/state_ledger.py`
- Tests: `/home/adarsh/Documents/Youtube-Channel/tests/orchestrator/test_state_ledger.py`
- Documentation: `/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase04/01_Runtime_Architecture.md`
