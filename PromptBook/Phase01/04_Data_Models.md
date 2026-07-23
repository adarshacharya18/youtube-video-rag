# Phase01/04_Data_Models.md

Author: Principal Software Architect
Target System: Automated DSA Educational YouTube Video Pipeline
Document Version: 1.0.0
Status: Canonical

---

# Table of Contents

1. Purpose
2. Design Principles
3. Naming Conventions
4. Shared Types
5. Enumerations
6. Common Value Objects
7. Module Data Models
8. Serialization Rules
9. Validation Rules
10. Model Relationships
11. Versioning Strategy
12. Future Extensions

---

# 1. Purpose

This document defines every domain model used throughout the pipeline.

It serves as the single source of truth for:

- Dataclasses
- Enums
- Value Objects
- Serialization
- Validation
- Relationships

No pipeline module may invent its own data structure.

All modules communicate exclusively through these models.

---

# 2. Design Principles

Every model must satisfy:

✓ Immutable
✓ Serializable
✓ Type Safe
✓ Self Contained
✓ Independent
✓ JSON Compatible
✓ Versionable

Rules

- frozen=True (for all inter-module models)
- canonical types (e.g. datetime, Path)
- no business logic
- no external dependencies
- no file I/O
- no API calls
- no mutable defaults

---

# 3. Naming Conventions

## Dataclasses

PascalCase

Example
ScrapedProblem
VideoScript
VoiceResult
AnimationResult

---

## Enums

Singular nouns

Difficulty
PipelineStatus
AnimationStyle
SectionType

---

## Collections

Always use

list[T]
dict[K, V]
set[T]

Prefer list[T] for ordered collections. Use tuple[T, ...] only when frozen dataclass immutability requires it (e.g., MemoryRecord.errors).

Never

Any
object

unless explicitly required.

---

# 4. Shared Types

This section defines reusable value objects.

## Example

Purpose
Represents one example from LeetCode.

Ownership
Problem Model

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| input | str | Yes | Example input |
| output | str | Yes | Expected output |
| explanation | str \| None | No | Optional explanation |

Validation
- input cannot be empty
- output cannot be empty

---

## RelatedProblem

Purpose
Represents a suggested practice problem.

Fields

| Field | Type |
|--------|------|
| slug | str |
| title | str |
| difficulty | Difficulty |

Validation
slug must be unique.

---

## RetrievedChunk

Purpose
Single RAG chunk.

Fields

| Field | Type |
|--------|------|
| content | str |
| source_file | str |
| relevance_score | float |
| chunk_index | int |

Validation
0 <= relevance_score <= 1

---

## Null Object Factories

### TagKnowledge.empty()
Purpose: Factory method providing a Null Object pattern for TagKnowledge. Used by the Orchestrator when Tag Explorer module fails (graceful degradation).
Returns `TagKnowledge` with default fields:
- `primary_pattern` = "General"
- `prerequisites` = []
- `related_problems` = []
- `animation_style` = AnimationStyle.TEXT_EXPLANATION

### RAGContext.empty()
Purpose: Factory method providing a Null Object pattern for RAGContext. Used by the Orchestrator when RAG Engine fails (graceful degradation).
Returns `RAGContext` with default fields:
- `slug` = ""
- `retrieved_chunks` = []
- `query_used` = ""
- `total_chunks_searched` = 0
- `retrieval_time_ms` = 0.0
- `retrieved_at` = datetime.utcnow()

---

# 5. Enumerations

---

## Difficulty

Purpose
Represents LeetCode difficulty.

Values
- EASY
- MEDIUM
- HARD

---

## PipelineStatus

Purpose
Tracks the state of a run for memory and telemetry.

Values
- PENDING
- RUNNING
- COMPLETED
- PARTIAL_FAILURE
- FAILED

---

## AnimationStyle

Purpose
Determines the class of Manim scene to invoke. (Note: AnimationStyle serves as a suggestion from the Tag Explorer. The VisualParams union discriminator is authoritative for scene selection).

Values
- ARRAY_TRAVERSAL
- LINKED_LIST
- TREE_RECURSION
- GRAPH_BFS
- GRAPH_DFS
- HASH_MAP
- STACK_QUEUE
- TWO_POINTERS
- SLIDING_WINDOW
- DYNAMIC_PROGRAMMING
- CODE_HIGHLIGHT
- COMPLEXITY_CHART

---

## SectionType

