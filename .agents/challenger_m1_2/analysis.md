# Empirical Analysis: Crash Recovery, Step Idempotency, and Resumption (M1 Challenger 2)

**Evaluator**: Empirical Challenger 2 (Phase 14 Milestone M1)  
**Timestamp**: 2026-07-30T23:18:16Z  
**Verdict**: **`APPROVE`**

---

## 1. Executive Summary

Empirical testing was conducted against `PipelineRunner`, `WorkflowEngine`, `StateLedger`, and the `ops.py resume` CLI to evaluate:
1. Crash recovery after node failure midway through pipeline execution.
2. State ledger tracking of completed vs. failed steps.
3. Step idempotency and skipping of previously completed steps upon execution resumption.
4. Multistage incremental recovery across sequential node failures.
5. End-to-end master CLI operation via `python -m src.cli.ops resume`.

All 4 empirical stress tests in `tests/test_m1_2_empirical.py` passed cleanly without error, confirming robust fault tolerance, exact state ledger updates, and seamless step resumption.

---

## 2. Test Harness & Empirical Methodology

An empirical test suite was constructed at `tests/test_m1_2_empirical.py` containing four test harnesses:

1. **`test_crash_recovery_step3_failure_and_resume`**:
   - Executes a 5-node pipeline with custom node identifiers (`step1_ingest` -> `step5_assembly`).
   - Node 3 (`step3_script`) is configured to raise a `RuntimeError` during execution.
   - Asserts that execution halts immediately at Node 3 and returns `success=False` with `status=FAILED`.
   - Queries `StateLedger` directly to confirm Steps 1 and 2 are recorded as `COMPLETED`, Step 3 is NOT completed, and run status is `FAILED`.
   - Clears the simulated failure on Node 3 and invokes `runner.resume_run(run_id)`.
   - Asserts that Steps 1 and 2 are in `skipped_steps` and Node 1/2 execution counters remain 1 (no re-execution).
   - Asserts Steps 3-5 complete successfully and `StateLedger` updates overall run status to `COMPLETED`.

2. **`test_production_nodes_crash_and_ops_cli_resume`**:
   - Executes the production node sequence (`ingest` -> `plan` -> `script_generator` -> `voice_generator` -> `animation_generator` -> `video_assembly`) using `ops.py run`.
   - Monkeypatches `ScriptGeneratorNode.execute` to throw a `ScriptGenerationError` on attempt 1.
   - Verifies `ops.py run` returns exit code 1.
   - Inspects `StateLedger` to confirm `ingest` and `plan` steps are `COMPLETED`, while `script_generator` is `FAILED`.
   - Invokes `ops.py resume --run-id <run_id> --json`.
   - Verifies exit code 0, JSON output indicating `ingest` and `plan` were SKIPPED, remaining nodes completed, and `StateLedger` records final run status as `COMPLETED`.

3. **`test_step_idempotency_on_repeated_runs`**:
   - Verifies pipeline resumption logic when triggering runs on completed vs incomplete slugs.

4. **`test_multistage_crash_and_incremental_resumption`**:
   - Simulates sequential failures across multiple steps (Step 2 fails on run 1; Step 3 fails on run 2; run 3 completes).
   - Verifies that state ledger correctly tracks incremental state checkpoints across multiple resumption cycles.

---

## 3. Empirical Results Summary

| Test Scenario | Test Function | Result | Notes |
|---|---|---|---|
| Step 3 Failure & Resumption | `test_crash_recovery_step3_failure_and_resume` | **PASSED** | Steps 1-2 COMPLETED, Step 3 FAILED, Resumed -> Steps 1-2 SKIPPED, Steps 3-5 COMPLETED |
| Production Nodes & CLI Resume | `test_production_nodes_crash_and_ops_cli_resume` | **PASSED** | `ops.py run` failed at `script_generator`; `ops.py resume` skipped `ingest` & `plan` and completed run |
| Step Idempotency Verification | `test_step_idempotency_on_repeated_runs` | **PASSED** | Unforced rerun on completed slug creates new run; incomplete run auto-resumes |
| Incremental Resumption | `test_multistage_crash_and_incremental_resumption` | **PASSED** | Multi-failure recovery verified without state corruption |

### Pytest Execution Log Output
```
tests/test_m1_2_empirical.py::test_crash_recovery_step3_failure_and_resume PASSED
tests/test_m1_2_empirical.py::test_production_nodes_crash_and_ops_cli_resume PASSED
tests/test_m1_2_empirical.py::test_step_idempotency_on_repeated_runs PASSED
tests/test_m1_2_empirical.py::test_multistage_crash_and_incremental_resumption PASSED

========================= 4 passed, 1 warning in 1.77s =========================
```

---

## 4. Source Code Architecture Breakdown

1. **`PipelineRunner` (`src/core/orchestrator/pipeline_runner.py`)**:
   - `run_problem(slug, force=False)`: Auto-detects incomplete runs for the slug in `StateLedger` and calls `engine.run(existing_run.pipeline_run_id)`.
   - `resume_run(run_id_or_slug)`: Looks up run by ID or slug and invokes `WorkflowEngine.run(run_id)`.
   - `get_status(query)`: Queries StateLedger for completed steps, step timestamps, and execution status.

2. **`WorkflowEngine` (`src/core/workflow/engine.py`)**:
   - Queries `self.ledger.get_completed_steps(run_id)` before iterating through nodes.
   - For each node: checks `if node.name in completed_steps_map and status == COMPLETED`. If true, appends node to `skipped_steps` and `completed_steps` and loads cached output payload from StateLedger.
   - If a node throws an exception, captures traceback, records `record_step_failure`, emits `NodeFailed` event, and returns `EngineResult(success=False, status=FAILED)`.

3. **`StateLedger` (`src/core/orchestrator/state_ledger.py`)**:
   - SQLite-backed transactional ledger operating in WAL mode.
   - Atomically updates step statuses (`IN_PROGRESS`, `COMPLETED`, `FAILED`) and parent run status.

4. **Master CLI `ops.py` (`src/cli/ops.py`)**:
   - `cmd_run`: Calls `runner.run_problem(slug)`.
   - `cmd_resume`: Calls `runner.resume_run(query)`.
   - `cmd_status`: Calls `runner.get_status(query)`.

---

## 5. Conclusion & Verdict

The crash recovery, step idempotency, and resumption mechanisms in `PipelineRunner`, `WorkflowEngine`, `StateLedger`, and `ops.py` work seamlessly and withstand adversarial failure scenarios.

**Explicit Verdict**: **`APPROVE`**
