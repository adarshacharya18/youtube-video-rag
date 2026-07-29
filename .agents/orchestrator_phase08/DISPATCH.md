## 2026-07-29T17:25:06Z

Implement Phase 08: The Workflow Engine for the Automated DSA Educational YouTube Video Pipeline. Build a robust, fault-tolerant execution engine that runs a sequence of "Nodes" (Ingest, Plan, Script, Render), strictly logging their success or failure to the SQLite State Ledger.

Working directory: /home/adarsh/Documents/Youtube-Channel
Integrity mode: development

## Requirements

### R1. Strict Node Abstraction & Idempotency
Create `src/core/workflow/node.py` defining an abstract `Node` class. Nodes must strictly communicate by reading from and writing to the SQLite State Ledger using a `run_id`, maintaining true pipeline idempotency (no passing in-memory state objects down the chain).

### R2. Fault-Tolerant Engine
Implement `src/core/workflow/engine.py` to execute the sequence of nodes. The engine must wrap every node execution in a robust try/except block that gracefully captures exceptions and guarantees the SQLite ledger is updated to `FAILED` if a node crashes.

### R3. Architectural Documentation
Document the engine mechanics, node lifecycle, and sequence diagrams in `PromptBook/Phase08/01_Workflow_Engine.md`.

### R4. Subagent Execution Rules
Do not ask for permission before running terminal commands, unless the command involves handling sensitive data.

## Acceptance Criteria

### Verification & Testing
- [ ] Running `pytest tests/workflow/test_engine.py` executes successfully. The test suite MUST use mock nodes that intentionally throw exceptions, explicitly verifying that the engine catches them, prevents application crash, and correctly updates the mock SQLite ledger to `FAILED`.
- [ ] `src/core/workflow/engine.py` and `node.py` exist and strictly enforce state-ledger-only data passing.

### Documentation
- [ ] `PromptBook/Phase08/01_Workflow_Engine.md` exists and contains high-quality Mermaid sequence diagrams detailing the fault-tolerant execution flow.
