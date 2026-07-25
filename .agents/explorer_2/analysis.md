# Phase 05 Exploration Report: Core Data Models & Schemas

## Executive Summary
This report analyzes the existing codebase environment, core module structure, Pydantic V2 usage, state ledger alignment, test setup, and Phase 05 documentation requirements to prepare for implementing strict Pydantic V2 data models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`, etc.).

---

## 1. Environment & Pydantic V2 Verification

- **Python Interpreter**: `/home/adarsh/Documents/Youtube-Channel/.venv/bin/python3` (Python 3.13.7)
- **Pydantic Version**: `2.13.4` (Confirmed Pydantic V2)
- **Pydantic Settings**: Installed (`pydantic-settings 2.13.1`)
- **Pydantic V2 Usage Patterns in Codebase**:
  - `src/core/config.py` relies on Pydantic V2 `BaseSettings`, `Field`, `SecretStr`, and `SettingsConfigDict`.
  - Utilizes Pydantic V2 methods: `.model_dump()` and `.model_validate()`.

---

## 2. Codebase Structure & Existing Core Modules

### `src/core/` Structure
- `src/core/base.py`:
  - Defines generic structural protocols via `@runtime_checkable` `Protocol`: `PipelineModule[T_contra, T_co]`, `Service`, `Repository[T]`, `Provider[T_co]`, `Factory[T_co]`, `Command`, `Configuration`, `Lifecycle`, `Validator[T_contra]`.
  - Defines standard execution outcome wrapper: `@dataclass class BasePipelineResult[T]`.
- `src/core/config.py`:
  - Environment profile enum `Environment(StrEnum)`: `DEVELOPMENT`, `TESTING`, `PRODUCTION`.
  - Sub-configurations: `ScraperConfig`, `RAGConfig`, `GeminiConfig`, `YouTubeConfig`.
  - Root configuration: `PipelineConfig` using double-underscore `__` delimiter for nested env override parsing (`SCRAPER__TIMEOUT_SECONDS=20`).
- `src/core/exceptions.py`:
  - Root: `PipelineError(Exception)`
  - Classifications: `RetryableError(PipelineError)`, `FatalError(PipelineError)`
  - Key validation exceptions: `ValidationError(FatalError)` and `PipelineValidationError(ValidationError)`.
- `src/core/orchestrator/state_ledger.py`:
  - SQLite WAL mode execution tracking (`StateLedger`).
  - Table `pipeline_runs`: `pipeline_run_id` (PRIMARY KEY), `slug`, `status`, `created_at`, `updated_at`, `metadata` (JSON TEXT).
  - Table `step_executions`: `step_execution_id` (PRIMARY KEY), `pipeline_run_id` (FOREIGN KEY), `step_name`, `status`, `input_payload` (JSON TEXT), `output_payload` (JSON TEXT), `error_message`, `error_details`, `created_at`, `updated_at`.

### Legacy Models in `src/models/`
- Existing draft models in `src/models/` (`problem.py`, `enums.py`, `pipeline.py`, etc.) utilize Python stdlib `@dataclass` rather than Pydantic V2 models.
- `src/core/models/` **does not exist yet** and must be created for Phase 05.

---

## 3. Directory Audit & Missing Deliverables

| Target Path | Existing Status | Action Required for Phase 05 |
|---|---|---|
| `src/core/models/` | Missing | Scaffold directory & create `__init__.py`, `video.py`, `plan.py`, `assets.py` using Pydantic V2 `BaseModel` |
| `PromptBook/Phase05/` | Exists (Contains legacy plugin docs) | Scaffold `PromptBook/Phase05/01_Data_Models.md` mapping models to State Ledger |
| `tests/models/` | Missing (`tests/test_models/` exists with `__init__.py` only) | Scaffold `tests/models/` & create `test_validation.py` asserting `ValidationError`s on malformed JSON |

---

## 4. Pytest Setup & Test Execution Analysis

- **Configuration Files**:
  - `pytest.ini`: Sets `addopts = --strict-markers --cov=src --cov-report=term-missing -v`, `testpaths = tests`, markers: `unit`, `integration`, `e2e`, `performance`.
  - `pyproject.toml`: Configures `testpaths = ["tests"]`, `pythonpath = ["."]`.
- **Test Suite Status**:
  - Running root `pytest` encounters collection errors in unbuilt future modules (`tests/evolution`, `tests/media`, `tests/plugins`).
  - Target-specific tests in `tests/core/` and `tests/orchestrator/` run cleanly with 100% success (23 tests passed):
    - `tests/core/test_base.py`: PASSED
    - `tests/core/test_config.py`: PASSED
    - `tests/core/test_exceptions.py`: PASSED
    - `tests/core/test_logger.py`: PASSED
    - `tests/orchestrator/test_state_ledger.py`: PASSED

---

## 5. Blueprint for Phase 05 Implementation

1. **Model Definitions (`src/core/models/`)**:
   - `video.py`: `VideoMetadata` (slug, title, resolution: 1080p/720p/4k, frame_rate, duration_seconds > 0, status, created_at, updated_at).
   - `plan.py`: `EducationalPlan` (problem_slug, title, difficulty, target_audience, core_concepts, script_outline, render_segments: List[RenderSegment]).
   - `assets.py`: `RenderSegment` (segment_id, sequence_index >= 0, scene_type, voiceover_text, duration_seconds > 0.0, visual_assets: List[str]).
2. **Ledger Alignment**:
   - Serialization methods (`model_dump()`, `model_dump_json()`) ensuring 1-to-1 compatibility with SQLite `pipeline_runs.metadata` and `step_executions.input_payload`/`output_payload`.
3. **Tests (`tests/models/test_validation.py`)**:
   - Active validation testing with invalid payloads (missing required fields, negative durations, invalid resolution strings, wrong field types) checking for `pydantic.ValidationError` or `PipelineValidationError`.
4. **Documentation (`PromptBook/Phase05/01_Data_Models.md`)**:
   - Comprehensive data contract documentation with JSON schemas and State Ledger alignment table.
