# Project: Phase 14 - Integration & Production Orchestration

## Architecture
- `src/cli/ops.py`: Command Line Interface with Click / Argparse / Typer / Rich for `run`, `status`, `resume`, `health`.
- `src/core/orchestrator/pipeline_runner.py`: Single cohesive pipeline linking nodes chronologically (Ingestion -> Plan -> Script -> TTS -> Manim -> FFmpeg).
- `PromptBook/Phase14/01_Production_Orchestration.md`: Documentation for DevOps engineers on system startup, CLI commands, resume handling, and health monitoring.
- `tests/production/test_pipeline_e2e.py`: E2E integration test suite covering end-to-end pipeline execution via orchestrator.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Pipeline Orchestrator | Single cohesive pipeline runner linking Ingestion -> Plan -> Script -> TTS -> Manim -> FFmpeg | M1 | R2 |
| 2 | Master CLI (`ops.py`) | Operational CLI supporting `run`, `status`, `resume`, `health` | M1 | R1 |
| 3 | Operational Documentation | Runbooks and system startup guide in `PromptBook/Phase14/01_Production_Orchestration.md` | M2 | R3 |
| 4 | E2E Integration Testing | Comprehensive test suite in `tests/production/test_pipeline_e2e.py` | M3 | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M0 | Exploration | Map existing codebase, node interfaces, and test environment | none | DONE |
| M1 | Core Implementation | Build `pipeline_runner.py` and `ops.py` | M0 | DONE |
| M2 | Runbook Documentation | Create `PromptBook/Phase14/01_Production_Orchestration.md` | M1 | IN_PROGRESS |
| M3 | E2E Testing & Verification | Create `tests/production/test_pipeline_e2e.py` & pass verification | M1, M2 | PLANNED |

## Interface Contracts
### Master CLI ↔ Pipeline Orchestrator
- `ops.py run --topic <topic> --output <dir>`: Invokes `PipelineRunner.run(...)`
- `ops.py status --job-id <id>`: Checks status in State Ledger / Workflow Engine
- `ops.py resume --job-id <id>`: Resumes pipeline execution from failed/checkpointed node
- `ops.py health`: Verifies system health (dependencies, storage, environment)

## Code Layout
- `src/cli/ops.py`
- `src/core/orchestrator/pipeline_runner.py`
- `PromptBook/Phase14/01_Production_Orchestration.md`
- `tests/production/test_pipeline_e2e.py`
