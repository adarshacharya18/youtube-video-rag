# Phase 14 Exploration Analysis: Master Ops CLI & Production E2E Testing

## Executive Summary
This report presents the findings of the Phase 14 M0 exploration into the CLI module ecosystem, entry point architecture, existing command-line interfaces, and test configuration across the codebase. It details the design specifications for the Master Operations CLI (`src/cli/ops.py`) and the production integration test suite (`tests/production/test_pipeline_e2e.py`).

---

## 1. CLI Architecture & Existing Entry Points Investigation

### 1.1 Dependencies & Libraries
- **Standard Library `argparse`**: Used across all CLI modules in `src/cli/` (`ingestion_cli.py`, `content_cli.py`, `organization_cli.py`, `rag_cli.py`, `ops.py`).
- **No External CLI Frameworks**: Neither `click` nor `typer` is present in `pyproject.toml` or `requirements.txt`.
- **Async & Subprocess Execution**: Entry points bridge sync/async boundaries via `asyncio.run()` (e.g., `ingestion_cli.py`) or wrap subprocess tools/orchestrators (e.g., `content_cli.py`).
- **Exit Code Convention**: CLI entry points return `0` on success and non-zero (`1` or `2`) on execution error or invalid arguments.

### 1.2 Analysis of `src/cli/ops.py` (Current State)
`src/cli/ops.py` currently exists as a initial stub (120 lines).
- **Existing Subcommands**: `health`, `benchmark`, `deploy`, `rollback`, `diagnose`, `status`, `report`.
- **Limitations of Current Stub**:
  - Lacks the mandatory `run` command to trigger pipeline runs.
  - Lacks the mandatory `resume` command to re-run failed/interrupted runs from StateLedger.
  - `status` and `health` currently return static mock/stub text instead of querying `StateLedger` and verifying system dependencies.
  - Does not import or instantiate `PipelineRunner` (`src/core/orchestrator/pipeline_runner.py`).

---

## 2. Requirements Analysis & Design Specification for `src/cli/ops.py`

### 2.1 Target Operational Commands
`src/cli/ops.py` must serve as the master DevOps interface with four primary commands:

1. **`run`**: Triggers execution of the automated pipeline for a problem slug or batch of problems.
   - **Arguments**:
     - `--slug TEXT`: Problem slug to run (e.g., `two-sum`). Optional if `--all` or `--batch` specified.
     - `--batch-file PATH`: Optional JSON/text file containing list of slugs for batch execution.
     - `--db PATH`: Path to SQLite StateLedger database (defaults to `data/state_ledger.db`).
     - `--quality [low|medium|high|4k]`: Rendering quality flag for Manim/FFmpeg.
     - `--json`: Format command output as raw JSON.
   - **Integration**:
     - Instantiates `PipelineRunner` (or `WorkflowEngine`).
     - Creates a new run record in `StateLedger` (`ledger.create_run(slug)`).
     - Invokes `runner.run(run_id)`.
     - Displays real-time / summary execution status and duration.

