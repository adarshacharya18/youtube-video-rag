# Phase 05: Core Data Models & Schemas Documentation

## 1. Overview

Phase 05 establishes strict Pydantic V2 data models and schemas for the Automated DSA Educational YouTube Video Pipeline. These models reside in `src/core/models/` and align 1-to-1 with the SQLite State Ledger (Phase 04). All models enforce rigorous type safety and semantic validation before content reaches downstream rendering engines.

---

## 2. Model Specifications

### 2.1 Video & Platform Models (`src/core/models/video.py`)

- **`VideoResolution`** (StrEnum): `"720p"`, `"1080p"`, `"1440p"`, `"4K"`
- **`TargetPlatform`** (StrEnum): `"youtube"`, `"youtube_shorts"`, `"tiktok"`
- **`PrivacyStatus`** (StrEnum): `"public"`, `"unlisted"`, `"private"`
- **`Difficulty`** (StrEnum): `"EASY"`, `"MEDIUM"`, `"HARD"`

- **`SEOMetadata`**:
  - `youtube_title` (str, 1..100 chars, non-whitespace)
  - `youtube_description` (str, 1..5000 chars, non-whitespace)
  - `tags` (list[str], total chars <= 500)
  - `category_id` (int, default 27)
  - `privacy_status` (PrivacyStatus, default public)
  - `chapter_timestamps` (list[dict[str, str]])

- **`VideoMetadata`**:
  - `title` (str, 1..100 chars, non-whitespace)
  - `description` (str, 1..5000 chars, non-whitespace)
  - `slug` (str, regex `^[a-z0-9-]+$`)
  - `resolution` (VideoResolution, default "1080p")
  - `width` (int, gt 0, default 1920)
  - `height` (int, gt 0, default 1080)
  - `fps` (int, allowed set `{24, 25, 30, 50, 60, 120}`, default 30)
  - `tags` (list[str], total chars <= 500)
  - `format` (str, default "mp4")
  - `target_platform` (TargetPlatform, default "youtube")
  - `category_id` (int, gt 0, default 27)
  - `privacy_status` (PrivacyStatus, default "public")
  - `language` (str, default "en")
  - `problem_number` (int | None)
  - `difficulty` (Difficulty | None)
  - `seo_metadata` (SEOMetadata | None)
  - *Validators*: Non-whitespace checks, FPS allowed set check, total tags length check, and post-model alignment of `resolution` with `width` and `height`.

---

### 2.2 Educational Plan Models (`src/core/models/plan.py`)

- **`PlanSection`**:
  - `section_id` (str, non-whitespace)
  - `section_type` (str, non-whitespace)
  - `title` (str, non-whitespace)
  - `narration` (str, non-whitespace)
  - `estimated_duration` (float, gt 0.0)
  - `visual_cue_ids` (list[str])
  - `order` (int, ge 0)

- **`CodeSnippet`**:
  - `snippet_id` (str, non-whitespace)
  - `language` (str, default "python")
  - `code` (str, non-whitespace)
  - `explanation` (str | None)
  - `line_highlights` (list[int], line numbers >= 1)

- **`VisualCue`**:
  - `cue_id` (str, non-whitespace)
  - `animation_type` (str, non-whitespace)
  - `description` (str, non-whitespace)
  - `parameters` (dict[str, Any])

- **`ConceptPrerequisite`**:
  - `concept` (str, non-whitespace)
  - `description` (str | None)

- **`LearningObjective`**:
  - `objective_id` (str, non-whitespace)
  - `description` (str, non-whitespace)
  - `taxonomic_level` (str | None)

- **`EducationalPlan`**:
  - `topic` (str, non-whitespace)
  - `slug` (str, regex `^[a-z0-9-]+$`)
  - `target_audience` (str, default "Beginner")
  - `difficulty` (str, default "Medium")
  - `learning_objectives` (list[LearningObjective | str], min 1 item)
  - `prerequisites` (list[ConceptPrerequisite | str])
  - `sections` (list[PlanSection], min 1 item)
  - `code_snippets` (list[CodeSnippet])
  - `visual_cues` (list[VisualCue])
  - `estimated_total_duration` (float, gt 0.0)
  - *Validators*: Slug regex pattern, non-empty learning objectives, non-duplicate `section_id` check across sections, and section duration summation matching `estimated_total_duration` within 0.1s tolerance.

---

### 2.3 Assets & Render Manifest Models (`src/core/models/assets.py`)

- **`AssetReference`**:
  - `asset_id` (str, non-whitespace)
  - `asset_type` (str, non-whitespace)
  - `file_path` (str, non-whitespace)
  - `duration` (float | None, gt 0.0)

- **`AudioAsset`**:
  - `audio_id` (str, non-whitespace)
  - `file_path` (str, non-whitespace)
  - `duration_seconds` (float, gt 0.0)
  - `sample_rate` (int, gt 0, default 24000)
  - `voice_model` (str, default "kokoro")

- **`VideoAsset`**:
  - `asset_id` (str, non-whitespace)
  - `file_path` (str, non-whitespace)
  - `duration_seconds` (float, gt 0.0)
  - `resolution` (str, default "1920x1080")
  - `fps` (int, gt 0, le 120, default 30)
  - `file_size_bytes` (int, ge 0, default 0)

- **`RenderSegment`**:
  - `segment_id` (str, non-whitespace)
  - `segment_type` (str, allowed set: `{"intro", "code_walkthrough", "visual_anim", "outro", "narration"}`)
  - `start_time` (float, ge 0.0)
  - `end_time` (float, gt 0.0)
  - `duration` (float, gt 0.0)
  - `asset_references` (list[AssetReference])
  - `audio_path` (str | None)
  - `visual_path` (str | None)
  - `narration_text` (str | None)
  - `volume` (float, 0.0..2.0, default 1.0)
  - `transition_in` (str | None)
  - `transition_out` (str | None)
  - `audio_asset` (AudioAsset | None)
  - `scene_type` (str | None)
  - `visual_parameters` (dict[str, Any])
  - *Validators*: `end_time > start_time`, `duration == end_time - start_time` (tolerance 1e-3), requirement of at least one asset reference (`audio_path`, `visual_path`, `asset_references`, or `audio_asset`).

