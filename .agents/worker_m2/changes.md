# Changes Summary - Milestone 2 (Workflow Engine Integration)

## Files Modified
- `src/core/workflow/engine.py`

## Detailed Changes

### 1. Imports
Imported `EventBus`, `NodeStarted`, `NodeCompleted`, and `NodeFailed` from `src.core.events`:
```python
from src.core.events import EventBus, NodeCompleted, NodeFailed, NodeStarted
```

### 2. `WorkflowEngine.__init__` Update
Updated constructor parameter list to accept optional `event_bus`:
```python
def __init__(
    self,
    nodes: Sequence[Node],
    ledger: Optional[StateLedger] = None,
    event_bus: Optional[EventBus] = None,
) -> None:
    ...
    self.event_bus: Optional[EventBus] = event_bus
```

### 3. Lifecycle Event Emission in `WorkflowEngine.run`
- **`NodeStarted`**: Emitted immediately after recording step execution start in `StateLedger`:
  ```python
  step_id = self.ledger.record_step_start(run_id, node.name)
  if self.event_bus is not None:
      self.event_bus.publish(
          NodeStarted(run_id=run_id, node_name=node.name, step_id=step_id)
      )
  ```
- **`NodeCompleted`**: Emitted immediately after recording step completion in `StateLedger`:
  ```python
  self.ledger.record_step_completion(step_id, node_output)
  if self.event_bus is not None:
      self.event_bus.publish(
          NodeCompleted(
              run_id=run_id,
              node_name=node.name,
              step_id=step_id,
              output=node_output,
          )
      )
  ```
- **`NodeFailed`**: Emitted inside the exception handler immediately after recording step failure in `StateLedger`:
  ```python
  self.ledger.record_step_failure(
      step_id,
      error_message=error_msg,
      error_details=error_details,
  )
  if self.event_bus is not None:
      self.event_bus.publish(
          NodeFailed(
              run_id=run_id,
              node_name=node.name,
              step_id=step_id,
              error_message=error_msg,
              error_details=error_details,
          )
      )
  ```

## Verification
- Executed `pytest tests/workflow/test_engine.py`: 8 passed in 0.25s.
