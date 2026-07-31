Verdict: REQUEST_CHANGES

# Handoff Report — Phase 14 Milestone 3 (Integration & Production Orchestration) Audit

**Agent**: Challenger 2 (`challenger_m3_4`)  
**Target Scope**: Phase 14 ONLY
- `src/cli/ops.py`
- `src/core/orchestrator/pipeline_runner.py`
- `PromptBook/Phase14/01_Production_Orchestration.md`
- `tests/production/test_pipeline_e2e.py`

---

## 1. Observation

1. **Pytest Integration Suite Result**:
   - Command: `pytest tests/production/test_pipeline_e2e.py`
   - Output: `2 passed, 2 warnings in 1.69s`
   - Verified that `test_pipeline_e2e_full_execution` and `test_pipeline_e2e_resume_flow` execute and pass successfully.

2. **Empirical Stress Test Harness Findings** (`/tmp/test_phase14_stress.py`):
   - Command: `python3 -m src.cli.ops health --json | jq .`
   - Output:
     ```
     jq: parse error: Invalid numeric literal at line 1, column 11
     ```
     Command exited with code 5.
   - Direct execution command: `python3 -m src.cli.ops health --json`
   - Console Output:
     ```
     2026-07-31 10:31:04 [info     ] Initialized StateLedger database connection db_path=data/state_ledger.db
     2026-07-31 10:31:04 [info     ] Database schema initialized successfully
     2026-07-31 10:31:04 [info     ] Closed StateLedger database connection
     2026-07-31 10:31:04 [warning  ] Manim CLI/module not detected; using fallback rendering if configured.
     {
       "status": "degraded",
       "database": {
         "connected": true,
         "db_path": "data/state_ledger.db"
       }, ...
     ```
   - Direct execution command: `python3 -m src.cli.ops run --slug two-sum --json`
   - Console Output: 25 lines of structlog info/error entries and Python stack trace prepended to `stdout` before the final JSON payload `{ "success": false, ... }`.

3. **Code Inspection - Logging & CLI Handling (`src/cli/ops.py` lines 440-445)**:
   ```python
   if getattr(parsed_args, "json", False):
       import logging
       logging.getLogger().setLevel(logging.WARNING)
       for h in logging.getLogger().handlers:
           h.setLevel(logging.WARNING)
   ```
   - Standard logging handler level changes do NOT prevent `structlog` from writing colored/formatted log events to `sys.stdout` when `StateLedger` or `PipelineRunner` instantiate. Furthermore, WARNING level logs (like missing Manim/FFmpeg warnings) are still emitted to `stdout`.

4. **State Checkpointing & Resumption Verification (`src/core/orchestrator/pipeline_runner.py`)**:
   - Simulated node failure in a 3-node sequence using custom `FlakyNode`.
   - Node 1 completed, Node 2 failed. On resumption (`runner.resume_run("slug")`), Node 1 was skipped (`res.skipped_steps == ["node1"]`), Node 2 re-executed, and Node 3 executed to completion.
   - Calling `resume_run` on a completed run skipped all 3 nodes (`skipped_steps == ["node1", "node2", "node3"]`), confirming step idempotency.

5. **CLI Argument & Exit Code Validation**:
   - `python3 -m src.cli.ops run` (missing `--slug`) -> exit code 1.
   - `python3 -m src.cli.ops status` (missing args) -> exit code 1.
   - `python3 -m src.cli.ops resume` (missing args) -> exit code 1.
   - `python3 -m src.cli.ops rollback` (missing `--file`) -> exit code 1.
   - `python3 -m src.cli.ops rollback --file /invalid/path` -> exit code 1.
   - `python3 -m src.cli.ops invalid_subcommand` -> exit code 2.

6. **Runbook Inspection (`PromptBook/Phase14/01_Production_Orchestration.md`)**:
   - Line 593 explicitly documents piping JSON output: `python -m src.cli.ops health --json | jq '.'`.
   - Comprehensive 620-line operational runbook covering system architecture, 6-stage node lifecycle, state ledger interaction, CLI manual, deployment procedures, hardware specs, failure recovery SOPs, emergency SQL queries, and observability.

