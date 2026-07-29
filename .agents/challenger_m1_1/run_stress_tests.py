"""
Empirical Stress Test Script for WorkflowEngine and Node exception handling.
"""

import sqlite3
from typing import Any
from src.core.exceptions import PipelineStageError, PipelineError
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow import Node, WorkflowEngine, EngineResult

class MockSuccessNode(Node):
    def __init__(self, step_name: str = "success_node"):
        self._name = step_name
        self.executed = False
    
    @property
    def name(self) -> str:
        return self._name
    
    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        self.executed = True
        return {"status": "ok", "step": self.name}


class ExceptionRaisingNode(Node):
    def __init__(self, step_name: str, exception_to_raise: Exception):
        self._name = step_name
        self.exception_to_raise = exception_to_raise
        self.executed = False

    @property
    def name(self) -> str:
        return self._name

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        self.executed = True
        raise self.exception_to_raise


def run_tests():
    print("=== Starting Empirical Stress Testing of WorkflowEngine ===")
    
    exceptions_to_test = [
        ("KeyError", KeyError("missing_key")),
        ("ZeroDivisionError", ZeroDivisionError("division by zero")),
        ("AttributeError", AttributeError("'NoneType' object has no attribute 'foo'")),
        ("PipelineStageError", PipelineStageError("Required step output missing")),
        ("TypeError", TypeError("unsupported operand type(s)")),
        ("ValueError", ValueError("invalid literal")),
        ("IndexError", IndexError("list index out of range")),
        ("MemoryError", MemoryError("out of memory")),
    ]
    
    results = {}
    
    for exc_name, exc_inst in exceptions_to_test:
        ledger = StateLedger(":memory:")
        run_id = ledger.create_run(f"test-run-{exc_name.lower()}")
        
        node1 = MockSuccessNode("step_1")
        failing_node = ExceptionRaisingNode("step_2_failing", exc_inst)
        node3 = MockSuccessNode("step_3_should_not_run")
        
        engine = WorkflowEngine([node1, failing_node, node3], ledger)
        
        try:
            res = engine.run(run_id)
            
            # Assertions on EngineResult
            assert res.success is False, f"Expected success=False for {exc_name}"
            assert res.status == StepStatus.FAILED, f"Expected status FAILED for {exc_name}"
            assert res.failed_step == "step_2_failing", f"Expected failed_step 'step_2_failing' for {exc_name}"
            assert str(exc_inst) in str(res.error), f"Error message mismatch for {exc_name}"
            assert res.completed_steps == ["step_1"], f"Completed steps mismatch for {exc_name}: {res.completed_steps}"
            assert node3.name not in res.completed_steps, f"Step 3 executed despite failure for {exc_name}"
            assert node3.executed is False, f"Step 3 node execute method called despite failure for {exc_name}"

            # Check StateLedger DB for run record and step execution record
            run_rec = ledger.get_run(run_id)
            assert run_rec is not None, f"Run record missing for {exc_name}"
            assert run_rec.status == StepStatus.FAILED, f"Ledger run status not FAILED for {exc_name}: {run_rec.status}"
            
            # Query step execution from DB
            cursor = ledger._conn.cursor()
            cursor.execute(
                "SELECT status, error_message, error_details FROM step_executions WHERE pipeline_run_id = ? AND step_name = ?",
                (run_id, "step_2_failing")
            )
            step2_row = cursor.fetchone()
            assert step2_row is not None, f"Step 2 record missing in ledger DB for {exc_name}"
            
            step2_status, step2_err_msg, step2_err_details_json = step2_row
            assert step2_status == StepStatus.FAILED.value, f"Step 2 status in DB not FAILED for {exc_name}: {step2_status}"
            assert step2_err_msg == str(exc_inst), f"Step 2 error msg mismatch in DB for {exc_name}"
            assert exc_name in step2_err_details_json, f"Step 2 error details missing exception name in DB for {exc_name}"
            
            print(f"[PASS] {exc_name}: engine caught exception, halted pipeline, recorded FAILED in StateLedger.")
            results[exc_name] = "PASS"
        except Exception as test_err:
            print(f"[FAIL] {exc_name}: {test_err}")
            results[exc_name] = f"FAIL: {test_err}"
            
    print("\n=== Additional Boundary Test 1: Node returning None ===")
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("test-none-output")
    
    class NoneOutputNode(Node):
        @property
        def name(self) -> str:
            return "none_node"
        def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
            return None  # type: ignore
            
    engine = WorkflowEngine([NoneOutputNode()], ledger)
    res = engine.run(run_id)
    assert res.success is True
    assert res.outputs["none_node"] == {}
    print("[PASS] None output handled gracefully converting to empty dict.")

    print("\n=== Additional Boundary Test 2: Idempotency with Prior Failure ===")
    # When a run failed previously on step_2, running engine again should re-attempt step_2 (since step_2 was NOT completed)
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("resume-failed-run")
    
    # First execution fails at step_2
    fail_node = ExceptionRaisingNode("step_2", KeyError("initial failure"))
    engine1 = WorkflowEngine([MockSuccessNode("step_1"), fail_node], ledger)
    res1 = engine1.run(run_id)
    assert res1.success is False
    
    # Second execution replaces step_2 with successful node
    engine2 = WorkflowEngine([MockSuccessNode("step_1"), MockSuccessNode("step_2")], ledger)
    res2 = engine2.run(run_id)
    assert res2.success is True
    assert res2.skipped_steps == ["step_1"]
    assert res2.completed_steps == ["step_1", "step_2"]
    print("[PASS] Resuming failed pipeline correctly skips completed step_1 and re-runs step_2 to completion.")

    print("\n=== Summary ===")
    all_passed = all(val == "PASS" for val in results.values())
    print(f"All stress tests passed: {all_passed}")

if __name__ == "__main__":
    run_tests()
