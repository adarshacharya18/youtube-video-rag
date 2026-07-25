# Project: Phase 05 Core Data Models & Schemas

## Architecture
- Pydantic V2 BaseModel schemas defining data flowing through the Automated DSA Educational YouTube Video Pipeline.
- Core Data Models:
  - `VideoMetadata` (`src/core/models/video.py`): Video title, description, resolution, fps, tags, format, target platform, SEO metadata.
  - `EducationalPlan` (`src/core/models/plan.py`): Educational topic, target audience, learning objectives, script breakdown/sections, code snippets, visual cues, concept prerequisites.
  - `RenderSegment` (`src/core/models/assets.py`): Timeline render segment, segment type (intro, code_walkthrough, visual_anim, outro, narration), start/end time, duration, asset references, audio/narration paths, audio asset, video asset, render manifest, assembled video.
- Integration: 1-to-1 alignment with SQLite State Ledger (`src/core/orchestrator/state_ledger.py`) fields `pipeline_runs.metadata`, `step_executions.input_payload`, `step_executions.output_payload`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | VideoMetadata Model | Pydantic V2 model for video metadata, title, resolution, fps, tags | M1 | R1 |
| 2 | EducationalPlan Model | Pydantic V2 model for educational plan, topic, sections, code snippets | M1 | R1 |
| 3 | RenderSegment Model | Pydantic V2 model for timeline render segments, asset refs, durations | M1 | R1 |
| 4 | Semantic Validation | Strict validations (positive durations, finite floats, valid resolutions, non-empty strings) | M1 | R2 |
| 5 | State Ledger 1-to-1 Mapping | Serialization & schema alignment with SQLite State Ledger | M1 | R2 |
| 6 | Validation Test Suite | `tests/models/test_validation.py` testing malformed data & edge cases | M2 | Acceptance |
| 7 | Data Contract Documentation | `PromptBook/Phase05/01_Data_Models.md` documenting Pydantic schemas | M3 | R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Data Models | `video.py`, `plan.py`, `assets.py` with strict Pydantic V2 validation | Survey | DONE |
| M2 | Validation Test Suite | `tests/models/test_validation.py` testing malformed data & edge cases | M1 | DONE |
| M3 | Data Contract Docs | `PromptBook/Phase05/01_Data_Models.md` with 1-to-1 ledger mapping | M1 | DONE |
| M4 | Gate & Forensic Audit | Reviewers, Challengers, and Forensic Auditor verification | M1, M2, M3 | DONE |

## Interface Contracts
### Models ↔ State Ledger Serialization
- All models inherit from `Pydantic V2 BaseModel`.
- Serialization: `.model_dump(mode="json")`, `.model_dump_json()`.
- Deserialization: `.model_validate()`, `.model_validate_json()`.
- JSON-compatible dictionaries stored directly into State Ledger `metadata`, `input_payload`, and `output_payload`.

## Code Layout
- `src/core/models/__init__.py`
- `src/core/models/video.py`
- `src/core/models/plan.py`
- `src/core/models/assets.py`
- `tests/models/test_validation.py`
- `PromptBook/Phase05/01_Data_Models.md`
