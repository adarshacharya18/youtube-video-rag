# Phase 05 Core Data Models & Schemas — Detailed Analysis Report

**Author**: Explorer 3  
**Target System**: Automated DSA Educational YouTube Video Pipeline  
**Working Directory**: `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_3`  
**Date**: 2026-07-25  

---

## 1. Executive Summary & Scope Overview

Phase 05 establishes the foundational data contracts for the pipeline using **Pydantic V2** (`pydantic.BaseModel`). The goal is to define strict, type-safe, self-validating data structures that map 1-to-1 with the SQLite State Ledger (`src/core/orchestrator/state_ledger.py`) and prevent corrupted or malformed data from propagating down to downstream components (RAG, Gemini LLM, Manim video rendering, FFmpeg assembly, YouTube upload).

### Target Files & Deliverables
1. `src/core/models/__init__.py`: Package export for core models.
2. `src/core/models/video.py`: Pydantic V2 model for `VideoMetadata` (video resolution, frame rate, tags, title, description, format, platform).
3. `src/core/models/plan.py`: Pydantic V2 model for `EducationalPlan` and nested models (`PlanSection`, `CodeSnippet`, `VisualCue`).
4. `src/core/models/assets.py`: Pydantic V2 model for `RenderSegment` and nested models (`AssetReference`, `RenderManifest`).
5. `tests/models/test_validation.py`: Test suite actively validating correct models, malformed JSON, missing fields, type errors, and semantic violations.
6. `PromptBook/Phase05/01_Data_Models.md`: Comprehensive data contract documentation with 1-to-1 State Ledger mapping.

---

## 2. Data Model 1: `VideoMetadata` (`src/core/models/video.py`)

### Purpose
Represents video production specifications, rendering parameters, and YouTube publication metadata.

### Data Contract & Field Specifications

| Field | Type | Required | Default | Validation & Constraints | Description |
|-------|------|----------|---------|---------------------------|-------------|
| `title` | `str` | Yes | - | `strip() != ""`, `1 <= len <= 100` | YouTube video title |
| `description` | `str` | Yes | - | `strip() != ""`, `1 <= len <= 5000` | Video description with chapter timestamps |
| `resolution` | `str` | Yes | `"1080p"` | Must be in `{"720p", "1080p", "1440p", "4K"}` or match regex `^\d+x\d+$` | Target resolution string |
| `width` | `int` | Yes | `1920` | `gt=0`, `le=7680` | Horizontal pixel resolution |
| `height` | `int` | Yes | `1080` | `gt=0`, `le=4320` | Vertical pixel resolution |
| `fps` | `int` | Yes | `30` | `gt=0`, `le=120`, must be in valid set `{24, 25, 30, 50, 60, 120}` | Frame rate per second |
| `tags` | `list[str]` | Yes | - | Non-empty strings, total combined length across all tags <= 500 chars | YouTube tags for SEO |
| `format` | `str` | Yes | `"mp4"` | Must be in `{"mp4", "mov", "mkv", "webm"}` | Output video file container format |
| `target_platform` | `str` | Yes | `"youtube"` | Must be in `{"youtube", "youtube_shorts", "tiktok"}` | Target platform distribution channel |
| `category_id` | `int` | No | `27` | `gt=0` | YouTube category (27 = Education) |
| `privacy_status` | `str` | No | `"public"` | Must be in `{"public", "unlisted", "private"}` | YouTube upload visibility setting |
| `language` | `str` | No | `"en"` | Non-empty 2-letter language code | Video language ISO code |

### Semantic Validation Rules
1. **String Sanitization**: `title` and `description` must not be whitespace-only. `title.strip()` length must be between 1 and 100 characters. `description.strip()` length must be between 1 and 5000 characters.
2. **Resolution & Dimensions Alignment**: 
   - If `resolution` is `"1080p"`, `(width, height)` must be `(1920, 1080)`.
   - If `resolution` is `"4K"`, `(width, height)` must be `(3840, 2160)`.
   - If `resolution` is `"720p"`, `(width, height)` must be `(1280, 720)`.
   - If custom standard formatted resolution like `"1920x1080"` is supplied, `width` and `height` must match the parsed values.
