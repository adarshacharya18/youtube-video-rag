# Phase 06 Technical Exploration Analysis: LLM Provider Abstraction

## 1. Executive Summary
This analysis details the current codebase architecture, Pydantic V2 data models from Phase 05, existing base abstractions/exceptions, and package environment status to prepare for Phase 06 (LLM Provider Abstraction). `src/core/llm/` and `tests/llm/` do not currently exist and must be implemented. LangChain dependencies (`langchain`, `langchain-openai`, `langchain-anthropic`) are currently missing from `.venv` and must be declared in `requirements.txt` and `pyproject.toml`.

---

## 2. Base Architecture & Core Utilities Survey

### 2.1 Protocols & Building Blocks (`src/core/base.py`)
- **`Provider[T_co]` (Protocol)**: Generic read-only access protocol (`def provide(self) -> T_co`).
- **`BasePipelineResult[T]`**: Standardized dataclass encapsulating `success`, `data`, `error`, `error_message`, `execution_time_ms`, and `timestamp`.
- **`PipelineModule[T_contra, T_co]`**: Core protocol for pipeline stages (`def execute(self, payload: T_contra) -> T_co`).

### 2.2 Exception Hierarchy (`src/core/exceptions.py`)
- **Base Exception**: `PipelineError` (inherits from standard `Exception`).
- **Operational Categories**:
  - `RetryableError(PipelineError)`: Marker for transient issues (e.g. rate limits, timeouts).
    - `RateLimitError(RetryableError)`: 429 Too Many Requests.
    - `NetworkError(RetryableError)`: TCP/HTTP connection timeouts.
  - `FatalError(PipelineError)`: Marker for unrecoverable errors.
    - `ValidationError(FatalError)`: Data schema failure (e.g., malformed LLM JSON).
    - `ConfigurationError(FatalError)`: Missing/invalid environment variables.
    - `AuthenticationError(FatalError)`: Invalid API keys.

### 2.3 Configuration Management (`src/core/config.py`)
- Uses `pydantic_settings.BaseSettings` with `env_nested_delimiter="__"`.
- `PipelineConfig` holds module configs (`ScraperConfig`, `RAGConfig`, `GeminiConfig`, `YouTubeConfig`).
- **Phase 06 Recommendation**: Implement `LLMConfig` (or `OpenAIConfig` and `AnthropicConfig`) in `src/core/config.py` to store model names, API key secret fields, max retries, timeout parameters, and temperature settings.

### 2.4 Structured Logging (`src/core/logger.py`)
- Uses `structlog` bound logger (`get_logger(__name__)`).
- Provides execution timing context manager (`log_execution_time`).

---

## 3. Phase 05 Pydantic V2 Data Models Survey (`src/core/models/`)

The LLM Provider Abstraction must strictly output instances of these Phase 05 Pydantic V2 schemas.

### 3.1 Video Models (`src/core/models/video.py`)
- `VideoResolution` (StrEnum: `720p`, `1080p`, `1440p`, `4K`).
- `TargetPlatform` (StrEnum: `youtube`, `youtube_shorts`, `tiktok`).
- `PrivacyStatus` (StrEnum: `public`, `unlisted`, `private`).
- `Difficulty` (StrEnum: `EASY`, `MEDIUM`, `HARD`).
- `SEOMetadata`: `youtube_title` (1-100 chars), `youtube_description` (1-5000 chars), `tags` (total char count <= 500), `category_id`, `privacy_status`, `chapter_timestamps`.
- `VideoMetadata`: `title`, `description`, `slug` (regex `^[a-z0-9-]+$`), `resolution`, `width`, `height`, `fps` (one of `{24, 25, 30, 50, 60, 120}`), `tags`, `target_platform`, `difficulty`, `seo_metadata`. Includes automatic resolution & dimension alignment validator.

