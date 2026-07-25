# Phase 05 Core Data Models & Schemas: State Ledger Alignment Analysis

**Author:** Explorer 1  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Working Directory:** `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_1`  
**Date:** July 2026  
**Status:** Canonical Investigation Report  

---

## 1. Executive Summary & Overview

This analysis investigates the **Phase 04 State Ledger** implementation in `src/core/orchestrator/state_ledger.py`, its database tables, columns, types, and JSON blob fields, and details how the Phase 05 Pydantic V2 data models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`) must align 1-to-1 with the State Ledger.

The pipeline operates under a **Synchronous Batch-Pipeline** paradigm. Crash recovery and idempotency rely on atomic state transitions recorded in SQLite. The State Ledger persists high-level run configuration, step execution status, and intermediate payload outputs as JSON blobs.

To maintain type safety and data integrity across pipeline stages:
1. **`src/core/models/video.py`** (`VideoMetadata`, `SEOMetadata`): Defines target problem attributes, video parameters, and YouTube SEO details. Aligns with `pipeline_runs.metadata` and step outputs (`scraper`, `script`, `youtube`).
2. **`src/core/models/plan.py`** (`EducationalPlan`, `LearningObjective`, `ConceptPrerequisite`, `PlanSectionOutline`): Defines pedagogical breakdown and visual outline. Aligns with `step_executions.output_payload` for step `educational_planner` / `plan`.
3. **`src/core/models/assets.py`** (`RenderSegment`, `AudioAsset`, `VideoAsset`, `AssembledVideo`): Defines visual rendering segments and audio/video asset outputs. Aligns with `step_executions.output_payload` for step `manim` / `render` / `assembly`.

---

## 2. State Ledger DDL & Schema Architecture Analysis

### 2.1 SQLite Schema & Table Definitions

The SQLite database (located at `data/state_ledger.db`) is initialized by `StateLedger.init_db()` in `src/core/orchestrator/state_ledger.py`. It consists of two relational tables: `pipeline_runs` and `step_executions`.

```sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
    pipeline_run_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS step_executions (
    step_execution_id TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL,
    input_payload TEXT,
    output_payload TEXT,
    error_message TEXT,
    error_details TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (pipeline_run_id) REFERENCES pipeline_runs (pipeline_run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_step_executions_run_id ON step_executions(pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_slug ON pipeline_runs(slug);
```

### 2.2 Table Field Analysis & Data Types

| Table | Column Name | SQLite Data Type | Python / Pydantic Type | Nullable? | Description / Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `pipeline_runs` | `pipeline_run_id` | `TEXT` | `str` | **No** (PK) | Unique run identifier e.g., `run_a1b2c3d4...` |
| `pipeline_runs` | `slug` | `TEXT` | `str` | **No** | Target problem slug e.g. `two-sum` |
| `pipeline_runs` | `status` | `TEXT` | `StepStatus` (Enum string) | **No** | Run lifecycle state (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`) |
| `pipeline_runs` | `created_at` | `TEXT` | `datetime` (ISO-8601 str) | **No** | UTC creation timestamp |
| `pipeline_runs` | `updated_at` | `TEXT` | `datetime` (ISO-8601 str) | **No** | UTC last updated timestamp |
| `pipeline_runs` | `metadata` | `TEXT` | `dict[str, Any]` (JSON) | Yes | JSON blob containing `VideoMetadata` and pipeline configuration |
| `step_executions` | `step_execution_id` | `TEXT` | `str` | **No** (PK) | Unique step execution ID e.g., `step_e5f6g7h8...` |
| `step_executions` | `pipeline_run_id` | `TEXT` | `str` | **No** (FK) | References `pipeline_runs.pipeline_run_id` |
| `step_executions` | `step_name` | `TEXT` | `str` | **No** | Module/step name (`scraper`, `tags`, `rag`, `plan`, `script`, `voice`, `render`, `assembly`, `youtube`, `memory`) |
| `step_executions` | `status` | `TEXT` | `StepStatus` (Enum string) | **No** | Step lifecycle state (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`) |
| `step_executions` | `input_payload` | `TEXT` | `dict[str, Any]` (JSON) | Yes | JSON blob containing step input models/arguments |
| `step_executions` | `output_payload` | `TEXT` | `dict[str, Any]` (JSON) | Yes | JSON blob containing step output models (`EducationalPlan`, `RenderSegment`, etc.) |
| `step_executions` | `error_message` | `TEXT` | `str` | Yes | Error summary on step failure |
| `step_executions` | `error_details` | `TEXT` | `dict[str, Any]` (JSON) | Yes | JSON blob containing exception details/traceback |
| `step_executions` | `created_at` | `TEXT` | `datetime` (ISO-8601 str) | **No** | UTC creation timestamp |
| `step_executions` | `updated_at` | `TEXT` | `datetime` (ISO-8601 str) | **No** | UTC last updated timestamp |

### 2.3 SQLite Concurrency & Transactional Configuration

The `StateLedger` class applies four mandatory PRAGMA settings upon connection initialization:
1. `PRAGMA journal_mode=WAL;` — Enables Write-Ahead Logging for concurrent non-blocking reads during background step execution.
2. `PRAGMA synchronous=NORMAL;` — Optimizes write performance without sacrificing crash safety.
3. `PRAGMA foreign_keys=ON;` — Guarantees referential integrity between `step_executions` and `pipeline_runs`.
4. `PRAGMA busy_timeout=5000;` — Avoids `database is locked` errors during multi-threaded step transitions.

Thread safety is guaranteed using an internal `threading.Lock()` mutex wrapping all connection context blocks (`with self._lock: with self._conn:`).

---

## 3. Storage & Mapping of Core Domain Concepts

### 3.1 `VideoMetadata` Mapping
- **Ledger Storage Location**:
  - `pipeline_runs.metadata`: Stores global video configuration and problem metadata upon pipeline run creation.
  - `step_executions.output_payload` (`step_name='scraper'` or `'script'` or `'youtube'`): Stores problem parameters, generated SEO fields, and published video links.
- **Payload Structure**: Serialized JSON dictionary matching `VideoMetadata.model_dump()`.

### 3.2 `EducationalPlan` Mapping
- **Ledger Storage Location**:
  - `step_executions.output_payload` (`step_name='educational_planner'` or `'plan'`): Stores the structured output of the educational planning stage.
  - `step_executions.input_payload` (`step_name='script'` or `'render'`): Consumed by downstream script compilation and storyboard rendering steps.
- **Payload Structure**: Serialized JSON dictionary matching `EducationalPlan.model_dump()`.

### 3.3 `RenderSegment` Mapping
- **Ledger Storage Location**:
  - `step_executions.output_payload` (`step_name='manim'` or `'render'` or `'storyboard'`): Stores a list or dictionary of animation render segments.
  - `step_executions.input_payload` (`step_name='assembly'`): Consumed by the video assembler to combine audio files and rendered scene clips.
- **Payload Structure**: Serialized JSON list/dictionary matching `list[RenderSegment]`.

### 3.4 Execution Status & Pipeline State
- **Execution Status**: Handled via `StepStatus` Enum (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`).
- **Pipeline State**: Step start transitions `pipeline_runs.status` and `step_executions.status` to `IN_PROGRESS`. Step failure automatically updates both `step_executions` and parent `pipeline_runs` to `FAILED`.

---

## 4. Field Specifications, Types, and Constraints for Pydantic V2 Models

All models must inherit strictly from `pydantic.BaseModel` (Pydantic V2) and reside in `src/core/models/`.

### 4.1 File: `src/core/models/video.py`

#### 4.1.1 `Difficulty` (Enum)
```python
from enum import Enum

class Difficulty(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
```

#### 4.1.2 `SEOMetadata` (Pydantic V2 `BaseModel`)
| Field Name | Type | Constraints / Validation | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `youtube_title` | `str` | `min_length=1`, `max_length=100` | Required | Title formatted for YouTube |
| `youtube_description` | `str` | `max_length=5000` | Required | Markdown/formatted YouTube description |
| `tags` | `list[str]` | Max 500 chars total length | `[]` | SEO video tags |
| `category_id` | `int` | `ge=1` | `27` | YouTube Education category |
| `privacy_status` | `Literal["public", "unlisted", "private"]` | Standard string literal | `"unlisted"` | YouTube privacy setting |
| `chapter_timestamps` | `list[dict[str, str]]` | Valid timestamp strings `MM:SS` | `[]` | Video chapter markers |

#### 4.1.3 `VideoMetadata` (Pydantic V2 `BaseModel`)
| Field Name | Type | Constraints / Validation | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `slug` | `str` | `min_length=1`, `max_length=128`, `pattern=r"^[a-z0-9-]+$"` | Required | Canonical LeetCode slug |
| `title` | `str` | `min_length=1`, `max_length=200` | Required | Problem title |
| `problem_number` | `int` | `ge=1` | Required | LeetCode problem number |
| `difficulty` | `Difficulty` | Enum validation | Required | Difficulty level |
| `description` | `str` | `min_length=1` | Required | Problem description text |
| `tags` | `list[str]` | List of non-empty strings | `[]` | LeetCode topic tags |
| `target_resolution` | `str` | `pattern=r"^\d+x\d+$"` (e.g. `"1920x1080"`) | `"1920x1080"` | Render resolution |
| `fps` | `int` | `gt=0`, `le=120` | `30` | Target frame rate |
| `language` | `str` | `min_length=1` | `"python"` | Code language |
| `seo_metadata` | `SEOMetadata` | Embedded model | Required | YouTube SEO configuration |
| `created_at` | `datetime` | Timezone-aware UTC | Auto (utcnow) | Model creation timestamp |
| `updated_at` | `datetime` | Timezone-aware UTC | Auto (utcnow) | Model update timestamp |

---

### 4.2 File: `src/core/models/plan.py`

#### 4.2.1 `ConceptPrerequisite` (Pydantic V2 `BaseModel`)
| Field Name | Type | Constraints / Validation | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `concept` | `str` | `min_length=1` | Required | Concept name (e.g. `"Two Pointers"`) |
| `description` | `str` | None | `""` | Brief explanation of prerequisite |

#### 4.2.2 `LearningObjective` (Pydantic V2 `BaseModel`)
| Field Name | Type | Constraints / Validation | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `objective_id` | `str` | `min_length=1` | Required | Unique objective ID e.g. `"obj_1"` |
| `description` | `str` | `min_length=1` | Required | Actionable learning goal |
| `taxonomic_level` | `str` | `min_length=1` | `"Understand"` | Bloom's taxonomy level |

#### 4.2.3 `PlanSectionOutline` (Pydantic V2 `BaseModel`)
| Field Name | Type | Constraints / Validation | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `section_id` | `str` | `min_length=1` | Required | Section ID e.g. `"sec_hook"` |
| `section_type` | `str` | Valid section type string | Required | Structural role e.g. `"HOOK"` |
| `title` | `str` | `min_length=1` | Required | Section title |
| `target_duration_seconds` | `float` | `gt=0.0` | Required | Target time in seconds |
| `key_takeaways` | `list[str]` | List of strings | `[]` | Core points to cover |

#### 4.2.4 `EducationalPlan` (Pydantic V2 `BaseModel`)
| Field Name | Type | Constraints / Validation | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `slug` | `str` | `min_length=1`, `pattern=r"^[a-z0-9-]+$"` | Required | Target problem slug |
| `target_audience` | `str` | `min_length=1` | `"Intermediate"` | Target skill level |
| `estimated_total_duration_seconds` | `float` | `gt=0.0` | Required | Total estimated plan duration |
| `primary_algorithm_pattern` | `str` | `min_length=1` | Required | Algorithm family e.g. `"HashMap"` |
| `prerequisites` | `list[ConceptPrerequisite]` | Sub-model list | `[]` | Concept prerequisites |
| `learning_objectives` | `list[LearningObjective]` | `min_length=1` | Required | List of learning objectives |
| `sections` | `list[PlanSectionOutline]` | `min_length=1` | Required | Planned video sections |
| `created_at` | `datetime` | Timezone-aware UTC | Auto (utcnow) | Plan generation timestamp |

---

### 4.3 File: `src/core/models/assets.py`

#### 4.3.1 `AudioAsset` (Pydantic V2 `BaseModel`)
| Field Name | Type | Constraints / Validation | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `audio_id` | `str` | `min_length=1` | Required | Audio asset ID |
| `file_path` | `str` | `min_length=1` | Required | Path to output `.wav` file |
| `duration_seconds` | `float` | `gt=0.0` | Required | Audio duration (must be > 0) |
| `sample_rate` | `int` | `gt=0` | `24000` | Sample rate in Hz |
| `voice_model` | `str` | `min_length=1` | `"kokoro"` | TTS model identifier |

#### 4.3.2 `RenderSegment` (Pydantic V2 `BaseModel`)
| Field Name | Type | Constraints / Validation | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `segment_id` | `str` | `min_length=1` | Required | Segment ID e.g. `"seg_01"` |
| `section_id` | `str` | `min_length=1` | Required | Parent script section ID |
| `scene_type` | `str` | `min_length=1` | Required | Manim scene style e.g. `"ARRAY_TRAVERSAL"` |
| `duration_seconds` | `float` | `gt=0.0` (STRICT: negative or 0 duration invalid) | Required | Render duration in seconds |
| `fps` | `int` | `gt=0`, `le=120` | `30` | Render frame rate |
| `resolution` | `str` | `pattern=r"^\d+x\d+$"` | `"1920x1080"` | Render resolution |
| `narration_text` | `str` | `min_length=1` | Required | Narration text for section |
| `code_snippet` | `str \| None` | Optional string | `None` | Optional code snippet for scene |
| `visual_parameters` | `dict[str, Any]` | JSON dictionary | `{}` | Scene specific visual options |
| `audio_asset` | `AudioAsset \| None` | Sub-model | `None` | Synthesized audio asset |
| `output_video_path` | `str \| None` | Optional path string | `None` | Rendered clip path `.mp4` |
| `status` | `StepStatus` | Enum value | `StepStatus.PENDING` | Segment execution status |

#### 4.3.3 `VideoAsset` (Pydantic V2 `BaseModel`)
| Field Name | Type | Constraints / Validation | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `asset_id` | `str` | `min_length=1` | Required | Video clip asset ID |
| `file_path` | `str` | `min_length=1` | Required | Path to clip `.mp4` |
| `duration_seconds` | `float` | `gt=0.0` | Required | Video clip duration |
| `resolution` | `str` | `pattern=r"^\d+x\d+$"` | `"1920x1080"` | Resolution |
| `fps` | `int` | `gt=0`, `le=120` | `30` | FPS |
| `file_size_bytes` | `int` | `ge=0` | Required | File size in bytes |

#### 4.3.4 `AssembledVideo` (Pydantic V2 `BaseModel`)
| Field Name | Type | Constraints / Validation | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `slug` | `str` | `min_length=1`, `pattern=r"^[a-z0-9-]+$"` | Required | Problem slug |
| `final_video_path` | `str` | `min_length=1` | Required | Output file path `.mp4` |
| `thumbnail_path` | `str \| None` | Optional string | `None` | Output thumbnail path `.png` |
| `total_duration_seconds` | `float` | `gt=0.0` | Required | Total assembled video duration |
| `file_size_bytes` | `int` | `ge=0` | Required | Total file size in bytes |
| `segments` | `list[RenderSegment]` | `min_length=1` | Required | Included render segments |
| `assembled_at` | `datetime` | Timezone-aware UTC | Auto (utcnow) | Timestamp of assembly |

---

## 5. JSON Serialization & Validation Requirements

1. **Pydantic V2 Native Validation**:
   All models inherit from `pydantic.BaseModel` (Pydantic V2). Instantation with bad types, missing fields, or invalid constraints (e.g. `duration_seconds=-5.0` or invalid slug `Two Sum!`) MUST raise `pydantic.ValidationError`.
2. **SQLite Interoperability**:
   - Model to SQLite: `StateLedger` accepts payload dictionaries. Models serialize via `model.model_dump()` or `model.model_dump_json()`.
   - SQLite to Model: Rows read from `step_executions.output_payload` or `pipeline_runs.metadata` are re-hydrated via `Model.model_validate_json(row["output_payload"])` or `Model.model_validate(json.loads(row["output_payload"]))`.
3. **Fail-Fast Policy**:
   Invalid LLM outputs or corrupted state ledger entries fail immediately during Pydantic parsing before entering rendering engines or external APIs.

---

## 6. Recommended Action Plan for Phase 05 Implementation

1. **Create Pydantic V2 Model Files**:
   - `src/core/models/video.py`
   - `src/core/models/plan.py`
   - `src/core/models/assets.py`
   - Update `src/core/models/__init__.py` to export models.
2. **Create Comprehensive Unit Tests**:
   - `tests/models/test_validation.py`: Assert that malformed JSON payloads (missing required fields, negative durations, invalid resolutions, bad slugs) correctly trigger Pydantic `ValidationError`s.
   - Assert round-trip JSON serialization and re-hydration with `StateLedger` output payloads.
3. **Document Data Contracts**:
   - Create `PromptBook/Phase05/01_Data_Models.md` detailing the data contracts and 1-to-1 ledger alignment.

---

**End of Analysis Report.**
