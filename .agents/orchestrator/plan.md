# Phase 01: Initial Setup & Global Architecture — Project Plan

## Architecture & Scope
Phase 01 establishes the repository scaffolding, core coding guidelines, base foundation classes, configuration management with Pydantic, and architectural documentation for the Automated DSA Educational YouTube Video Pipeline using a Synchronous Batch-Pipeline paradigm.

## Milestones

| # | Milestone Name | Scope & Deliverables | Dependencies | Status |
|---|----------------|----------------------|--------------|--------|
| M1 | Exploration & Repository Context | Inspect existing repository structure, python environment, pydantic version, pytest configuration | None | IN_PROGRESS |
| M2 | Global Scaffolding & Guidelines | Scaffold `src/`, `tests/`, `scripts/`, `PromptBook/Phase01/`. Create `PromptBook/Phase01/01_Global_Rules.md` (PEP 8, static typing, structural logging) | M1 | PLANNED |
| M3 | Core Foundation & Config | Create `src/core/__init__.py`, `src/core/base.py`, `src/core/exceptions.py`, `src/core/config.py`, and `tests/core/test_config.py` | M2 | PLANNED |
| M4 | Architectural Documentation | Scaffold `PromptBook/Phase01/02_Synchronous_Batch_Pipeline_Architecture.md` outlining the synchronous batch-pipeline architecture, forbidding async event buses and dynamic DI containers | M2 | PLANNED |
| M5 | Review, Challenge & Forensic Audit | Verification via Reviewer, Challenger (executing pytest), and Forensic Auditor (zero tolerance integrity check) | M3, M4 | PLANNED |

## Interface Contracts & Core Classes
- `src/core/base.py`: PipelineComponent base class, BasePipelineResult model/dataclass.
- `src/core/exceptions.py`: `PipelineError` (base exception), `ConfigurationError`, `PipelineStageError`, `PipelineValidationError`.
- `src/core/config.py`: Pydantic `BaseSettings` / `BaseModel` for system configuration loading environment variables (e.g. PIPELINE_ENV, LOG_LEVEL, OUTPUT_DIR, STATE_LEDGER_PATH, etc.).
- `tests/core/test_config.py`: Unit tests validating Pydantic environment hydration and validation defaults/overrides.
- `PromptBook/Phase01/01_Global_Rules.md`: Python coding conventions (PEP 8), strict type hint rules (mypy/pyright compatible), structural logging guidelines (JSON/structured key-value logging).
- `PromptBook/Phase01/02_Synchronous_Batch_Pipeline_Architecture.md`: Synchronous pipeline design, single composition root, stage interface, explicit prohibition of async event buses and dynamic DI containers.
