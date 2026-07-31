# Empirical Analysis & Stress Test Report — Phase 14 Milestone M1

## Executive Summary
This report presents the empirical verification and adversarial stress testing results for `src/cli/ops.py` and `src/core/orchestrator/pipeline_runner.py`.

A custom 30-scenario stress test harness (`/tmp/test_m1_cli_runner.py`) was constructed and executed against the live Python environment (`python3 -m src.cli.ops ...`). All 30 automated test cases passed, confirming that the primary subcommands (`run`, `status`, `resume`, `health`) and the 6-stage chronological pipeline orchestrator function as designed.

However, adversarial stress testing revealed **3 notable architectural/CLI design vulnerabilities** regarding `--json` stream clean-ness, resource cleanup on exceptions, and health check severity reporting.

---

## 1. Scope of Testing

### Core Modules Tested:
1. **Master CLI (`src/cli/ops.py`)**:
   - Subcommands: `run`, `status`, `resume`, `health`, `benchmark`, `deploy`, `rollback`, `diagnose`, `report`.
   - Options: `--slug`, `--run-id`, `--json`, `--db`, `--force`, `--output`, `--file`, `--dlq-path`.
2. **Pipeline Orchestrator (`src/core/orchestrator/pipeline_runner.py`)**:
   - Chronological node chaining (Ingestion -> Plan -> Script -> TTS -> Manim -> FFmpeg).
   - Checkpoint-based resumption (`resume_run`, `run_problem` with `force=False`).
   - EventBus lifecycle event dispatch (`NodeStarted`, `NodeCompleted`, `NodeFailed`).
   - StateLedger tracking and error reporting.

---

## 2. Empirical Test Results

### Test Suite Summary:
- **Total Test Cases**: 30
- **Passed**: 30
- **Failed**: 0
- **Execution Time**: 39.50 seconds

| Group / Feature | Test Description | Input / Command | Expected Outcome | Actual Outcome | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CLI Run** | Standard execution | `ops run --slug two-sum` | Status 0, report on stdout | Exit 0, execution report rendered | **PASS** |
| **CLI Run** | JSON output formatting | `ops run --slug two-sum --json` | Status 0, valid JSON output | Exit 0, JSON parsed with `success: true` | **PASS** |
| **CLI Run** | Missing required slug | `ops run` | Status 1, error on stderr | Exit 1, `"Error: Must specify --slug"` | **PASS** |
| **CLI Status** | Query status by slug | `ops status --slug valid-slug` | Status 0, displays run summary | Exit 0, 6/6 steps shown completed | **PASS** |
| **CLI Status** | Query status by run_id | `ops status --run-id <id>` | Status 0, displays step details | Exit 0, status matched run ID | **PASS** |
| **CLI Status** | JSON status output | `ops status --slug valid-slug --json` | Status 0, valid JSON payload | Exit 0, `found: true`, 6 steps listed | **PASS** |
| **CLI Status** | Non-existent slug | `ops status --slug unknown` | Status 1, error message | Exit 1, `"No pipeline run found"` | **PASS** |
| **CLI Status** | Non-existent slug (JSON) | `ops status --slug unknown --json` | Status 1, `{"found": false}` | Exit 1, JSON `{"found": false}` | **PASS** |
| **CLI Status** | Missing query args | `ops status` | Status 1, error on stderr | Exit 1, `"Error: Must specify..."` | **PASS** |
| **CLI Resume** | Resume completed run | `ops resume --slug two-sum` | Status 0, skips completed steps | Exit 0, resumption report displayed | **PASS** |
| **CLI Resume** | Invalid run ID | `ops resume --run-id invalid-999` | Status 1, error on stderr | Exit 1, `"Error resuming pipeline..."` | **PASS** |
| **CLI Resume** | Invalid run ID (JSON) | `ops resume --run-id invalid-999 --json` | Status 1, `{"success": false}` | Exit 1, JSON error returned | **PASS** |
| **CLI Resume** | Missing query args | `ops resume` | Status 1, error on stderr | Exit 1, `"Error: Must specify..."` | **PASS** |
| **CLI Health** | Healthy environment | `ops health` | Status 0, diagnostic report | Exit 0, DB & binaries checked | **PASS** |
| **CLI Health** | Health JSON output | `ops health --json` | Status 0, valid JSON payload | Exit 0, JSON health structure | **PASS** |
| **CLI Health** | Database failure handling | `ops health --db /root/forbidden.db` | Status 1, status: unhealthy | Exit 1, `connected: false`, `unhealthy` | **PASS** |
| **CLI Health** | Database failure (JSON) | `ops health --db /root/forbidden.db --json`| Status 1, JSON status unhealthy | Exit 1, JSON `status: unhealthy` | **PASS** |
| **CLI Parser** | Invalid CLI flag | `ops --invalid-flag` | Status 2, argparse error | Exit 2, usage error printed | **PASS** |
| **CLI Parser** | Subcommand invalid flag | `ops run --unknown-opt` | Status 2, argparse error | Exit 2, usage error printed | **PASS** |
| **CLI Bench** | Hardware benchmark JSON | `ops benchmark --json` | Status 0, JSON metrics | Exit 0, JSON metrics printed | **PASS** |
| **CLI Deploy** | Pre-flight release deploy | `ops deploy` | Status 0 or 1 | Exit 1 (dependency check failed as expected) | **PASS** |
| **CLI Rollback** | Rollback missing file arg | `ops rollback` | Status 1, error on stderr | Exit 1, `"Must provide --file"` | **PASS** |
| **CLI Rollback** | Rollback nonexistent file | `ops rollback --file missing.sqlite` | Status 1, error on stderr | Exit 1, `"Backup file ... does not exist"` | **PASS** |
| **CLI Rollback** | Rollback success | `ops rollback --file backup.sqlite` | Status 0, file restored | Exit 0, target DB replaced | **PASS** |
| **CLI Diagnose** | DLQ clean state | `ops diagnose --dlq-path clean.jsonl` | Status 0, DLQ clean message | Exit 0, `"DLQ is clean"` | **PASS** |
| **CLI Diagnose** | DLQ entry parsing | `ops diagnose --dlq-path dlq.jsonl` | Status 0, displays error trace | Exit 0, displays run_id and error trace | **PASS** |
| **CLI Report** | Generate markdown report | `ops report --output report.md` | Status 0, creates Markdown file | Exit 0, report created at target path | **PASS** |
| **Orchestrator**| Checkpoint resumption | Fail node 2, rerun `run_problem` | Resumes node 2, skips node 1 | Node 1 skipped, Node 2 & 3 executed | **PASS** |
| **Orchestrator**| EventBus subscription | Subscribe `NodeStarted`, `NodeCompleted` | Events emitted during run | 2 NodeStarted & 2 NodeCompleted received | **PASS** |
| **Orchestrator**| Missing run_id resume | `runner.resume_run("invalid-id")` | Raises `PipelineError` | `PipelineError` raised with message | **PASS** |