- **`RenderManifest`**:
  - `pipeline_run_id` (str, non-whitespace)
  - `slug` (str, regex `^[a-z0-9-]+$`)
  - `segments` (list[RenderSegment], min 1 item)
  - `total_duration` (float, gt 0.0)

- **`AssembledVideo`**:
  - `slug` (str, regex `^[a-z0-9-]+$`)
  - `final_video_path` (str, non-whitespace)
  - `thumbnail_path` (str | None)
  - `total_duration_seconds` (float, gt 0.0)
  - `file_size_bytes` (int, ge 0, default 0)
  - `segments` (list[RenderSegment])
  - `assembled_at` (str | datetime | None)

---

## 3. Re-exports & Usage

All models are re-exported in `src/core/models/__init__.py`:

```python
from src.core.models import (
    AssembledVideo,
    AssetReference,
    AudioAsset,
    CodeSnippet,
    ConceptPrerequisite,
    Difficulty,
    EducationalPlan,
    LearningObjective,
    PlanSection,
    PrivacyStatus,
    RenderManifest,
    RenderSegment,
    SEOMetadata,
    TargetPlatform,
    VideoAsset,
    VideoMetadata,
    VideoResolution,
    VisualCue,
)
```

---

## 4. 1-to-1 SQLite State Ledger Mapping Reference

The Pydantic V2 models defined in Phase 05 map directly (1-to-1) to the SQLite State Ledger schema established in Phase 04 (`src/core/orchestrator/state_ledger.py`).

### 4.1 Schema Mapping Table

| Pydantic Model | SQLite Table & Column | Description & Usage |
|---|---|---|
| `VideoMetadata` | `pipeline_runs.metadata` | Global run configuration serialized via `.model_dump(mode="json")` into JSON string column `metadata`. Re-hydrated via `VideoMetadata.model_validate(run.metadata)`. |
| `EducationalPlan` | `step_executions.input_payload` / `output_payload` | Structured output of the plan generation step (or input to script/rendering steps), serialized via `.model_dump(mode="json")` and stored in JSON string columns. Re-hydrated via `EducationalPlan.model_validate(...)`. |
| `RenderSegment` | `step_executions.input_payload` / `output_payload` | Individual scene/segment rendering payload produced during video assembly. Serialized via `.model_dump(mode="json")` and re-hydrated via `RenderSegment.model_validate(...)`. |

### 4.2 Serialization & Re-Hydration Pattern

When persisting state to the SQLite State Ledger, Pydantic V2 models are converted to JSON-compatible dictionaries using `.model_dump(mode="json")`. Upon retrieval from the State Ledger (which automatically parses SQLite JSON text into Python dictionaries), `model_validate()` re-instantiates fully validated model instances.

#### Python Code Example

```python
from src.core.models import EducationalPlan, PlanSection, RenderSegment, VideoMetadata
from src.core.orchestrator.state_ledger import StateLedger

# 1. Initialize State Ledger
with StateLedger("pipeline_state.db") as ledger:
    # 2. Instantiate models
    video_meta = VideoMetadata(
        title="Two Sum Explained",
        description="Detailed guide to solving Two Sum.",
        slug="two-sum",
    )

    # 3. Create run with VideoMetadata mapped to pipeline_runs.metadata
    run_id = ledger.create_run(
        slug=video_meta.slug,
        metadata=video_meta.model_dump(mode="json"),
    )

    # 4. Re-hydrate VideoMetadata from SQLite run record
    run_record = ledger.get_run(run_id)
    retrieved_meta = VideoMetadata.model_validate(run_record.metadata)

    # 5. Record step execution using EducationalPlan as output payload
    plan = EducationalPlan(
        topic="Two Sum",
        slug="two-sum",
        learning_objectives=["Master Hash Maps"],
        sections=[
            PlanSection(
                section_id="sec-1",
                section_type="intro",
                title="Introduction",
                narration="Welcome to Two Sum.",
                estimated_duration=10.0,
            )
        ],
        estimated_total_duration=10.0,
    )

    step_id = ledger.record_step_start(
        pipeline_run_id=run_id,
        step_name="plan_generation",
        input_payload=retrieved_meta.model_dump(mode="json"),
    )
    ledger.record_step_completion(
        step_execution_id=step_id,
        output_payload=plan.model_dump(mode="json"),
    )

    # 6. Re-hydrate EducationalPlan from step_executions
    step_record = ledger.get_step_execution(step_id)
    retrieved_plan = EducationalPlan.model_validate(step_record.output_payload)

    # 7. Record RenderSegment execution payload
    segment = RenderSegment(
        segment_id="seg-1",
        segment_type="intro",
        start_time=0.0,
        end_time=10.0,
        duration=10.0,
        audio_path="/path/to/narration.mp3",
    )

    seg_step_id = ledger.record_step_start(
        pipeline_run_id=run_id,
        step_name="segment_render",
        input_payload=retrieved_plan.model_dump(mode="json"),
    )
    ledger.record_step_completion(
        step_execution_id=seg_step_id,
        output_payload=segment.model_dump(mode="json"),
    )

    # 8. Re-hydrate RenderSegment from step_executions
    seg_record = ledger.get_step_execution(seg_step_id)
    retrieved_segment = RenderSegment.model_validate(seg_record.output_payload)
```