3. **Frame Rate Validation**: `fps` must be a positive integer in `{24, 25, 30, 50, 60, 120}`. Negative, zero, or non-standard frame rates (e.g. 0, -30, 500) must raise `ValidationError`.
4. **YouTube Tag Constraints**: Each tag in `tags` must be non-empty after stripping. Total character length of `",".join(tags)` must not exceed 500 characters (YouTube API enforcement).

### Schema Design Sketch (`src/core/models/video.py`)
```python
from enum import StrEnum
from pydantic import BaseModel, Field, field_validator, model_validator

class VideoResolution(StrEnum):
    R720P = "720p"
    R1080P = "1080p"
    R1440P = "1440p"
    R4K = "4K"

class TargetPlatform(StrEnum):
    YOUTUBE = "youtube"
    YOUTUBE_SHORTS = "youtube_shorts"
    TIKTOK = "tiktok"

class PrivacyStatus(StrEnum):
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"

class VideoMetadata(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Video title")
    description: str = Field(..., min_length=1, max_length=5000, description="Video description")
    resolution: str = Field(default="1080p")
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    fps: int = Field(default=30, gt=0, le=120)
    tags: list[str] = Field(default_factory=list)
    format: str = Field(default="mp4")
    target_platform: TargetPlatform = Field(default=TargetPlatform.YOUTUBE)
    category_id: int = Field(default=27, gt=0)
    privacy_status: PrivacyStatus = Field(default=PrivacyStatus.PUBLIC)
    language: str = Field(default="en")

    @field_validator("title", "description")
    @classmethod
    def check_non_empty_str(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace only")
        return v.strip()

    @field_validator("fps")
    @classmethod
    def check_valid_fps(cls, v: int) -> int:
        valid_fps = {24, 25, 30, 50, 60, 120}
        if v not in valid_fps:
            raise ValueError(f"FPS must be one of {valid_fps}, got {v}")
        return v

    @field_validator("tags")
    @classmethod
    def check_tags(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip() for t in v if t and t.strip()]
        total_len = sum(len(t) for t in cleaned)
        if total_len > 500:
            raise ValueError(f"Combined tag length ({total_len}) exceeds YouTube 500 char limit")
        return cleaned

    @model_validator(mode="after")
    def validate_resolution_dimensions(self) -> "VideoMetadata":
        res_map = {
            "720p": (1280, 720),
            "1080p": (1920, 1080),
            "1440p": (2560, 1440),
            "4K": (3840, 2160),
        }
        if self.resolution in res_map:
            expected_w, expected_h = res_map[self.resolution]
            if self.width != expected_w or self.height != expected_h:
                # Align or validate width and height
                object.__setattr__(self, "width", expected_w)
                object.__setattr__(self, "height", expected_h)
        return self
```

---

## 3. Data Model 2: `EducationalPlan` (`src/core/models/plan.py`)

### Purpose
Represents the educational video script breakdown, topic objectives, code snippets, visual cues, and section timing.

### Nested Models
1. **`PlanSection`**:
   - `section_id` (`str`): Unique section identifier (e.g. `"sec_hook"`, `"sec_visual"`). Must be non-empty.
   - `section_type` (`str`): Structural role (e.g. `"HOOK"`, `"PROBLEM_STATEMENT"`, `"CONSTRAINTS"`, `"VISUAL_WALKTHROUGH"`, `"CODE_WALKTHROUGH"`, `"COMPLEXITY_ANALYSIS"`, `"CLOSING"`).
   - `title` (`str`): Non-empty section title.
   - `narration` (`str`): Non-empty spoken text script.
   - `estimated_duration` (`float`): Section duration in seconds (`gt=0.0`).
   - `visual_cue_ids` (`list[str]`): Associated visual cue IDs (`default_factory=list`).
   - `order` (`int`): Sequential section order index (`ge=0`).

2. **`CodeSnippet`**:
   - `snippet_id` (`str`): Unique identifier (`strip() != ""`).
   - `language` (`str`): Programming language (`"python"`, `"cpp"`, `"java"`).
   - `code` (`str`): Non-empty source code string.
   - `explanation` (`str | None`): Spoken explanation or commentary for code.
   - `line_highlights` (`list[int]`): 1-based line numbers to highlight (`ge=1`).

