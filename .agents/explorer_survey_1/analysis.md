# Codebase Survey Analysis for Phase 08 (The Workflow Engine)

## Executive Summary
This analysis details the structural and architectural state of the `src/` codebase in preparation for implementing **Phase 08: The Workflow Engine**. 

Key findings:
1. **SQLite State Ledger**: Implemented in `src/core/orchestrator/state_ledger.py` with comprehensive unit and crash recovery tests (`tests/orchestrator/test_state_ledger.py`). It uses SQLite in WAL mode with transactional thread locking.
2. **Workflow Engine Directory**: `src/core/workflow/` currently **does not exist** and must be created along with `node.py` and `engine.py`.
3. **Core Base Classes & Protocols**: `src/core/base.py` provides runtime-checkable protocols (`PipelineModule`, `Service`, `Repository`, `Provider`, `Factory`, `Command`, `Configuration`, `Lifecycle`, `Validator`) and `BasePipelineResult[T]`.
4. **Exception Hierarchy**: `src/core/exceptions.py` defines `PipelineError` as root, categorized into operational impacts (`RetryableError`, `FatalError`) and domain errors (`PipelineValidationError`, `PipelineStageError`, etc.).
5. **Pydantic Models**: `src/core/models/` contains Pydantic V2 models (`video.py`, `plan.py`, `assets.py`) providing data contracts for `VideoMetadata`, `EducationalPlan`, `RenderSegment`, and `RenderManifest`.
6. **Config Loader**: `src/core/config.py` provides `PipelineConfig` and `load_config()` using `pydantic_settings.BaseSettings` with nested environment variable parsing (`env_nested_delimiter="__"`).

---

## 1. Codebase Inventory (`src/` and `src/core/`)

### 1.1 `src/core/` Directory Layout
- `src/core/__init__.py`: Package initialization.
- `src/core/base.py`: Core protocols and generic result data structures.
- `src/core/config.py`: Centralized Pydantic-Settings configuration module.
- `src/core/exceptions.py`: Centralized exception hierarchy.
- `src/core/logger.py`: Structlog-based structured logging initialization.
- `src/core/ingestion/`: Parser, sanitizer, and models for LeetCode markdown ingestion (`models.py`, `parser.py`, `sanitizer.py`).
- `src/core/llm/`: Provider abstraction and prompt loading (`provider.py`, `openai_client.py`, `anthropic_client.py`, `prompt_loader.py`, `prompts/v1/`).
- `src/core/models/`: Pydantic V2 schemas (`video.py`, `plan.py`, `assets.py`).
- `src/core/orchestrator/`: **Contains SQLite State Ledger** (`state_ledger.py`).
- `src/core/rag/`: RAG engine and vector store abstractions (`embedder.py`, `vector_store.py`).
- `src/core/workflow/`: **NOT PRESENT** (Needs creation for Phase 08).

### 1.2 Other Subdirectories under `src/`
- `src/animation/`: Manim scene definitions (`renderer.py`, `scenes/`).
- `src/assembly/`: FFmpeg video assembly (`assembler.py`, `ffmpeg_commands.py`).
- `src/cli/`: CLI interfaces (`ingestion_cli.py`, `content_cli.py`, `rag_cli.py`, `organization_cli.py`, `ops.py`, `evolve.py`).
- `src/memory/`: Memory store definitions (`store.py`).
- `src/models/`: Domain legacy models (`problem.py`, `enums.py`, etc.).
- `src/orchestrator/`: Empty placeholders (`pipeline.py`, `checkpoint.py`).
- `src/plugins/`, `src/rag/`, `src/scraper/`, `src/script/`, `src/tags/`, `src/voice/`, `src/youtube/`: Legacy/specialized feature modules.

---

## 2. SQLite State Ledger API & Schema Analysis

### 2.1 Location
- **Implementation File**: `src/core/orchestrator/state_ledger.py`
- **Test File**: `tests/orchestrator/test_state_ledger.py`

### 2.2 Schema Definitions

