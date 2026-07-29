"""
In-memory Publish/Subscribe Event Bus and Pipeline Lifecycle Event Models.

Provides core event models (BaseEvent, NodeStarted, NodeCompleted, NodeFailed)
and a fault-tolerant EventBus implementation that catches and suppresses
exceptions raised by listeners during event dispatch.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Type

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BaseEvent:
    """Base event model containing an ISO 8601 UTC timestamp."""

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        kw_only=True,
    )


@dataclass
class NodeStarted(BaseEvent):
    """Event emitted when a workflow node execution starts."""

    run_id: str
    node_name: str
    step_id: str


@dataclass
class NodeCompleted(BaseEvent):
    """Event emitted when a workflow node completes successfully."""

    run_id: str
    node_name: str
    step_id: str
    output: Any


@dataclass
class NodeFailed(BaseEvent):
    """Event emitted when a workflow node execution fails."""

    run_id: str
    node_name: str
    step_id: str
    error_message: str
    error_details: Any = None


class EventBus:
    """
    In-memory Publish/Subscribe Event Bus.

    Allows subscribers to register listeners for specific event types. When an event
    is published, all matching registered listeners are invoked. Exceptions raised
    by individual listeners are logged and suppressed so that listener failures
    never crash the publisher or interrupt core pipeline execution.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[Type[Any], List[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: Type[Any], listener: Callable[[Any], None]) -> None:
        """
        Subscribe a listener callable to a specific event type.

        Args:
            event_type: The event class or type to listen for.
            listener: Callable to invoke when a matching event is published.
        """
        if listener not in self._subscribers[event_type]:
            self._subscribers[event_type].append(listener)

    def unsubscribe(self, event_type: Type[Any], listener: Callable[[Any], None]) -> None:
        """
        Unsubscribe a listener callable from an event type.

        Args:
            event_type: The event class or type to unsubscribe from.
            listener: The listener callable to remove.
        """
        if event_type in self._subscribers:
            if listener in self._subscribers[event_type]:
                self._subscribers[event_type].remove(listener)
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]

    def publish(self, event: Any) -> None:
        """
        Publish an event to all subscribed listeners.

        Iterates over listeners registered for the exact event type, its superclasses,
        or wildcards. Any exception raised by a listener is caught, logged via structured
        logging, and suppressed to ensure fault tolerance.

        Args:
            event: The event instance to dispatch.
        """
        listeners_to_call: List[Callable[[Any], None]] = []
        for sub_type, listeners in list(self._subscribers.items()):
            try:
                if isinstance(event, sub_type):
                    listeners_to_call.extend(listeners)
            except TypeError:
                if sub_type == type(event) or sub_type is Any:
                    listeners_to_call.extend(listeners)

        for listener in listeners_to_call:
            try:
                listener(event)
            except Exception as e:
                logger.error(
                    "EventBus listener raised an exception",
                    event_type=type(event).__name__,
                    listener=getattr(listener, "__qualname__", str(listener)),
                    error=str(e),
                    exc_info=True,
                )

    def clear(self) -> None:
        """Clear all registered event subscribers."""
        self._subscribers.clear()