3. **`VisualCue`**:
   - `cue_id` (`str`): Unique cue identifier.
   - `animation_type` (`str`): Scene animation style (e.g., `"ARRAY_TRAVERSAL"`, `"TREE_RECURSION"`, `"GRAPH_BFS"`, `"CODE_HIGHLIGHT"`).
   - `description` (`str`): Human readable cue description.
   - `parameters` (`dict[str, Any]`): Animation configuration dict for Manim renderer.

### Core Model: `EducationalPlan`

| Field | Type | Required | Default | Validation & Constraints | Description |
|-------|------|----------|---------|---------------------------|-------------|
| `topic` | `str` | Yes | - | `strip() != ""` | Educational topic name |
| `slug` | `str` | Yes | - | Regex `^[a-z0-9-]+$` | Canonical problem slug identifier |
| `target_audience` | `str` | Yes | `"Beginner"` | Must be in `{"Beginner", "Intermediate", "Advanced"}` | Intended audience level |
| `difficulty` | `str` | Yes | `"Medium"` | Must be in `{"Easy", "Medium", "Hard"}` | Problem difficulty level |
| `learning_objectives` | `list[str]` | Yes | - | `len >= 1`, non-empty strings | Key takeaway objectives |
| `prerequisites` | `list[str]` | No | `[]` | List of non-empty prerequisite concepts | Required background knowledge |
| `sections` | `list[PlanSection]` | Yes | - | `len >= 1`, unique `section_id` values, positive durations | Ordered script sections |
| `code_snippets` | `list[CodeSnippet]` | No | `[]` | Snippets used in script | Source code snippets |
| `visual_cues` | `list[VisualCue]` | No | `[]` | Visual animation cues | Manim animation definitions |
| `estimated_total_duration` | `float` | Yes | - | `gt=0.0`, matches sum of section durations | Total estimated duration in seconds |

### Semantic Validation Rules
1. **Slug Format**: `slug` must match pattern `^[a-z0-9-]+$`. Uppercase letters, spaces, or special characters raise `ValidationError`.
2. **Learning Objectives**: `learning_objectives` must contain at least 1 non-empty item.
3. **Section Id Uniqueness**: All `section.section_id` values in `sections` must be unique across the plan. Duplicates raise `ValidationError`.
4. **Positive Durations**: Every `PlanSection.estimated_duration` must be strictly positive (`gt=0.0`). Negative or zero section durations raise `ValidationError`.
5. **Duration Ledger Alignment**: `estimated_total_duration` must be positive (`gt=0.0`) and equal the sum of `section.estimated_duration` across all sections (within float tolerance `abs(sum - total) < 0.1`).
6. **Code Highlight Line Bounds**: Line numbers in `CodeSnippet.line_highlights` must be positive integers (`>= 1`).

### Schema Design Sketch (`src/core/models/plan.py`)
```python
import re
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any

class PlanSection(BaseModel):
    section_id: str = Field(..., min_length=1)
    section_type: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    narration: str = Field(..., min_length=1)
    estimated_duration: float = Field(..., gt=0.0)
    visual_cue_ids: list[str] = Field(default_factory=list)
    order: int = Field(default=0, ge=0)

    @field_validator("section_id", "title", "narration")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

class CodeSnippet(BaseModel):
    snippet_id: str = Field(..., min_length=1)
    language: str = Field(default="python")
    code: str = Field(..., min_length=1)
    explanation: str | None = None
    line_highlights: list[int] = Field(default_factory=list)

    @field_validator("line_highlights")
    @classmethod
    def check_line_numbers(cls, v: list[int]) -> list[int]:
        for line in v:
            if line < 1:
                raise ValueError(f"Line highlight numbers must be >= 1, got {line}")
        return v

class VisualCue(BaseModel):
    cue_id: str = Field(..., min_length=1)
    animation_type: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)

class EducationalPlan(BaseModel):
    topic: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    target_audience: str = Field(default="Beginner")
    difficulty: str = Field(default="Medium")
    learning_objectives: list[str] = Field(..., min_length=1)
    prerequisites: list[str] = Field(default_factory=list)
    sections: list[PlanSection] = Field(..., min_length=1)
    code_snippets: list[CodeSnippet] = Field(default_factory=list)
    visual_cues: list[VisualCue] = Field(default_factory=list)
    estimated_total_duration: float = Field(..., gt=0.0)

    @field_validator("slug")
    @classmethod
    def check_slug_format(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(f"Slug must be lowercase alphanumeric with hyphens, got '{v}'")
        return v

    @field_validator("learning_objectives")
    @classmethod
    def check_objectives(cls, v: list[str]) -> list[str]:
        cleaned = [obj.strip() for obj in v if obj and obj.strip()]
        if not cleaned:
            raise ValueError("learning_objectives list must contain at least one non-empty string")
        return cleaned

    @model_validator(mode="after")
    def check_sections_and_durations(self) -> "EducationalPlan":
        sec_ids = set()
        total_sec_duration = 0.0
        for sec in self.sections:
            if sec.section_id in sec_ids:
                raise ValueError(f"Duplicate section_id '{sec.section_id}' in sections list")
            sec_ids.add(sec.section_id)
            total_sec_duration += sec.estimated_duration

        if abs(total_sec_duration - self.estimated_total_duration) > 0.1:
            raise ValueError(
                f"estimated_total_duration ({self.estimated_total_duration}) "
                f"does not match sum of section durations ({total_sec_duration})"
            )
        return self
```

