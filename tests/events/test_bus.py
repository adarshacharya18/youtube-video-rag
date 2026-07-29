"""
Unit tests for the fault-tolerant in-memory EventBus and event models.
"""

from unittest.mock import MagicMock
import pytest

from src.core.events.bus import (
    BaseEvent,
    EventBus,
    NodeCompleted,
    NodeFailed,
    NodeStarted,
)


def test_event_models_initialization() -> None:
    """Verify event dataclasses assign attributes and default ISO timestamp."""
    start_ev = NodeStarted(run_id="run-1", node_name="ScraperNode", step_id="step-1")
    assert start_ev.run_id == "run-1"
    assert start_ev.node_name == "ScraperNode"
    assert start_ev.step_id == "step-1"
    assert start_ev.timestamp is not None

    comp_ev = NodeCompleted(run_id="run-1", node_name="ScraperNode", step_id="step-1", output={"result": "ok"})
    assert comp_ev.output == {"result": "ok"}

    fail_ev = NodeFailed(
        run_id="run-1",
        node_name="ScraperNode",
        step_id="step-1",
        error_message="Network timeout",
        error_details={"code": 504},
    )
    assert fail_ev.error_message == "Network timeout"
    assert fail_ev.error_details == {"code": 504}


def test_subscribe_and_publish() -> None:
    """Verify listener receives published events of subscribed type."""
    bus = EventBus()
    mock_listener = MagicMock()

    bus.subscribe(NodeStarted, mock_listener)
    event = NodeStarted(run_id="run-100", node_name="RAGNode", step_id="step-10")
    bus.publish(event)

    mock_listener.assert_called_once_with(event)


def test_unsubscribe() -> None:
    """Verify unsubscribed listeners no longer receive events."""
    bus = EventBus()
    mock_listener = MagicMock()

    bus.subscribe(NodeStarted, mock_listener)
    bus.unsubscribe(NodeStarted, mock_listener)

    event = NodeStarted(run_id="run-100", node_name="RAGNode", step_id="step-10")
    bus.publish(event)

    mock_listener.assert_not_called()


def test_inheritance_dispatch() -> None:
    """Verify subscribing to BaseEvent receives subclass events."""
    bus = EventBus()
    mock_listener = MagicMock()

    bus.subscribe(BaseEvent, mock_listener)

    ev1 = NodeStarted(run_id="r1", node_name="N1", step_id="s1")
    ev2 = NodeCompleted(run_id="r1", node_name="N1", step_id="s1", output="done")
    ev3 = NodeFailed(run_id="r1", node_name="N1", step_id="s1", error_message="failed")

    bus.publish(ev1)
    bus.publish(ev2)
    bus.publish(ev3)

    assert mock_listener.call_count == 3


def test_fault_tolerant_exception_suppression() -> None:
    """Verify throwing RuntimeError in a mock listener does not crash publish or prevent other listeners."""
    bus = EventBus()
    good_listener_1 = MagicMock()
    bad_listener = MagicMock(side_effect=RuntimeError("Intentional listener crash!"))
    good_listener_2 = MagicMock()

    bus.subscribe(NodeStarted, good_listener_1)
    bus.subscribe(NodeStarted, bad_listener)
    bus.subscribe(NodeStarted, good_listener_2)

    event = NodeStarted(run_id="run-99", node_name="AudioNode", step_id="step-5")

    # Should not raise exception
    bus.publish(event)

    good_listener_1.assert_called_once_with(event)
    bad_listener.assert_called_once_with(event)
    good_listener_2.assert_called_once_with(event)


def test_subscribe_any_type() -> None:
    """Verify subscribing to typing.Any handles generic subscriptions gracefully."""
    from typing import Any
    bus = EventBus()
    mock_listener = MagicMock()

    bus.subscribe(Any, mock_listener)
    event = NodeStarted(run_id="run-100", node_name="RAGNode", step_id="step-10")
    bus.publish(event)

    mock_listener.assert_called_once_with(event)


def test_clear_subscribers() -> None:
    """Verify clear() removes all subscribers."""
    bus = EventBus()
    mock_listener = MagicMock()

    bus.subscribe(NodeStarted, mock_listener)
    bus.clear()

    event = NodeStarted(run_id="run-100", node_name="RAGNode", step_id="step-10")
    bus.publish(event)

    mock_listener.assert_not_called()