---

## 2. Logic Chain

1. Observation 1 shows that unit/integration tests in `tests/production/test_pipeline_e2e.py` pass.
2. Observation 4 verifies that `PipelineRunner` and `WorkflowEngine` correctly enforce step idempotency, crash resilience, state ledger checkpointing, and partial resumption.
3. Observation 5 verifies that `ops.py` correctly handles missing required CLI arguments and invalid subcommands, returning proper non-zero exit codes.
4. However, Observation 2 empirically demonstrates that invoking `ops.py` subcommands with `--json` outputs log entries to `sys.stdout` before emitting the JSON text.
5. Unix tool pipelines (like `jq`) expect strictly clean JSON on `stdout`. Piping `ops health --json | jq .` fails with exit code 5 (`jq: parse error: Invalid numeric literal at line 1, column 11`).
6. Observation 3 identifies the root cause in `ops.py`: `structlog` console output is directed to `sys.stdout` instead of `sys.stderr`, and `--json` flag handling fails to redirect structlog output away from `stdout`.
7. Observation 6 confirms that `PromptBook/Phase14/01_Production_Orchestration.md` explicitly mandates `ops health --json | jq '.'` for automated monitoring, which currently fails due to Observation 2.
8. Therefore, while `PipelineRunner` logic is sound and unit tests pass, `src/cli/ops.py` has a critical functional flaw when executing in JSON mode that breaks CLI tool integration and runbook compliance.

---

## 3. Caveats

- **Missing System Binaries**: The test host environment lacks system `ffmpeg` and `manim` binaries, causing `ops.py run` against the full node pipeline to fail at `VideoAssemblyNode`. This is expected in environments without media dependencies, and fallback/mocking logic in pytest suite verified full pipeline mechanics.
- **Multiple Historical Runs for Slug**: In `PipelineRunner.resume_run(slug)`, passing a problem slug always resolves to the most recent run record (`ORDER BY created_at DESC`). If multiple runs exist for a single slug and an older run failed, engineers must pass the exact `--run-id` to target that specific run.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

The core pipeline orchestration engine (`PipelineRunner`), State Ledger integration, and runbook documentation are high quality and well-tested. However, `src/cli/ops.py` contains a critical bug in `--json` subcommand handling:

### Required Modifications for Implementer:
1. **Fix Stdout Log Stream Pollution in `src/cli/ops.py` / `src/core/logger.py`**:
   - Redirect all application/structlog log output from `sys.stdout` to `sys.stderr` when initializing console log handlers in `src/core/logger.py`.
   - Alternatively, when `--json` flag is provided in `ops.py`, disable console logging handlers or redirect them to `sys.stderr` so `sys.stdout` contains ONLY valid, parseable JSON.
2. **Verify JSON Output Purity**:
   - Ensure `python3 -m src.cli.ops health --json | jq .`, `python3 -m src.cli.ops status --slug <slug> --json | jq .`, and `python3 -m src.cli.ops run --slug <slug> --json | jq .` execute with exit code 0 and valid JSON output.

---

## 5. Verification Method

To independently verify this audit and the proposed fix:

1. **Run Pytest Integration Suite**:
   ```bash
   pytest tests/production/test_pipeline_e2e.py
   ```
   Expect: 2 passed.

2. **Verify JSON Output Piping (Bug Reproduction & Verification)**:
   ```bash
   python3 -m src.cli.ops health --json | jq .
   ```
   - Current Behavior (Failure): `jq: parse error: Invalid numeric literal at line 1, column 11` (exit code 5).
   - Expected Fixed Behavior: Formatted JSON object returned with exit code 0.

3. **Run Empirical Stress Harness**:
   ```bash
   python3 /tmp/test_phase14_stress.py
   ```
