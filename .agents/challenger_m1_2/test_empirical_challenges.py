"""
Empirical Challenge Test Suite for WorkflowEngine & Node Abstraction.

Tests:
1. Verification that nodes cannot pass in-memory state objects to subsequent nodes.
   - Serialization boundary enforcing JSON-only payloads (custom objects raise TypeError -> caught as FAILED run).
   - Fresh deserialization from SQLite preventing in-memory object reference sharing and mutation leakage.
   - Node instance isolation across separate WorkflowEngine executions.
2. Verification that completed steps in SQLite are cleanly skipped.
   - Clean skipping of COMPLETED steps with mock execution counter asserting zero re-executions.
   - Output payload retrieval directly from SQLite for skipped steps.
   - Crash-resume capability (skipping COMPLETED steps, re-running FAILED/unrun steps).
   - Pre-seeded SQLite COMPLETED step handling.
"""

from typing import Any
import pytest

from src.core.exceptions import PipelineStageError
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow.engine import WorkflowEngine
from src.core.workflow.node import Node


# Custom non-JSON-serializable class to challenge in-memory object passing
class UnserializableStateObject:
    def __init__(self, data: str):
        self.data = data


class NodeA_ReturnsCustomObject(Node):
    @property
    def name(self) -> str:
        return "node_a"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        # Tries to return an in-memory object instance
        return {"custom_obj": UnserializableStateObject("secret_state")}


class NodeA_Standard(Node):
    def __init__(self):
        self.execution_count = 0

    @property
    def name(self) -> str:
        return "node_a"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        self.execution_count += 1
        return {"payload_key": "node_a_value", "numbers": [10, 20]}


class NodeB_Mutator(Node):
    def __init__(self):
        self.execution_count = 0

    @property
    def name(self) -> str:
        return "node_b"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        self.execution_count += 1
        node_a_output = self.get_step_output(run_id, ledger, "node_a")
        # Attempt in-memory mutation on the retrieved output dict
        node_a_output["numbers"].append(999)
        node_a_output["mutated"] = True
        return {"b_received": node_a_output["payload_key"]}


class NodeC_Reader(Node):
    def __init__(self):
        self.execution_count = 0

    @property
    def name(self) -> str:
        return "node_c"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        self.execution_count += 1
        node_a_output = self.get_step_output(run_id, ledger, "node_a")
        return {"node_a_numbers": node_a_output["numbers"]}


class FlakyNode(Node):
    def __init__(self, fail_first_time: bool = True):
        self.fail_first_time = fail_first_time
        self.execution_count = 0

    @property
    def name(self) -> str:
        return "flaky_node"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        self.execution_count += 1
        if self.fail_first_time and self.execution_count == 1:
            raise RuntimeError("Transient node failure")
        return {"status": "flaky_recovered"}


# ---------------------------------------------------------------------------
# Check 1: Empirical Challenges for State Passing & In-Memory Isolation
# ---------------------------------------------------------------------------


def test_challenge_unserializable_in_memory_object_rejected():
    """
    Verify that nodes cannot pass in-memory state objects.

    Attempts to return a non-JSON serializable object fail at the StateLedger
    boundary, causing WorkflowEngine to capture the TypeError and record FAILED status.
    """
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("object-pass-test")

    engine = WorkflowEngine([NodeA_ReturnsCustomObject(), NodeB_Mutator()], ledger)
    result = engine.run(run_id)

    assert result.success is False
    assert result.status == StepStatus.FAILED
    assert result.failed_step == "node_a"
    assert "Object of type UnserializableStateObject is not JSON serializable" in str(result.error)


def test_challenge_mutation_isolation_via_state_ledger():
    """
    Verify that reading step output returns fresh deserialized data from SQLite,
    preventing in-memory reference sharing or mutation side-effects between nodes.
    """
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("mutation-isolation-test")

    node_a = NodeA_Standard()
    node_b = NodeB_Mutator()
    node_c = NodeC_Reader()

    engine = WorkflowEngine([node_a, node_b, node_c], ledger)
    result = engine.run(run_id)

    assert result.success is True
    # Verify Node C retrieved pristine numbers [10, 20], unmodified by Node B's in-memory mutation
    assert result.outputs["node_c"]["node_a_numbers"] == [10, 20]

    # Verify directly from StateLedger that node_a payload in SQLite remains pristine
    completed = ledger.get_completed_steps(run_id)
    assert completed["node_a"].output_payload == {"payload_key": "node_a_value", "numbers": [10, 20]}


