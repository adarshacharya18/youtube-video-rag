# Changes Report — Milestone 1 (Event Bus Implementation)

## Overview
Implemented the in-memory Publish/Subscribe `EventBus` and core workflow lifecycle event models (`BaseEvent`, `NodeStarted`, `NodeCompleted`, `NodeFailed`) for Phase 10: Event Bus Integration.

## Files Created / Modified

### 1. `src/core/events/bus.py` (Created)
- **`BaseEvent`**: `@dataclass` base event with ISO 8601 UTC timestamp generator (`datetime.now(timezone.utc).isoformat()`, configured with `kw_only=True` to support dataclass inheritance cleanly).
- **`NodeStarted`**: `@dataclass` event with `run_id`, `node_name`, `step_id`.
- **`NodeCompleted`**: `@dataclass` event with `run_id`, `node_name`, `step_id`, `output`.
- **`NodeFailed`**: `@dataclass` event with `run_id`, `node_name`, `step_id`, `error_message`, `error_details`.
- **`EventBus`**:
  - `subscribe(event_type, listener)`: Registers listener for `event_type`, avoiding duplicate registrations.
  - `unsubscribe(event_type, listener)`: Removes subscriber for `event_type`.
  - `publish(event)`: Dispatches `event` to listeners registered for `type(event)` and parent classes. Each listener invocation is wrapped in `try...except Exception:`, logging errors via structured `structlog` logger (`logger.error(...)`) and suppressing exceptions so calling workflow/code never halts.
  - `clear()`: Empties registered subscribers.

### 2. `src/core/events/__init__.py` (Created)
- Package init file exporting `EventBus`, `BaseEvent`, `NodeStarted`, `NodeCompleted`, `NodeFailed`.

### 3. `tests/events/__init__.py` & `tests/events/test_bus.py` (Created)
- Full unit test suite for `EventBus` covering initialization, subscribe/publish, unsubscribe, sub-type/inheritance dispatching, `Any` generic handling, subscriber clearance, and fault-tolerant listener exception suppression.

## Design Rationale
- **Dataclass Inheritance (`kw_only=True`)**: In Python dataclasses, defining a default field in a base class (`timestamp`) can trigger `TypeError: non-default argument follows default argument` in subclasses. Setting `kw_only=True` on `timestamp` allows positional argument initialization for subclass fields (`run_id`, `node_name`, `step_id`) while preserving default timestamp creation.
- **Fault Tolerance**: `EventBus.publish()` catches all `Exception` instances per listener. A crashing listener cannot prevent other listeners from running or crash the workflow caller.
- **Sub-type Matching**: `isinstance(event, sub_type)` allows registering listeners for `BaseEvent` or specific subclasses (`NodeStarted`), providing flexible event routing.

## Verification
- **Unit Test Command**: `pytest tests/events/test_bus.py`
- **Result**: 7 passed, 100% test coverage on `src/core/events/bus.py` and `src/core/events/__init__.py`.
- **Core & Workflow Suite**: `pytest tests/core tests/workflow` (33 passed).