---

## 4. Data Model 3: `RenderSegment` (`src/core/models/assets.py`)

### Purpose
Represents a rendered media timeline segment (combining visual clip, narration audio, start/end timestamps, duration, and asset references) for FFmpeg video assembly.

### Auxiliary / Container Models
1. **`AssetReference`**:
   - `asset_id` (`str`): Unique identifier of the asset file (`strip() != ""`).
   - `asset_type` (`str`): Type of media asset (`"video"`, `"audio"`, `"image"`, `"subtitle"`, `"manim_scene"`).
   - `file_path` (`str`): Path to asset file.
   - `duration` (`float | None`): Asset duration if applicable (`gt=0.0`).

2. **`RenderManifest`**:
   - `pipeline_run_id` (`str`): Pipeline run ID.
   - `slug` (`str`): Problem slug.
   - `segments` (`list[RenderSegment]`): Non-empty list of timeline render segments.
   - `total_duration` (`float`): Total combined duration of timeline (`gt=0.0`).

### Core Model: `RenderSegment`

| Field | Type | Required | Default | Validation & Constraints | Description |
|-------|------|----------|---------|---------------------------|-------------|
| `segment_id` | `str` | Yes | - | `strip() != ""` | Unique segment timeline ID |
| `segment_type` | `str` | Yes | - | Must be in `{"intro", "code_walkthrough", "visual_anim", "outro", "narration"}` | Type of timeline segment |
| `start_time` | `float` | Yes | - | `ge=0.0` | Segment start timestamp in seconds |
| `end_time` | `float` | Yes | - | `gt=0.0`, must be `> start_time` | Segment end timestamp in seconds |
| `duration` | `float` | Yes | - | `gt=0.0`, must equal `end_time - start_time` | Duration in seconds |
| `asset_references` | `list[AssetReference]` | No | `[]` | List of media asset references | Attached assets |
| `audio_path` | `str | None` | No | `None` | Optional path to narration `.wav`/`.mp3` audio | Audio asset file path |
| `visual_path` | `str | None` | No | `None` | Optional path to rendered `.mp4` video clip | Video clip asset file path |
| `narration_text` | `str | None` | No | `None` | Spoken narration text for subtitle alignment | Narration text |
| `volume` | `float` | No | `1.0` | `ge=0.0`, `le=2.0` | Audio gain level multiplier |
| `transition_in` | `str | None` | No | `None` | Transition effect at start (e.g. `"fade"`, `"wipe"`) | Start transition effect |
| `transition_out` | `str | None` | No | `None` | Transition effect at end | End transition effect |

### Semantic Validation Rules
1. **Timestamp Consistency**:
   - `start_time` >= 0.0
   - `end_time` > `start_time`
   - `duration` > 0.0
   - Strict relation: `duration` MUST match `end_time - start_time` within 0.001 seconds tolerance (`abs(duration - (end_time - start_time)) < 1e-3`).