def test_challenge_multi_engine_instance_state_isolation():
    """
    Verify that subsequent steps run in completely separate engine/node instances
    can successfully read prior step state purely from SQLite.
    """
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("multi-engine-test")

    # Engine 1 executes Node A only
    node_a = NodeA_Standard()
    engine1 = WorkflowEngine([node_a], ledger)
    res1 = engine1.run(run_id)
    assert res1.success is True
    assert res1.completed_steps == ["node_a"]

    # Engine 2 executes Node A and Node B with brand new Node instances
    node_a_new = NodeA_Standard()
    node_b_new = NodeB_Mutator()
    engine2 = WorkflowEngine([node_a_new, node_b_new], ledger)
    res2 = engine2.run(run_id)

    assert res2.success is True
    assert res2.skipped_steps == ["node_a"]
    assert res2.completed_steps == ["node_a", "node_b"]
    assert node_a_new.execution_count == 0  # Skipped, never executed!
    assert node_b_new.execution_count == 1  # Executed, read state from SQLite!
    assert res2.outputs["node_b"]["b_received"] == "node_a_value"


# ---------------------------------------------------------------------------
# Check 2: Empirical Challenges for Idempotency & Clean Skipping of COMPLETED
# ---------------------------------------------------------------------------


def test_challenge_completed_step_skipped_cleanly():
    """
    Verify that running WorkflowEngine.run(run_id) on a run with already COMPLETED steps
    skips execution cleanly (execution_count == 0) and returns payload from SQLite.
    """
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("clean-skip-test")

    node_a = NodeA_Standard()
    node_b = NodeB_Mutator()

    engine = WorkflowEngine([node_a, node_b], ledger)

    # Initial Run
    res1 = engine.run(run_id)
    assert res1.success is True
    assert node_a.execution_count == 1
    assert node_b.execution_count == 1

    # Second Run (Re-run)
    res2 = engine.run(run_id)
    assert res2.success is True
    assert res2.skipped_steps == ["node_a", "node_b"]
    # Node execute methods were NOT called again!
    assert node_a.execution_count == 1
    assert node_b.execution_count == 1
    # Payloads returned in outputs match SQLite records exactly
    assert res2.outputs["node_a"] == {"payload_key": "node_a_value", "numbers": [10, 20]}
    assert res2.outputs["node_b"] == {"b_received": "node_a_value"}


def test_challenge_crash_resume_idempotency():
    """
    Verify crash recovery: completed steps before a failure are skipped on resume,
    while the failed step and subsequent steps execute.
    """
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("crash-resume-test")

    node_a = NodeA_Standard()
    flaky_node = FlakyNode(fail_first_time=True)
    node_c = NodeC_Reader()

    engine = WorkflowEngine([node_a, flaky_node, node_c], ledger)

    # Attempt 1: Node A succeeds, FlakyNode fails, Node C not reached
    res1 = engine.run(run_id)
    assert res1.success is False
    assert res1.failed_step == "flaky_node"
    assert res1.completed_steps == ["node_a"]
    assert node_a.execution_count == 1
    assert flaky_node.execution_count == 1
    assert node_c.execution_count == 0

    # Attempt 2: Resume. Node A is COMPLETED (skipped). FlakyNode retries and succeeds. Node C executes.
    res2 = engine.run(run_id)
    assert res2.success is True
    assert res2.skipped_steps == ["node_a"]
    assert res2.completed_steps == ["node_a", "flaky_node", "node_c"]
    assert node_a.execution_count == 1  # Skipped!
    assert flaky_node.execution_count == 2  # Re-executed!
    assert node_c.execution_count == 1  # Executed!


def test_challenge_preseeded_sqlite_completed_step():
    """
    Verify that if SQLite state ledger contains a pre-existing COMPLETED step record,
    WorkflowEngine respects it, skips the node, and returns the pre-existing payload.
    """
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("preseeded-test")

    # Manually seed a completed step in StateLedger
    step_id = ledger.record_step_start(run_id, "node_a")
    ledger.record_step_completion(step_id, {"payload_key": "preseeded_val", "numbers": [100]})

    node_a = NodeA_Standard()
    node_c = NodeC_Reader()

    engine = WorkflowEngine([node_a, node_c], ledger)
    result = engine.run(run_id)

    assert result.success is True
    assert result.skipped_steps == ["node_a"]
    assert node_a.execution_count == 0  # Node A was skipped!
    assert result.outputs["node_a"]["payload_key"] == "preseeded_val"
    assert result.outputs["node_c"]["node_a_numbers"] == [100]
