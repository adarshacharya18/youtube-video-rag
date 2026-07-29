# Adversarial Challenge Report — Milestone M1_2

## Challenge Summary

- **Overall Risk Assessment**: LOW
- **Verdict**: APPROVE
- **Target Components**: `WorkflowEngine` (`src/core/workflow/engine.py`), `Node` (`src/core/workflow/node.py`), and `StateLedger` (`src/core/orchestrator/state_ledger.py`).

---

## Empirical Verification & Check Results

### Check 1: In-Memory State Objects & State-Ledger Isolation
- **Hypothesis**: Nodes cannot pass in-memory state objects to subsequent nodes; communication must occur exclusively via SQLite `StateLedger`.
- **Empirical Harness**: `.agents/challenger_m1_2/test_empirical_challenges.py` (`test_challenge_unserializable_in_memory_object_rejected`, `test_challenge_mutation_isolation_via_state_ledger`, `test_challenge_multi_engine_instance_state_isolation`).
- **Observations & Evidence**:
  1. `Node.execute()` returns a `dict[str, Any]` output payload which `WorkflowEngine` writes to SQLite via `StateLedger.record_step_completion()`.
  2. `StateLedger.record_step_completion()` serializes outputs using `json.dumps(output_payload)`. Returning a non-JSON-serializable in-memory Python object (e.g., `UnserializableStateObject`) immediately raises `TypeError: Object of type UnserializableStateObject is not JSON serializable` at line 267 of `state_ledger.py`. `WorkflowEngine.run()` catches this exception, logs node failure, updates step status to `FAILED`, and returns `EngineResult(success=False, status=StepStatus.FAILED)`.
  3. Nodes retrieve prior outputs using `self.get_step_output(run_id, ledger, step_name)`, which queries SQLite (`SELECT * FROM step_executions...` in `StateLedger.get_completed_steps()`) and deserializes JSON via `json.loads()`. Modifying the dict returned by `get_step_output()` in a downstream node does not affect subsequent nodes or alter the stored SQLite record.
  4. Separate `WorkflowEngine` and `Node` instances can run steps independently without sharing any in-memory references.
- **Result**: **PASS** (In-memory state object passing is strictly prohibited by serialization boundaries and fresh SQLite queries).

---

### Check 2: Idempotency & Clean Skipping of COMPLETED Steps
- **Hypothesis**: If a step is already recorded as `COMPLETED` in SQLite, running `WorkflowEngine.run(run_id)` skips that node execution cleanly and returns output payloads from SQLite.
- **Empirical Harness**: `.agents/challenger_m1_2/test_empirical_challenges.py` (`test_challenge_completed_step_skipped_cleanly`, `test_challenge_crash_resume_idempotency`, `test_challenge_preseeded_sqlite_completed_step`).
- **Observations & Evidence**:
  1. When `WorkflowEngine.run(run_id)` executes, line 131 queries completed steps from SQLite: `completed_steps_map = self.ledger.get_completed_steps(run_id)`.
  2. For any node whose name is present in `completed_steps_map` with `StepStatus.COMPLETED`, `WorkflowEngine` appends the step name to `skipped_steps` and `completed_steps`, sets `outputs[node.name] = completed_steps_map[node.name].output_payload`, and `continue`s loop without calling `node.execute()`.
  3. In empirical tests, re-running a 2-node workflow resulted in zero node re-executions (`execution_count` remained 1 for both nodes), `skipped_steps == ["node_a", "node_b"]`, and exact output payload restoration from SQLite.
  4. In crash-resume tests, Node 1 (`COMPLETED`) was cleanly skipped while Node 2 (`FAILED` on first attempt) was re-executed and completed successfully upon retry.
  5. Pre-seeded `COMPLETED` records inserted directly into SQLite were correctly recognized and skipped by `WorkflowEngine`.
- **Result**: **PASS** (Step idempotency, clean skipping, and payload restoration from SQLite confirmed empirically).

---

### Check 3: Existing Unit Test Suite Execution
- **Command**: `pytest tests/workflow/test_engine.py`
- **Result**: **PASS** (8 passed, 0 failed in 0.23s).

---

## Stress Test Results Table

| Test Scenario | Expected Behavior | Actual Behavior | Pass/Fail |
|---|---|---|---|
| Non-JSON object in Node output | Reject at SQLite serialization boundary, mark run `FAILED` | `TypeError` caught, run marked `FAILED`, process does not crash | PASS |
| Downstream dictionary mutation | No pollution of prior step state in SQLite or future node reads | SQLite payload pristine (`[10, 20]`), downstream reads pristine | PASS |
| Re-run completed pipeline | Skip node `execute()`, restore outputs from SQLite | Node `execute()` count = 0 on re-run, outputs loaded from SQLite | PASS |
| Crash resume on `FAILED` step | Skip `COMPLETED` steps, re-run `FAILED` step | `COMPLETED` steps skipped (`skipped_steps`), `FAILED` step retried | PASS |
| Run `test_engine.py` | 100% test pass rate | 8 passed, 0 failures | PASS |

---

## Conclusion & Verdict

`WorkflowEngine` and `Node` strictly enforce state-ledger-only communication and robust step-level idempotency. No in-memory state objects leak between nodes, and completed steps are cleanly skipped when querying SQLite.

**Final Verdict**: **APPROVE**