2. **Segment Type Enforcement**: `segment_type` must be one of `{"intro", "code_walkthrough", "visual_anim", "outro", "narration"}`.
3. **Asset Attachment Rule**: A `RenderSegment` must have at least one media asset (either `audio_path` is provided, `visual_path` is provided, or `asset_references` is non-empty). A segment with no media assets raises `ValidationError`.
4. **Volume Control Bounds**: `volume` must be between 0.0 (muted) and 2.0 (200% volume).

### Schema Design Sketch (`src/core/models/assets.py`)
```python
import math
from pydantic import BaseModel, Field, field_validator, model_validator

class AssetReference(BaseModel):
    asset_id: str = Field(..., min_length=1)
    asset_type: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    duration: float | None = Field(default=None, gt=0.0)

    @field_validator("asset_id", "asset_type", "file_path")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

class RenderSegment(BaseModel):
    segment_id: str = Field(..., min_length=1)
    segment_type: str = Field(..., min_length=1)
    start_time: float = Field(..., ge=0.0)
    end_time: float = Field(..., gt=0.0)
    duration: float = Field(..., gt=0.0)
    asset_references: list[AssetReference] = Field(default_factory=list)
    audio_path: str | None = None
    visual_path: str | None = None
    narration_text: str | None = None
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    transition_in: str | None = None
    transition_out: str | None = None

    @field_validator("segment_id", "segment_type")
    @classmethod
    def check_non_empty_str(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

    @field_validator("segment_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid_types = {"intro", "code_walkthrough", "visual_anim", "outro", "narration"}
        if v not in valid_types:
            raise ValueError(f"segment_type must be one of {valid_types}, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_timestamps_and_assets(self) -> "RenderSegment":
        if self.end_time <= self.start_time:
            raise ValueError(f"end_time ({self.end_time}) must be strictly greater than start_time ({self.start_time})")

        expected_duration = self.end_time - self.start_time
        if not math.isclose(self.duration, expected_duration, abs_tol=1e-3):
            raise ValueError(
                f"duration ({self.duration}) does not match end_time - start_time ({expected_duration})"
            )

        if not self.audio_path and not self.visual_path and not self.asset_references:
            raise ValueError("RenderSegment must reference at least one asset (audio_path, visual_path, or asset_references)")

        return self

class RenderManifest(BaseModel):
    pipeline_run_id: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    segments: list[RenderSegment] = Field(..., min_length=1)
    total_duration: float = Field(..., gt=0.0)
```

---

## 5. SQLite State Ledger Alignment & Serialization Architecture

### 1-to-1 Mapping to `StateLedger` (`src/core/orchestrator/state_ledger.py`)

The Phase 04 State Ledger tracks runs and step execution payloads in SQLite text columns using JSON blobs:

1. **`pipeline_runs.metadata`**:
   - Stores root run metadata.
   - Accepts `VideoMetadata.model_dump()` dictionary.
   - Restored via `VideoMetadata.model_validate(json.loads(row["metadata"]))`.

2. **`step_executions.input_payload` & `step_executions.output_payload`**:
   - Stores step execution input & output payload state.
   - Example (Step: `"plan_generation"`): `output_payload` stores `EducationalPlan.model_dump()`.
   - Example (Step: `"asset_rendering"`): `output_payload` stores `RenderManifest.model_dump()` or list of `RenderSegment.model_dump()`.

### Serialization Proof of Code
```python
# Save model into StateLedger
metadata_dict = video_meta.model_dump(mode="json")
run_id = ledger.create_run(slug="two-sum", metadata=metadata_dict)

# Record step start with input model
plan_input_dict = {"slug": "two-sum", "difficulty": "Medium"}
step_id = ledger.record_step_start(run_id, step_name="educational_plan_gen", input_payload=plan_input_dict)

# Record step completion with output model
plan_output_dict = edu_plan.model_dump(mode="json")
ledger.record_step_completion(step_id, output_payload=plan_output_dict)

# Re-hydrate model from StateLedger read record
run_record = ledger.get_run(run_id)
restored_video_meta = VideoMetadata.model_validate(run_record.metadata)

step_record = ledger.get_step_execution(step_id)
restored_edu_plan = EducationalPlan.model_validate(step_record.output_payload)
```

---

## 6. Test Suite Requirements (`tests/models/test_validation.py`)