### 3.2 Educational Plan Models (`src/core/models/plan.py`)
- `PlanSection`: `section_id`, `section_type`, `title`, `narration`, `estimated_duration` (finite float > 0), `visual_cue_ids`, `order`.
- `CodeSnippet`: `snippet_id`, `language`, `code`, `explanation`, `line_highlights` (1-based integer list).
- `VisualCue`: `cue_id`, `animation_type`, `description`, `parameters`.
- `ConceptPrerequisite`: `concept`, `description`.
- `LearningObjective`: `objective_id`, `description`, `taxonomic_level`.
- `EducationalPlan`: `topic`, `slug` (regex `^[a-z0-9-]+$`), `target_audience`, `difficulty`, `learning_objectives`, `prerequisites`, `sections` (non-empty list), `code_snippets`, `visual_cues`, `estimated_total_duration`. Enforces invariants: unique `section_id` check across sections, and `estimated_total_duration` matching sum of section durations within 0.1s tolerance.

### 3.3 Asset & Render Manifest Models (`src/core/models/assets.py`)
- `AssetReference`: `asset_id`, `asset_type`, `file_path`, `duration`.
- `AudioAsset`: `audio_id`, `file_path`, `duration_seconds`, `sample_rate`, `voice_model`.
- `VideoAsset`: `asset_id`, `file_path`, `duration_seconds`, `resolution`, `fps`, `file_size_bytes`.
- `RenderSegment`: `segment_id`, `segment_type` (one of `{"intro", "code_walkthrough", "visual_anim", "outro", "narration"}`), `start_time`, `end_time` (> start_time), `duration` (= end_time - start_time), `asset_references`, `audio_path`, `visual_path`, `narration_text`, `volume`, `transition_in`, `transition_out`, `audio_asset`, `scene_type`, `visual_parameters`. Must contain at least one asset reference.
- `RenderManifest`: `pipeline_run_id`, `slug`, `segments` (non-empty), `total_duration`.
- `AssembledVideo`: `slug`, `final_video_path`, `thumbnail_path`, `total_duration_seconds`, `file_size_bytes`, `segments`, `assembled_at`.

---

## 4. Current Gaps and Target Phase 06 Architecture

### 4.1 Missing Components
1. **`src/core/llm/` Directory**: Missing entirely.
   - `provider.py`: Define `BaseLLMProvider` abstract class / protocol with structured generation interface.
   - `openai_client.py`: Implement concrete `OpenAIProvider` wrapping LangChain's `ChatOpenAI` + `.with_structured_output()`.
   - `anthropic_client.py`: Implement concrete `AnthropicProvider` wrapping LangChain's `ChatAnthropic` + `.with_structured_output()`.
2. **`tests/llm/` Directory**: Missing entirely.
   - `test_providers.py`: Implement unit tests using mocked API responses for both OpenAI and Anthropic, verifying structured Pydantic object generation and error handling.
3. **Documentation Deliverable**: `PromptBook/Phase06/01_LLM_Abstraction.md`.

### 4.2 Target LLM Abstraction Design Strategy
- **LangChain Core Integration**: Use `BaseChatModel` from `langchain_core.language_models` and `.with_structured_output(schema=ModelClass)`.
- **Resiliency & Retry**: Use exponential backoff for transient errors (`RateLimitError`, `NetworkError`, HTTP 429/5xx).
- **Error Normalization**: Catch provider-specific exceptions (e.g. `openai.RateLimitError`, `anthropic.RateLimitError`) and re-raise as domain exceptions (`src.core.exceptions.RateLimitError`, `src.core.exceptions.ValidationError`).
- **Structured Schema Enforcer**: Guarantee identical output schemas (`EducationalPlan`, `VideoMetadata`, `RenderManifest`) regardless of backend model.

---

## 5. Dependencies Assessment

### 5.1 Currently Installed in `.venv`
- `pydantic`: `2.13.4`
- `pydantic-settings`: `2.14.2`
- `pytest`: `9.1.1`
- `pytest-cov`: `7.1.0`
- `structlog`: `26.1.0`

### 5.2 Missing Dependencies (Action Required)
- `langchain`
- `langchain-core`
- `langchain-openai`
- `langchain-anthropic`
- `openai`
- `anthropic`

These dependencies must be added to `requirements.txt` and `pyproject.toml` and installed into the environment before Phase 06 implementation begins.
