# Project: Phase 10 — Event Bus Integration

## Architecture
- Package: `src/core/events/bus.py`
  - In-memory Pub/Sub `EventBus` class.
  - Event dataclasses: `NodeStarted`, `NodeCompleted`, `NodeFailed`.
  - Methods: `subscribe(event_type, listener)`, `unsubscribe(event_type, listener)`, `publish(event)`.
  - Fault tolerance: `publish` iterates over registered listeners for the event type (and base event types if applicable) in a `try...except Exception:` block, logging/suppressing listener exceptions so callers never crash.
- Package: `src/core/workflow/engine.py`
  - Accept `event_bus: Optional[EventBus] = None` in `WorkflowEngine.__init__`.
  - Publish `NodeStarted(run_id, node_name, step_id, timestamp)` after `record_step_start`.
  - Publish `NodeCompleted(run_id, node_name, step_id, output, timestamp)` after `record_step_completion`.
  - Publish `NodeFailed(run_id, node_name, step_id, error_msg, error_details, timestamp)` after `record_step_failure`.
- Documentation: `PromptBook/Phase10/01_Event_Bus.md`
  - Architectural overview, Pub/Sub pattern, event dataclasses, fault-tolerance design, code examples.
- Test Suite:
  - `tests/events/test_bus.py`: Unit tests for EventBus (subscribe, publish, unsubscribe, exception suppression on RuntimeError).
  - `tests/workflow/test_engine.py`: Updated workflow engine tests verifying event emission during pipeline execution.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | EventBus & Event Models | `src/core/events/bus.py` with Pub/Sub and exception suppression | M1 | ORIGINAL_REQUEST R1 |
| 2 | Workflow Engine Integration | Emit `NodeStarted`, `NodeCompleted`, `NodeFailed` in `WorkflowEngine` | M2 | ORIGINAL_REQUEST R2 |
| 3 | SDK Documentation | `PromptBook/Phase10/01_Event_Bus.md` covering architecture & guidelines | M3 | ORIGINAL_REQUEST R3 |
| 4 | Verification Test Suite | `tests/events/test_bus.py` and `tests/workflow/test_engine.py` | M4 | ORIGINAL_REQUEST Acceptance Criteria |

## Code Layout
- `src/core/events/__init__.py`
- `src/core/events/bus.py`
- `src/core/workflow/engine.py`
- `PromptBook/Phase10/01_Event_Bus.md`
- `tests/events/__init__.py`
- `tests/events/test_bus.py`
- `tests/workflow/test_engine.py`

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Event Bus Implementation | Create `src/core/events/bus.py` with EventBus and event models | none | PLANNED |
| M2 | Workflow Engine Integration | Update `src/core/workflow/engine.py` to publish events | M1 | PLANNED |
| M3 | SDK Documentation | Create `PromptBook/Phase10/01_Event_Bus.md` | M1 | PLANNED |
| M4 | Unit & Integration Testing | Create `tests/events/test_bus.py` and update `tests/workflow/test_engine.py` | M1, M2 | PLANNED |

## Interface Contracts
### `src/core/events/bus.py`
```python
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Type
from datetime import datetime, timezone

@dataclass
class BaseEvent:
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class NodeStarted(BaseEvent):
    run_id: str
    node_name: str
    step_id: str

@dataclass
class NodeCompleted(BaseEvent):
    run_id: str
    node_name: str
    step_id: str
    output: Any

@dataclass
class NodeFailed(BaseEvent):
    run_id: str
    node_name: str
    step_id: str
    error_message: str
    error_details: Any = None

class EventBus:
    def __init__(self) -> None: ...
    def subscribe(self, event_type: Type, listener: Callable[[Any], None]) -> None: ...
    def unsubscribe(self, event_type: Type, listener: Callable[[Any], None]) -> None: ...
    def publish(self, event: Any) -> None: ... # MUST catch Exception and suppress
```

### `src/core/workflow/engine.py`
```python
class WorkflowEngine:
    def __init__(
        self,
        nodes: Sequence[Node],
        ledger: Optional[StateLedger] = None,
        event_bus: Optional[EventBus] = None
    ) -> None: ...
```