---

## 3. Adversarial Challenges & Findings

### Challenge 1: Log Stream Contamination in `--json` Mode [MEDIUM]
- **Assumption Challenged**: Passing `--json` to `ops` CLI commands produces pure, unpolluted JSON on `stdout`.
- **Attack Scenario**: Downstream automation tools (e.g. `ops run --slug two-sum --json | jq .run_id`) attempt to parse stdout.
- **Observation**:
  - In `cmd_benchmark`, `print("Starting hardware benchmark profiling...")` is printed to stdout before `json.dumps()`.
  - In `cmd_run`, `cmd_status`, `cmd_resume`, `cmd_health`, `structlog` emits INFO logs to stdout if logging handlers output to stdout (`StreamHandler(sys.stdout)` in `src/core/logger.py`).
- **Blast Radius**: Causes standard JSON parsers (`json.loads`, `jq`) to fail with `JSONDecodeError`.
- **Suggested Defense**:
  1. Direct all `structlog` console output to `sys.stderr`.
  2. In `cmd_benchmark`, remove the non-JSON `print()` statement when `args.json` is True.

### Challenge 2: Resource Leakage on Unhandled Subcommand Exceptions [LOW]
- **Assumption Challenged**: `cmd_status` and `cmd_run` always close the `StateLedger` SQLite database connection.
- **Attack Scenario**: An unhandled exception occurs inside `runner.get_status()` or `runner.run_problem()`.
- **Observation**:
  In `cmd_status`:
  ```python
  try:
      runner = PipelineRunner(db_path=db_path)
      status_info = runner.get_status(query)
      runner.close()  # Skipped if get_status raises exception!
  except Exception as e:
      ...
  ```
- **Blast Radius**: SQLite database connection remains open until process termination / garbage collection.
- **Suggested Defense**: Wrap `PipelineRunner` usage in `with PipelineRunner(db_path=db_path) as runner:` context managers.

### Challenge 3: Incomplete Dependency Failure Exit Code in `cmd_health` [LOW]
- **Assumption Challenged**: `ops health` returns a non-zero exit code if required production binaries (`ffmpeg`, `manim`) are missing.
- **Attack Scenario**: DevOps engineer runs `ops health` in a CI/CD pre-flight check pipeline.
- **Observation**:
  When `ffmpeg` or `manim` is missing, `health_data["status"]` is set to `"degraded"`. `cmd_health` returns `0 if health_data["status"] != "unhealthy" else 1`. Thus it returns exit code `0`.
- **Blast Radius**: CI/CD pre-flight pipeline reports success even when video assembly binaries are missing, allowing deployment to fail later at runtime.
- **Suggested Defense**: Introduce a `--strict` flag to `ops health` that exits with code `1` if health status is `"degraded"`.

---

## 4. Unchallenged Areas
- **Database Concurrency / Write Locks**: Multi-process concurrent CLI invocations writing to the same SQLite database simultaneously were not stress-tested under high lock contention (SQLite WAL mode is recommended).