Purpose
Identifies the structural role of a script segment.

Values
- HOOK
- PROBLEM_STATEMENT
- CONSTRAINTS
- BRUTE_FORCE
- OPTIMIZED_APPROACH
- VISUAL_WALKTHROUGH
- DRY_RUN
- CODE_WALKTHROUGH
- COMPLEXITY_ANALYSIS
- CLOSING

---

# 6. Common Value Objects

## ScriptSection

Purpose
A specific segment of the final video script.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| section_id | str | Yes | Unique ID (e.g., "hook") |
| section_type | SectionType | Yes | Structural role |
| narration | str | Yes | Text to be spoken |
| visual_params | VisualParams | Yes | Manim instructions (Union Type) |
| estimated_duration_seconds | float | Yes | Estimated length of section |
| order | int | Yes | Ordered index (0-9) |

Validation
- narration cannot be empty
- section_id must be unique across the script

---

## SEOMetadata

Purpose
YouTube upload fields.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| title | str | Yes | Video title (max 100 chars) |
| description | str | Yes | Video description |
| tags | list[str] | Yes | YouTube tags (max 500 chars total) |
| category_id | int | Yes | Default: 27 (Education) |
| chapter_timestamps | list[str] | Yes | Video chapters for description |

Validation
- title length <= 100

---

## SectionAudio

Purpose
Audio output for a single script section.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| section_id | str | Yes | Unique ID |
| audio_path | Path | Yes | Path to file |
| duration_seconds | float | Yes | Audio length |
| word_count | int | Yes | Word count |

Validation
- duration_seconds > 0
- word_count >= 0

---

## SectionClip

Purpose
Video output for a single script section.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| section_id | str | Yes | Unique ID |
| video_path | Path | Yes | Path to file |
| duration_seconds | float | Yes | Video length |

Validation
- duration_seconds > 0

---

# 7. Module Data Models

## M1: ScrapedProblem

Purpose
Raw data extracted from LeetCode.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| slug | str | Yes | Canonical ID |
| title | str | Yes | Human-readable title |
| number | int | Yes | Problem number on LeetCode |
| difficulty | Difficulty | Yes | Problem difficulty |
| description | str | Yes | Markdown description |
| constraints | list[str] | Yes | Problem bounds |
| examples | list[Example] | Yes | I/O test cases |
| tags | list[str] | Yes | LeetCode tags |
| accepted_code | str | Yes | Optimal solution |
| code_language | str | Yes | Language of the solution |
| scraped_at | datetime | Yes | Timestamp of scrape |

---

## M2: TagKnowledge

Purpose
Enriched algorithmic understanding of the problem.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| primary_pattern | str | Yes | Core algorithm family |
| prerequisites | list[str] | Yes | Concepts to know first |
| related_problems | list[RelatedProblem] | Yes | Recommended next steps |
| animation_style | AnimationStyle | Yes | Suggested visual approach |

---

## M3: RAGContext

Purpose
Relevant explanations fetched from the local knowledge base.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| slug | str | Yes | Canonical ID |
| retrieved_chunks | list[RetrievedChunk] | Yes | Filtered chunks |
| query_used | str | Yes | Search query |
| total_chunks_searched | int | Yes | Number of chunks in vector space |
| retrieval_time_ms | float | Yes | Query performance |
| retrieved_at | datetime | Yes | Retrieval timestamp |

---

## M4: VideoScript

Purpose
The finalized JSON blueprint for the video generation.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| slug | str | Yes | The target problem |
| title | str | Yes | Human-readable title |
| difficulty | Difficulty | Yes | Problem difficulty |
| seo_metadata | SEOMetadata | Yes | YouTube data |
| sections | list[ScriptSection] | Yes | Ordered list of segments |
| generated_at | datetime | Yes | Generation timestamp |

---

## M5: VoiceResult

Purpose
Paths to generated audio assets.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| slug | str | Yes | The target problem |
| section_audio | list[SectionAudio] | Yes | Audio file metadata |
| total_duration_seconds | float | Yes | Total length |
| sample_rate | int | Yes | Hz (e.g. 24000) |
| model_used | str | Yes | TTS model |
| generated_at | datetime | Yes | Generation timestamp |

---

## M6: AnimationResult

Purpose
Paths to generated visual assets.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| slug | str | Yes | The target problem |
| section_clips | list[SectionClip] | Yes | Generated video files |
| resolution | str | Yes | e.g. "1920x1080" |
| fps | int | Yes | Frames per second |
| theme | str | Yes | Theme used |
| rendered_at | datetime | Yes | Render timestamp |

