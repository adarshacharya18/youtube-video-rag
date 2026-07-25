# Phase 05 Implementation Plan: Core Data Models & Schemas

## Objective
Implement Phase 05 data models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`) using Pydantic V2 `BaseModel`, ensuring 1-to-1 alignment with the Phase 04 SQLite State Ledger schema, strict semantic validation, comprehensive validation tests (`tests/models/test_validation.py`), and detailed documentation (`PromptBook/Phase05/01_Data_Models.md`).

## Subtasks & Milestones

### Milestone 1: Survey & Requirements Mining
- Spawn Explorers (`teamwork_preview_explorer` / `teamwork_preview_spec_miner`) to investigate:
  1. `src/core/orchestrator/state_ledger.py` and any existing state ledger schemas / migrations / DB tables from Phase 04.
  2. Existing codebase structure in `src/core/` and `tests/`.
  3. Precise field definitions, data types, constraints, and 1-to-1 ledger mapping requirements for `VideoMetadata`, `EducationalPlan`, and `RenderSegment`.

### Milestone 2: Implementation of Core Pydantic Models & Schemas
- Spawn Worker (`teamwork_preview_worker`) to implement:
  1. `src/core/models/video.py` — `VideoMetadata` model with resolution validation (e.g. 1080p, 4K, valid dimensions), title/description non-empty checks, fps checks, etc.
  2. `src/core/models/plan.py` — `EducationalPlan` model representing educational topic, target audience, script outline, code snippets, section breakdown, etc.
  3. `src/core/models/assets.py` — `RenderSegment` model (and related asset models) with positive duration validation, asset paths, timing offsets, segment types, etc.
  4. Ensure all models use Pydantic V2 features (`@field_validator`, `@model_validator`, `Field`, etc.) and align 1-to-1 with State Ledger schema.

### Milestone 3: Test Suite & Validation Hardening
- Spawn Worker / Test Writer (`teamwork_preview_worker`) to implement:
  1. `tests/models/test_validation.py` testing positive cases, missing fields, malformed JSON, invalid types, negative/zero durations, unsupported resolutions, empty strings.
  2. Verify all tests pass with `pytest`.

### Milestone 4: Documentation & Data Contracts
- Spawn Worker (`teamwork_preview_worker`) to create:
  1. `PromptBook/Phase05/01_Data_Models.md` documenting all Pydantic models, validation rules, field descriptions, and explicit 1-to-1 mapping with Phase 04 SQLite State Ledger schema.

### Milestone 5: Verification, Review, Challenger & Forensic Audit Gate
- Spawn Reviewers (`teamwork_preview_reviewer`) to review code quality, schema alignment, and typing.
- Spawn Challengers (`teamwork_preview_challenger`) to stress test models with edge cases and malformed inputs.
- Spawn Forensic Auditor (`teamwork_preview_auditor`) to run static analysis and integrity check.
- Gate approval check.

## Verification Commands
- `pytest tests/models/`
- `pytest` (full suite)
