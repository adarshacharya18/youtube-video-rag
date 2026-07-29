# Original User Request

## 2026-07-29T12:21:48Z

Implement Phase 10: Event Bus Integration for the Automated DSA Educational YouTube Video Pipeline. Build an in-memory Event Bus to dispatch real-time pipeline events (`NodeStarted`, `NodeCompleted`, `NodeFailed`) to subscribed listeners without blocking or crashing the core synchronous Workflow Engine.

Working directory: /home/adarsh/Documents/Youtube-Channel
Integrity mode: development

## Requirements

### R1. Fault-Tolerant Event Bus
Create `src/core/events/bus.py` defining an in-memory `EventBus` class using a Publish/Subscribe pattern. The bus MUST catch and suppress any exceptions raised by a listener during dispatch to ensure that a crashing listener never halts the main pipeline execution. 

### R2. Workflow Engine Integration
Update the Workflow Engine (`src/core/workflow/engine.py`) to emit lifecycle events (`NodeStarted`, `NodeCompleted`, `NodeFailed`) to the Event Bus during pipeline execution.

### R3. SDK Documentation
Document the event models, the publish/subscribe architecture, and fault-tolerance guidelines in `PromptBook/Phase10/01_Event_Bus.md`.

### R4. Subagent Execution Rules
Do not ask for permission before running terminal commands, unless the command involves handling sensitive data.

## Acceptance Criteria

### Verification & Testing
- [ ] Running `pytest tests/events/test_bus.py` executes successfully. The test suite MUST use mock listeners to verify that events are correctly dispatched, and explicitly verify that injecting an intentional `RuntimeError` into a mock listener does not crash the `EventBus.publish()` method or the calling `WorkflowEngine`.
- [ ] The `WorkflowEngine` tests (`tests/workflow/test_engine.py`) are updated and passing, proving that integrating the Event Bus did not break existing fault tolerance logic.

### Documentation
- [ ] `PromptBook/Phase10/01_Event_Bus.md` exists and clearly documents the fault-tolerant in-memory Publisher/Subscriber architecture.

## 2026-07-29T17:04:46Z

Implement Phase 11: Script & Narration Generation for the Automated DSA Educational YouTube Video Pipeline. Build a Workflow Engine Node that utilizes the LLM Prompt Library to convert a raw DSA problem into a timed, highly engaging YouTube script, outputting perfectly structured JSON containing spoken narration and visual cues.

Working directory: /home/adarsh/Documents/Youtube-Channel
Integrity mode: development

## Requirements

### R1. Script Generator Node
Create `src/pipeline/nodes/script_generator_node.py` inheriting from the core `Node` class. The node must use the LLM Abstraction and Prompt Library to generate the script based on YouTube engagement metrics (Hook, Context, Solution, Complexity).

### R2. Error-Feedback Retry Loop
The node must enforce that the LLM output conforms strictly to a predefined Pydantic schema for the script. If the LLM returns invalid JSON or violates the schema, the node must aggressively retry the generation by catching the `ValidationError` or `JSONDecodeError` and feeding the exact error string back to the LLM so it can correct its mistake.

### R3. Script Generation Documentation
Document the scripting structure logic, the error-feedback retry mechanism, and the JSON schema in `PromptBook/Phase11/01_Script_Generation.md`.

### R4. Subagent Execution Rules
Do not ask for permission before running terminal commands, unless the command involves handling sensitive data.

## Acceptance Criteria

### Verification & Testing
- [ ] Running `pytest tests/pipeline/test_script_node.py` executes successfully. The test suite MUST mock the LLM to intentionally return a corrupted JSON string on the first call, and a valid JSON string on the second call, explicitly verifying that the node correctly feeds the error back and successfully recovers via the retry loop.
- [ ] The `script_generator_node.py` exists and correctly implements the Pydantic schema validation and the error-feedback retry logic.

### Documentation
- [ ] `PromptBook/Phase11/01_Script_Generation.md` exists and clearly documents the script JSON schema and the intelligent retry architecture.