2. **`status`**: Queries `StateLedger` to inspect active, completed, or failed pipeline executions.
   - **Arguments**:
     - `--run-id TEXT`: Specific pipeline run ID to query.
     - `--slug TEXT`: Filter run history by problem slug.
     - `--limit INT`: Number of recent runs to display (default: 10).
     - `--db PATH`: Path to SQLite StateLedger database.
     - `--json`: Output status payload as formatted JSON.
   - **Behavior**:
     - Reads run records from `StateLedger.get_run()` or queries database.
     - Displays run status (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`), completed steps, error details if failed, and timestamp metrics.

3. **`resume`**: Resumes an interrupted or failed pipeline run from the point of failure.
   - **Arguments**:
     - `--run-id TEXT`: Mandatory run ID of the interrupted/failed pipeline run.
     - `--db PATH`: Path to SQLite StateLedger database.
     - `--json`: Output outcome as raw JSON.
   - **Behavior**:
     - Fetches run record from `StateLedger`.
     - Instantiates `PipelineRunner`/`WorkflowEngine` with existing `run_id`.
     - Calls `runner.run(run_id)`.
     - Leverages `WorkflowEngine` step idempotency: already `COMPLETED` steps are automatically skipped; execution resumes at the first `PENDING` or `FAILED` step.

4. **`health`**: Performs system-wide diagnostic checks across dependencies and services.
   - **Arguments**:
     - `--json`: Output health diagnostic payload as JSON.
   - **Diagnostic Checks**:
     - **Database**: Validates connection and write permissions to `StateLedger` SQLite DB.
     - **FFmpeg**: Executes `ffmpeg -version` via `subprocess.run()` to confirm binary availability.
     - **Manim**: Checks `manim` CLI tool or mock renderer binary availability.
     - **LLM API Credentials**: Validates `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` presence in environment.
     - **Disk Space**: Ensures sufficient disk space in `data/` directory for video rendering artifacts.

5. **Utility Subcommands (Preserved)**:
   - `benchmark`, `deploy`, `rollback`, `diagnose`, `report` can be preserved as secondary helper subcommands.

### 2.2 Output Formatting & Error Handling Standards
- **Output Formatting**:
  - Human-friendly CLI formatting using visual status indicators (e.g., `[SUCCESS]`, `[FAILED]`, `[RUNNING]`, `[SKIPPED]`).
  - `--json` flag support on all commands to allow automated script parsing.
- **Error Handling**:
  - All exceptions caught inside command handlers.
  - Errors logged to structlog logger (`src.core.logger.get_logger`).
  - Exit code `0` returned for success, `1` for execution failures, `2` for invalid CLI usage.

---

## 3. Pytest Infrastructure & Test Design for `tests/production/test_pipeline_e2e.py`

### 3.1 Existing Pytest Configuration
- **Configuration File**: `pyproject.toml`
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  pythonpath = ["."]
  addopts = "-v --tb=short"
  ```
- **Fixtures (`tests/conftest.py`)**:
  - `temp_data_dir`: Creates clean isolated `tmp_path/data`.
  - `test_config`: Loads `PipelineConfig` re-routed to temporary directories.
  - `mock_problem_factory`: Data factory for problem metadata.

### 3.2 Target Structure for `tests/production/test_pipeline_e2e.py`
The new test module `tests/production/test_pipeline_e2e.py` will provide comprehensive integration coverage verifying all nodes are linked and executable via `PipelineRunner` and `ops.py`.

#### Key Test Scenarios:

1. **`TestPipelineEndToEndExecution`**:
   - `test_full_chronological_pipeline_run`: Validates execution across all chronologically linked nodes (`IngestionNode` -> `PlanNode` -> `ScriptGeneratorNode` -> `VoiceGeneratorNode` -> `AnimationGeneratorNode` -> `VideoAssemblyNode`). Verifies all node step outputs are stored in `StateLedger` and final `EngineResult` is `COMPLETED`.
   - `test_event_bus_lifecycle_notifications`: Verifies `NodeStarted`, `NodeCompleted` events are published to `EventBus` for every node in the sequence.

2. **`TestPipelineIdempotencyAndResumption`**:
   - `test_resume_from_failed_step_skips_completed_nodes`: Executes a run where node 3 (e.g. Animation) fails. Asserts status is `FAILED`. Fixes mock/issue and calls `runner.run(run_id)`. Verifies nodes 1 and 2 are skipped (`skipped_steps`), node 3 and node 4 execute to completion, and final state becomes `COMPLETED`.

3. **`TestPipelineFaultToleranceAndErrorHandling`**:
   - `test_node_failure_records_error_details_without_crashing`: Simulates exception in node execution. Verifies `WorkflowEngine` captures exception, records error message and traceback in `StateLedger`, emits `NodeFailed` on `EventBus`, and returns `EngineResult(success=False)`.

4. **`TestMasterCLIOpsIntegration`**:
   - `test_ops_cli_run_command`: Invokes `src.cli.ops.main(['run', '--slug', 'two-sum'])` via `sys.argv` / `main()`, asserts exit code `0` and creation of completed run in ledger.
   - `test_ops_cli_status_command`: Invokes `ops.main(['status', '--run-id', run_id])`, verifies status output contains expected step details.
   - `test_ops_cli_resume_command`: Invokes `ops.main(['resume', '--run-id', failed_run_id])`, verifies resumption and exit code `0`.
   - `test_ops_cli_health_command`: Invokes `ops.main(['health'])`, verifies system health check returns JSON status with `"status": "healthy"`.

---

## 4. Architectural Integration Blueprint

```
                     +-------------------------------+
                     |     DevOps / CLI Engineer     |
                     +---------------+---------------+
                                     |
                                     v
                       +---------------------------+
                       |     src/cli/ops.py        |
                       |  (run, status, resume,    |
                       |         health)           |
                       +-------------+-------------+
                                     |
                                     v
                 +---------------------------------------+
                 | src/core/orchestrator/pipeline_runner |
                 +-------------------+-------------------+
                                     |
                                     v
                      +-----------------------------+
                      |   src/core/workflow/engine   |
                      |       (WorkflowEngine)      |
                      +--------------+--------------+
                                     |
    +--------------------------------+--------------------------------+
    |                                |                                |
    v                                v                                v
+------------------+       +------------------+       +-------------------+
| ScriptGen Node   | ----> | AnimationGen Node| ----> | VideoAssemblyNode |
+------------------+       +------------------+       +-------------------+
    |                                |                                |
    +--------------------------------+--------------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |  State Ledger / SQLite DB   |
                      +-----------------------------+
```

---

## 5. Verification Method

To verify the design once implemented:
1. `pytest tests/production/test_pipeline_e2e.py`
2. `python -m src.cli.ops health`
3. `python -m src.cli.ops run --slug two-sum`
4. `python -m src.cli.ops status`