The acceptance criteria mandate that `pytest tests/models/test_validation.py` actively feeds malformed inputs to models and asserts that `pydantic.ValidationError` is raised.

### Test Categories to Implement
1. **Valid Instantiation & Round-Trip Tests**:
   - `test_video_metadata_valid_instantiation()`
   - `test_educational_plan_valid_instantiation()`
   - `test_render_segment_valid_instantiation()`
   - Verify `model_dump()`, `model_dump_json()`, `model_validate()`, `model_validate_json()`.

2. **Malformed JSON & Missing Required Fields Tests**:
   - `test_video_metadata_missing_title_raises_validation_error()`
   - `test_educational_plan_missing_sections_raises_validation_error()`
   - `test_render_segment_missing_end_time_raises_validation_error()`

3. **Invalid Data Type Tests**:
   - `test_video_metadata_invalid_fps_type_raises_validation_error()` (e.g. passing `"thirty"`)
   - `test_educational_plan_invalid_sections_type_raises_validation_error()`
   - `test_render_segment_invalid_start_time_type_raises_validation_error()`

4. **Semantic Rule Violation Tests**:
   - **Segment Duration / Timestamps**:
     - `test_render_segment_negative_duration_raises_validation_error()`
     - `test_render_segment_end_time_before_start_time_raises_validation_error()`
     - `test_render_segment_duration_mismatch_raises_validation_error()`
     - `test_render_segment_no_assets_raises_validation_error()`
   - **Video Resolution & FPS**:
     - `test_video_metadata_invalid_fps_value_raises_validation_error()` (e.g. `fps=-30`, `fps=0`, `fps=1000`)
     - `test_video_metadata_exceeded_tags_length_raises_validation_error()` (>500 chars total)
     - `test_video_metadata_empty_title_raises_validation_error()` (`title="   "`)
   - **Educational Plan Rules**:
     - `test_educational_plan_invalid_slug_pattern_raises_validation_error()` (e.g. `"Two Sum!"`)
     - `test_educational_plan_duplicate_section_ids_raises_validation_error()`
     - `test_educational_plan_total_duration_mismatch_raises_validation_error()`
     - `test_code_snippet_negative_line_highlight_raises_validation_error()`

5. **State Ledger Integration Integration Test**:
   - `test_state_ledger_model_serialization_roundtrip()` (Verifies end-to-end storing and reading from `StateLedger` SQLite database).

---

## 7. Documentation Requirements (`PromptBook/Phase05/01_Data_Models.md`)

`PromptBook/Phase05/01_Data_Models.md` must be created with the following structured sections:
1. **Document Control & Header**: Purpose, target system, version, canonical status.
2. **Phase 05 Architecture & Design Principles**: Immutability, Pydantic V2 strict type validation, fail-fast boundary validation.
3. **Pydantic V2 Model Schemas & Specifications**:
   - `VideoMetadata` Data Contract table + validation rules.
   - `EducationalPlan`, `PlanSection`, `CodeSnippet`, `VisualCue` Data Contract tables + validation rules.
   - `RenderSegment`, `AssetReference`, `RenderManifest` Data Contract tables + validation rules.
4. **Semantic Validation Rules Specification Matrix**: Clear rule table with rule ID, target field, constraint description, and error type.
5. **1-to-1 State Ledger Mapping Reference**: SQL schema mapping (`pipeline_runs.metadata`, `step_executions.input_payload`, `step_executions.output_payload`) and python snippet for ledger read/write.
6. **Testing & Verification Matrix**: Map of model rules to `tests/models/test_validation.py` test cases.

---

## 8. Summary of Recommendations & Next Steps

1. **Implementer Guidance**:
   - Create `src/core/models/__init__.py`, `video.py`, `plan.py`, `assets.py` strictly using Pydantic V2 (`pydantic.BaseModel`).
   - Re-export all models in `src/core/models/__init__.py`.
   - Ensure imports handle StrEnum / Enum cleanly across Python 3.11+.
2. **Test Suite Guidance**:
   - Create `tests/models/test_validation.py` using `pytest.raises(ValidationError)`.
3. **Documentation Guidance**:
   - Create `PromptBook/Phase05/01_Data_Models.md`.