---

## M7: AssembledVideo

Purpose
Final artifacts ready for upload.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| slug | str | Yes | The target problem |
| video_path | Path | Yes | Complete .mp4 path |
| thumbnail_path | Path | Yes | Extracted .png path |
| duration_seconds | float | Yes | Final length |
| file_size_bytes | int | Yes | Size of video |
| assembled_at | datetime | Yes | Assembly timestamp |

---

## M8: UploadResult

Purpose
Confirmation of YouTube publication.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| slug | str | Yes | The target problem |
| youtube_video_id | str | Yes | 11-character ID |
| youtube_url | str | Yes | Public link |
| privacy_status | str | Yes | e.g. "public", "unlisted" |
| uploaded_at | datetime | Yes | Upload timestamp |

---

## M9: MemoryRecord

Purpose
Historical pipeline execution data.

Fields

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| slug | str | Yes | Target problem |
| problem_number | int | Yes | LeetCode number |
| title | str | Yes | Problem title |
| difficulty | Difficulty | Yes | Problem difficulty |
| tags | list[str] | Yes | LeetCode tags |
| primary_pattern | str | Yes | Core algorithm |
| script_hash | str | Yes | Hash for cache |
| voice_duration_seconds | float | Yes | Audio length |
| video_duration_seconds | float | Yes | Video length |
| file_size_bytes | int | Yes | MP4 size |
| youtube_video_id | str \| None | No | YouTube video ID |
| youtube_url | str \| None | No | Public link |
| status | PipelineStatus | Yes | Run outcome |
| errors | tuple[str, ...] | Yes | Error IDs |
| started_at | datetime | Yes | ISO8601 Timestamp |
| completed_at | datetime \| None | No | ISO8601 Timestamp |

---

# 8. Serialization Rules

1. JSON Format: All models must natively serialize to JSON strings to support file-caching.
2. Datetimes: Time values must strictly adhere to `ISO 8601` string format (e.g., `YYYY-MM-DDTHH:MM:SSZ`) when serialized.
3. Enumerations: Enums serialize to their underlying string names (e.g., `Difficulty.EASY` -> `"EASY"`).
4. Indentation: JSON files written to disk should be formatted with 4 spaces for readability.

---

# 9. Validation Rules

1. Validation Timing: Validation occurs strictly upon object instantiation using either `pydantic.dataclasses` or explicitly within `__post_init__` methods.
2. Fail Fast: Invalid types or missing fields must raise a `TypeError` or `ValueError` immediately, blocking the object from being constructed.
3. Path Strings: Any field representing a file path must point to an absolute or pipeline-relative path, but the dataclass itself does not verify filesystem existence (that is the Orchestrator/module's job).
4. Code Language Default: `ScrapedProblem.code_language` should be validated to be in the set of supported languages (e.g., "cpp").

---

# 10. Model Relationships

Models are structured as an additive pipeline tree. A single run originates from a `slug`. 

- `ScrapedProblem` is the root node.
- `TagKnowledge` and `RAGContext` derive purely from `ScrapedProblem`.
- `VideoScript` is an aggregation node, deriving from `ScrapedProblem`, `TagKnowledge`, and `RAGContext`.
- `VoiceResult` and `AnimationResult` derive from `VideoScript`.
- `AssembledVideo` aggregates `VoiceResult` and `AnimationResult`.
- `UploadResult` derives from `AssembledVideo` and `VideoScript` (for SEO).
- `MemoryRecord` acts as the archival wrapper for the entire run tree.

---

# 11. Versioning Strategy

1. Immutability: Deleting or mutating the type of existing fields is strictly forbidden.
2. Additive Changes: New fields can be added but must have a sensible default or be typed as `Optional[T]` (`| None`).
3. Structural Upgrades: If a breaking change is required, a new protocol model must be created (e.g., `VideoScriptV2`) and the Orchestrator updated to route appropriately.

---

# 12. Future Extensions

- Support for Pydantic `Field` validation constraints (`min_length`, `regex`) if simple dataclasses prove too brittle.
- `TelemetryMetrics` model to track NPU load, RAM usage, and runtime durations for individual sections.
- `ThumbnailConfig` model to decouple visual parameters for the YouTube thumbnail generator when extracted from Assembly.
