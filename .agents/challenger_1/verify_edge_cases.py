"""
Empirical verification script for EventBus and WorkflowEngine edge cases.
"""

import sys
from typing import Any, List
from unittest.mock import MagicMock

from src.core.events.bus import (
    BaseEvent,
    EventBus,
    NodeCompleted,
    NodeFailed,
    NodeStarted,
)
from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.engine import WorkflowEngine
from src.core.workflow.node import Node


class CustomException(Exception):
    """Custom exception type for edge case testing."""
    pass


class DummyNode(Node):
    @property
    def name(self) -> str:
        return "dummy_node"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        return {"status": "ok"}


def test_multiple_subscribers_differing_exceptions():
    print("--- Test 1: Multiple subscribers failing with different exception types ---")
    bus = EventBus()
    execution_order: List[str] = []

    def fail_runtime(event):
        execution_order.append("runtime")
        raise RuntimeError("Runtime fail")

    def fail_value(event):
        execution_order.append("value")
        raise ValueError("Value fail")

    def fail_custom(event):
        execution_order.append("custom")
        raise CustomException("Custom fail")

    def succeed(event):
        execution_order.append("succeed")

    bus.subscribe(NodeStarted, fail_runtime)
    bus.subscribe(NodeStarted, fail_value)
    bus.subscribe(NodeStarted, fail_custom)
    bus.subscribe(NodeStarted, succeed)

    event = NodeStarted(run_id="run-1", node_name="node-1", step_id="step-1")
    
    # Should not raise exception
    try:
        bus.publish(event)
        print("SUCCESS: EventBus.publish() completed without raising exceptions.")
    except Exception as e:
        print(f"FAILED: EventBus.publish() raised {type(e).__name__}: {e}")
        assert False

    assert execution_order == ["runtime", "value", "custom", "succeed"], f"Unexpected execution order: {execution_order}"
    print("SUCCESS: All 4 listeners (3 failing, 1 succeeding) were executed in order.\n")


def test_unsubscribe_during_event_delivery():
    print("--- Test 2: Unsubscribe called during event delivery ---")
    bus = EventBus()
    calls: List[str] = []

    def listener_self_unsub(event):
        calls.append("listener_self_unsub")
        bus.unsubscribe(NodeStarted, listener_self_unsub)

    def listener_unsub_other(event):
        calls.append("listener_unsub_other")
        bus.unsubscribe(NodeStarted, listener_target)

    def listener_target(event):
        calls.append("listener_target")

    bus.subscribe(NodeStarted, listener_self_unsub)
    bus.subscribe(NodeStarted, listener_unsub_other)
    bus.subscribe(NodeStarted, listener_target)

    event = NodeStarted(run_id="run-1", node_name="node-1", step_id="step-1")

    # First publish: snapshot captured all 3 listeners before calls start
    print("Publishing event #1...")
    try:
        bus.publish(event)
        print("SUCCESS: Publish #1 finished without RuntimeError (e.g. dictionary changed during iteration).")
    except Exception as e:
        print(f"FAILED: Publish #1 raised {type(e).__name__}: {e}")
        assert False

    print(f"Calls during event #1: {calls}")
    assert calls == ["listener_self_unsub", "listener_unsub_other", "listener_target"]

    # Second publish: listener_self_unsub and listener_target should be unsubscribed
    calls.clear()
    print("Publishing event #2...")
    bus.publish(event)
    print(f"Calls during event #2: {calls}")
    assert calls == ["listener_unsub_other"]
    print("SUCCESS: Subsequent publish respected unsubscribes made during delivery.\n")


def test_unhandled_and_base_events():
    print("--- Test 3: Unhandled or base event types ---")
    bus = EventBus()
    mock_base_listener = MagicMock()
    mock_started_listener = MagicMock()

    bus.subscribe(BaseEvent, mock_base_listener)
    bus.subscribe(NodeStarted, mock_started_listener)

    # Subtest 3a: Publishing unhandled event (no direct or indirect listeners)
    class CustomUnregisteredEvent:
        pass

    print("Publishing unhandled event CustomUnregisteredEvent()...")
    bus.publish(CustomUnregisteredEvent())
    mock_base_listener.assert_not_called()
    mock_started_listener.assert_not_called()
    print("SUCCESS: Unhandled event safely ignored.")

    # Subtest 3b: Publishing BaseEvent directly
    print("Publishing BaseEvent()...")
    base_ev = BaseEvent()
    bus.publish(base_ev)
    mock_base_listener.assert_called_once_with(base_ev)
    mock_started_listener.assert_not_called()
    print("SUCCESS: BaseEvent delivered to BaseEvent listener, ignored by NodeStarted listener.")

    # Subtest 3c: Publishing derived NodeStarted event
    mock_base_listener.reset_mock()
    mock_started_listener.reset_mock()
    print("Publishing NodeStarted()...")
    started_ev = NodeStarted(run_id="r", node_name="n", step_id="s")
    bus.publish(started_ev)
    mock_base_listener.assert_called_once_with(started_ev)
    mock_started_listener.assert_called_once_with(started_ev)
    print("SUCCESS: Derived event delivered to both BaseEvent subscriber (superclass matching) and NodeStarted subscriber.\n")


def test_workflow_engine_fault_tolerance_with_multiple_failing_listeners():
    print("--- Test 4: WorkflowEngine fault tolerance with multiple failing listeners ---")
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("test-wf-run")

    bus = EventBus()
    def fail_1(e): raise RuntimeError("Fail 1")
    def fail_2(e): raise ValueError("Fail 2")
    def fail_3(e): raise CustomException("Fail 3")

    bus.subscribe(NodeStarted, fail_1)
    bus.subscribe(NodeStarted, fail_2)
    bus.subscribe(NodeCompleted, fail_3)

    engine = WorkflowEngine([DummyNode()], ledger=ledger, event_bus=bus)
    result = engine.run(run_id)

    assert result.success is True
    assert result.completed_steps == ["dummy_node"]
    print("SUCCESS: WorkflowEngine completed successfully despite 3 crashing listeners with 3 different exception types.\n")


if __name__ == "__main__":
    test_multiple_subscribers_differing_exceptions()
    test_unsubscribe_during_event_delivery()
    test_unhandled_and_base_events()
    test_workflow_engine_fault_tolerance_with_multiple_failing_listeners()
    print("=== ALL EMPIRICAL VERIFICATION TESTS PASSED SUCCESSFULLY ===")
