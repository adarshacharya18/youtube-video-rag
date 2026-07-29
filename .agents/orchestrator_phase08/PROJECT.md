# Project: Phase 08 — The Workflow Engine

## Architecture
Phase 08 implements the synchronous, fault-tolerant execution engine for the Automated DSA Educational YouTube Video Pipeline. It coordinates sequential execution of pipeline nodes (Ingest, Plan, Script, Render). Each Node strictly reads prior inputs from and writes outputs to the SQLite State Ledger (`src/core/orchestrator/state_ledger.py`), enforcing true pipeline idempotency without passing in-memory state objects. `WorkflowEngine` wraps each node invocation in try/except blocks to gracefully capture exceptions, update SQLite step and run records to `FAILED`, and prevent process crashes.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Strict Node Abstraction | Abstract `Node` base class enforcing `run_id` state ledger communication | M1 | R1 |
| 2 | Fault-Tolerant Engine | `WorkflowEngine` with try/except wrapper, SQLite ledger update on error | M1 | R2 |
| 3 | Pipeline Idempotency | Engine checks completed steps before node execution to allow resume | M1 | R1, R2 |
| 4 | Engine & Node Unit Tests | `pytest tests/workflow/test_engine.py` with mock failing nodes asserting `FAILED` status | M2 | Acceptance Criteria |
| 5 | Architectural Documentation | Document engine mechanics & Mermaid diagrams in `PromptBook/Phase08/01_Workflow_Engine.md` | M3 | R3, Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Workflow Engine & Node Abstraction | Implement `src/core/workflow/node.py` & `src/core/workflow/engine.py` | none | DONE |
| M2 | Engine Fault-Tolerance & Unit Test Suite | Implement `tests/workflow/test_engine.py` verifying mock node exceptions | M1 | DONE |
| M3 | Architectural Documentation & Mermaid Diagrams | Author `PromptBook/Phase08/01_Workflow_Engine.md` | M1, M2 | DONE |

## Interface Contracts
### `Node` (Abstract Base Class)
- Module: `src/core/workflow/node.py`
- Abstract Property: `name: str`
- Abstract Method: `execute(self, run_id: str, ledger: StateLedger) -> Dict[str, Any]`
- Contract: Reads inputs exclusively via `ledger.get_completed_steps(run_id)` or `ledger.get_run(run_id)`. Returns dict of step output artifacts. Must NOT take or store in-memory state objects from preceding nodes.

### `WorkflowEngine`
- Module: `src/core/workflow/engine.py`
- Signature: `WorkflowEngine(nodes: List[Node], ledger: StateLedger)`
- Method: `run_pipeline(self, run_id: str) -> PipelineExecutionResult`
- Contract: Iterates through `nodes`. Checks if step completed. Wraps execution in `try...except Exception`. On failure, records step failure via `ledger.record_step_failure()`, sets run status to `FAILED`, and returns failure result without raising/crashing python.

## Code Layout
```
src/core/workflow/
├── __init__.py
├── node.py
└── engine.py

tests/workflow/
├── __init__.py
└── test_engine.py

PromptBook/Phase08/
└── 01_Workflow_Engine.md
```