#### Table: `pipeline_runs`
```sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
    pipeline_run_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_slug ON pipeline_runs(slug);
```
- `pipeline_run_id`: Format `run_<32-char-hex-uuid>`.
- `slug`: Problem/video slug (e.g. `two-sum`).
- `status`: String representation of `StepStatus` enum (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`).
- `metadata`: JSON string or NULL.

#### Table: `step_executions`
```sql
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
```
- `step_execution_id`: Format `step_<32-char-hex-uuid>`.
- `pipeline_run_id`: Foreign key referencing `pipeline_runs(pipeline_run_id)`.
- `step_name`: Name of step/node (e.g., `scraper`, `plan`, `script`, `render`).
- `status`: String representation of `StepStatus` enum (`IN_PROGRESS`, `COMPLETED`, `FAILED`).
- `input_payload` / `output_payload` / `error_details`: JSON strings or NULL.

### 2.3 SQLite PRAGMA Configuration
- `PRAGMA journal_mode=WAL;` (Write-Ahead Logging for high concurrency and crash resilience).
- `PRAGMA synchronous=NORMAL;` (Optimal durability with reduced sync overhead).
- `PRAGMA foreign_keys=ON;` (Enforces referential integrity on `pipeline_run_id`).
- `PRAGMA busy_timeout=5000;` (5-second lock timeout).

### 2.4 Data Structures & Enums
```python
class StepStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# Standard aliases provided for backward compatibility:
PipelineStatus = StepStatus
RunStatus = StepStatus
Status = StepStatus

@dataclass
class PipelineRunRecord:
    pipeline_run_id: str
    slug: str
    status: StepStatus
    created_at: str  # ISO 8601 UTC timestamp
    updated_at: str  # ISO 8601 UTC timestamp
    metadata: dict[str, Any] | None = None

@dataclass
class StepExecutionRecord:
    step_execution_id: str
    pipeline_run_id: str
    step_name: str
    status: StepStatus
    created_at: str  # ISO 8601 UTC timestamp
    updated_at: str  # ISO 8601 UTC timestamp
    input_payload: dict[str, Any] | None = None
    output_payload: dict[str, Any] | None = None
    error_message: str | None = None
    error_details: dict[str, Any] | None = None
```

### 2.5 State Ledger Class API Methods
The `StateLedger` class is thread-safe using an internal `threading.Lock()`.

| Method | Signature | Description | State Transitions |
|---|---|---|---|
| `__init__` | `(db_path: str \| Path)` | Opens SQLite DB, sets PRAGMAs, creates tables if needed. | N/A |
| `create_run` | `(slug: str, metadata: dict \| None = None) -> str` | Creates a new pipeline run record. Returns `pipeline_run_id`. | Sets run status to `PENDING`. |
| `get_run` | `(pipeline_run_id: str) -> PipelineRunRecord \| None` | Retrieves run record by ID. | N/A |
| `get_run_by_slug` | `(slug: str) -> PipelineRunRecord \| None` | Retrieves latest run record by slug (`ORDER BY created_at DESC LIMIT 1`). | N/A |
| `record_step_start` | `(pipeline_run_id: str, step_name: str, input_payload: dict \| None = None) -> str` | Records step start. Returns `step_execution_id`. | Inserts step as `IN_PROGRESS`. If run is `PENDING`, updates run status to `IN_PROGRESS`. |
| `record_step_completion` | `(step_execution_id: str, output_payload: dict \| None = None) -> None` | Records successful step completion. | Updates step status to `COMPLETED` and saves `output_payload`. |
| `record_step_failure` | `(step_execution_id: str, error_message: str, error_details: dict \| None = None) -> None` | Records step failure. | Updates step status to `FAILED`. **Automatically updates parent run status to `FAILED`**. |
| `get_completed_steps` | `(pipeline_run_id: str) -> dict[str, StepExecutionRecord]` | Returns dict mapping `step_name -> StepExecutionRecord` for all `COMPLETED` steps. | N/A |
| `get_step_execution` | `(step_execution_id: str) -> StepExecutionRecord \| None` | Retrieves step execution record by ID. | N/A |
| `close` | `() -> None` | Closes SQLite connection cleanly. | N/A |
| Context Manager | `__enter__` / `__exit__` | Enables standard Python `with StateLedger(...) as ledger:` usage. | Closes connection on exit. |

---

## 3. Examination of Workflow & Node Structures

### 3.1 Existing Directory State
- Directory `src/core/workflow/` **does not exist** on disk.

### 3.2 Phase 08 Design & Implementation Requirements
Based on Phase 08 specifications (`ORIGINAL_REQUEST.md` lines 152-182):
1. **Abstract `Node` Class (`src/core/workflow/node.py`)**:
   - Must define abstract `Node` base class.
   - Nodes must communicate strictly via reading from and writing to the `StateLedger` using a `run_id`.
   - No passing in-memory state objects down the chain (enforces pipeline idempotency & crash recoverability).
2. **Fault-Tolerant Engine (`src/core/workflow/engine.py`)**:
   - Must implement `WorkflowEngine` to execute sequence of nodes.
   - Must wrap each node execution in try/except blocks.
   - If a node throws an exception, engine must capture it, log it, update the step execution and parent pipeline run status to `FAILED` via `StateLedger.record_step_failure()`, and prevent application crash.
3. **Test Suite (`tests/workflow/test_engine.py`)**:
   - Must test node sequence execution.
   - Must use mock nodes that throw exceptions to verify that the engine catches exceptions and sets State Ledger status to `FAILED`.

---

## 4. Core Foundation Components (`src/core/`)

### 4.1 Base Protocols (`src/core/base.py`)
- `BasePipelineResult[T]`: Data class returning `(success, data, error, error_message, execution_time_ms, timestamp)`.
- `@runtime_checkable` Protocols:
  - `PipelineModule[T_contra, T_co]`: Defines `execute(payload: T_contra) -> T_co`.
  - `Service`: Marker protocol for domain services.
  - `Repository[T]`: Storage contract (`get`, `save`, `delete`).
  - `Provider[T_co]`: External resource reader (`provide()`).
  - `Factory[T_co]`: Object creator (`create(**kwargs)`).
  - `Command`: Command pattern encapsulation (`execute()`).
  - `Configuration`: Post-init validator (`validate_config()`).
  - `Lifecycle`: Startup/shutdown hooks (`initialize()`, `shutdown()`).
  - `Validator[T_contra]`: Target validator (`validate(target)`).

### 4.2 Exceptions (`src/core/exceptions.py`)
- Root class: `PipelineError(Exception)`
- Operational classifications:
  - `RetryableError(PipelineError)` (transient errors like network timeouts, 429 rate limits).
  - `FatalError(PipelineError)` (unrecoverable errors like bad credentials, schema validation failures).
- Infrastructure & Core:
  - `ConfigurationError(FatalError)`
  - `ValidationError(FatalError)` / `PipelineValidationError(ValidationError)`
  - `PipelineStageError(FatalError)`
  - `NetworkError(RetryableError)`
  - `AuthenticationError(FatalError)`
  - `RateLimitError(RetryableError)`
- Module specific:
  - `ScraperError` / `ProblemNotFoundError`
  - `TagExplorerError`
  - `RAGError` / `IndexNotFoundError` / `EmbeddingError` / `KnowledgeConflictError`
  - `ScriptGenerationError` / `PromptTemplateError` / `TemplateNotFoundError` / `TemplateRenderError`
  - `VoiceGenerationError`
  - `AnimationError`
  - `AssemblyError`
  - `YouTubeUploadError`

### 4.3 Pydantic Models (`src/core/models/`)
All models inherit from Pydantic V2 `BaseModel` and enforce strict validation rules.

- **`video.py`**:
  - `VideoResolution`: `StrEnum` (`720p`, `1080p`, `1440p`, `4K`).
  - `TargetPlatform`: `StrEnum` (`youtube`, `youtube_shorts`, `tiktok`).
  - `PrivacyStatus`: `StrEnum` (`public`, `unlisted`, `private`).
  - `Difficulty`: `StrEnum` (`EASY`, `MEDIUM`, `HARD`).
  - `SEOMetadata`: SEO fields (youtube_title, youtube_description, tags, category_id, chapter_timestamps).
  - `VideoMetadata`: Core video model aligned with pipeline state ledger (slug pattern `^[a-z0-9-]+$`, FPS validation, resolution alignment validator).
- **`plan.py`**:
  - `PlanSection`: Section ID, type, title, narration, duration (>0), visual_cue_ids, order.
  - `CodeSnippet`: Snippet ID, language, code, line_highlights (1-indexed).
  - `VisualCue`: Cue ID, animation_type, description, parameters.
  - `ConceptPrerequisite` & `LearningObjective`: Required educational goals and prerequisites.
  - `EducationalPlan`: Full plan model (slug pattern `^[a-z0-9-]+$`, total duration invariant validation matching sum of sections within 0.1s tolerance).
- **`assets.py`**:
  - `AssetReference`: Reference to media files with finite float duration validation.
  - `AudioAsset`: Audio path, sample rate, voice model, duration.
  - `VideoAsset`: Video path, resolution, fps, duration, file size.
  - `RenderSegment`: Detailed timeline segment (`segment_type` in `{"intro", "code_walkthrough", "visual_anim", "outro", "narration"}`, start/end time duration match within 1e-3 tolerance, asset presence validator).
  - `RenderManifest`: Pipeline run ID, slug, timeline segments list, total duration.
  - `AssembledVideo`: Final output video artifact.

### 4.4 Configuration Loader (`src/core/config.py`)
- Root model: `PipelineConfig(BaseSettings)`
- Nested settings classes:
  - `ScraperConfig`
  - `RAGConfig`
  - `GeminiConfig`
  - `YouTubeConfig`
  - `OpenAIConfig`
  - `AnthropicConfig`
  - `PromptConfig`
  - `LLMConfig`
- Loader function: `load_config(env_file=None, overrides=None) -> PipelineConfig`
  - Reads `ENVIRONMENT` variable (`development`, `testing`, `production`).
  - Automatically loads `.env.{environment}` or fallback `.env`.
  - Supports programmatic dictionary overrides with `_deep_merge()`.
  - Nested env var parsing via `env_nested_delimiter="__"` (e.g. `SCRAPER__TIMEOUT_SECONDS=20`).

---

## 5. Summary of Test Verification
Ran pytest command: `pytest tests/core tests/models tests/llm tests/orchestrator`
- **Results**: 87 passed in 2.61s.
- `tests/orchestrator/test_state_ledger.py`: All 9 test cases passed (DB init, WAL PRAGMAs, in-memory DB, run creation, success step lifecycle, failure step lifecycle & parent run update, exception handling, same-process crash recovery, multi-process SIGKILL crash recovery, concurrent thread safety).
