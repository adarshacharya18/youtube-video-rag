# Specification Extraction Analysis — Phase 06: LLM Provider Abstraction

**Agent Identity**: `spec_miner_survey_3`  
**Date**: 2026-07-26  
**Target Phase**: Phase 06 (LLM Provider Abstraction)  
**Working Directory**: `/home/adarsh/Documents/Youtube-Channel/.agents/spec_miner_survey_3`  

---

## 1. Executive Summary & Scope

Phase 06 establishes a unified, resilient LLM Provider Abstraction layer for the Automated DSA Educational YouTube Video Pipeline. The abstraction wraps external LLM providers (specifically **OpenAI** and **Anthropic**) using LangChain's `BaseChatModel` and `with_structured_output` mechanism.

The primary objective is to enforce strict schema validation against the Pydantic V2 models developed in Phase 05 (`EducationalPlan`, `VideoMetadata`, `RenderSegment`, `RenderManifest`, etc.), while providing transparent resiliency (retry with exponential backoff on rate limits and network errors).

---

## 2. Verbatim Phase 06 Requirements

Source: `/home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md` (Section `2026-07-26T04:11:31Z`)

> **Implement Phase 06: LLM Provider Abstraction for the Automated DSA Educational YouTube Video Pipeline.**  
> Create a unified, resilient Python interface wrapping external LLMs (OpenAI, Anthropic) that enforces strict structured output using the Pydantic models defined in Phase 05.

### Requirements

* **R1. Unified Provider Interface via LangChain**  
  Implement `src/core/llm/provider.py` defining the interface. Implement the concrete classes `src/core/llm/openai_client.py` and `src/core/llm/anthropic_client.py`. You must utilize LangChain's `BaseChatModel` and `with_structured_output` as the underlying abstraction engine to avoid reinventing the wheel.

* **R2. Resiliency & Structured Output**  
  The clients must gracefully handle rate limits and API failures via built-in retry/backoff logic. They must seamlessly integrate with the Phase 05 Pydantic models to guarantee identically structured output regardless of the active provider.

* **R3. Abstraction Strategy Documentation**  
  Document the provider strategy, retry logic, and fallback mechanisms in `PromptBook/Phase06/01_LLM_Abstraction.md`.

* **R4. Subagent Execution Rules**  
  Do not ask for permission before running terminal commands, unless the command involves handling sensitive data.

### Acceptance Criteria

* **Verification & Testing**  
  - [ ] Running `pytest tests/llm/test_providers.py` executes successfully. The test suite MUST use mocked API responses for both OpenAI and Anthropic, and strictly assert that both providers return identical Pydantic objects based on the Phase 05 schemas.
  - [ ] `src/core/llm/provider.py`, `openai_client.py`, and `anthropic_client.py` exist and successfully leverage LangChain's structured output abstraction.

* **Documentation**  
  - [ ] `PromptBook/Phase06/01_LLM_Abstraction.md` exists and clearly documents the LangChain abstraction strategy and resiliency configurations.

---

## 3. Features Discovered & Specification Matrix

## Features Discovered
| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Provider Abstract | `LLMProvider` Abstract Base/Protocol | Unified interface for LLM operations enforcing structured output | Prompt (str/list), response_model (Pydantic BaseModel class), parameters (temp, timeout) | Instance of response_model | Raises `PipelineError`, `ValidationError`, `RateLimitError`, `NetworkError` | Requirement R1, `src/core/base.py` |
| 2 | Concrete Client | `OpenAIClient` | Concrete LLM client using `langchain_openai.ChatOpenAI` and `with_structured_output` | Prompt string/messages, target Pydantic schema, model parameters | Validated Pydantic model instance | Catches API errors, retries, raises `RateLimitError`/`NetworkError`/`ValidationError` | Requirement R1, R2 |
| 3 | Concrete Client | `AnthropicClient` | Concrete LLM client using `langchain_anthropic.ChatAnthropic` and `with_structured_output` | Prompt string/messages, target Pydantic schema, model parameters | Validated Pydantic model instance | Catches API errors, retries, raises `RateLimitError`/`NetworkError`/`ValidationError` | Requirement R1, R2 |
| 4 | Resiliency | Built-in Retry / Exponential Backoff | Automatic retries on rate limits (429) and transient network failures | Provider API calls, configurable max_retries, backoff factors | Successful response or exhausted retries | Raises `RateLimitError` or `NetworkError` upon max retries | Requirement R2, `src/core/exceptions.py` |
| 5 | Structured Output | Pydantic Schema Integration | Guaranteed schema adherence via LangChain `with_structured_output(schema)` | Phase 05 Pydantic V2 models (`EducationalPlan`, `VideoMetadata`, etc.) | Instantiated, validated Pydantic object matching schema | Raises `ValidationError` if LLM output fails model constraints | Requirement R1, R2, Phase 05 Models |
| 6 | Documentation | Strategy & Resiliency Guide | Comprehensive architectural documentation of LLM abstraction | Technical specs, retry flowcharts, provider configuration details | `PromptBook/Phase06/01_LLM_Abstraction.md` markdown document | N/A (Documentation file) | Requirement R3 |
| 7 | Testing | Unified Provider Unit Test Suite | Test suite verifying provider abstraction using mocked API responses | Mocked API client responses for OpenAI & Anthropic, test prompts, schemas | Identical Pydantic object assertions | Test failures on mismatched outputs or missing retry behaviors | Acceptance Criteria, `tests/` |

---

## 4. Pydantic Models Compatibility Analysis (`src/core/models/`)

Phase 06 clients MUST seamlessly accept and hydrate all Phase 05 Pydantic V2 models. The model suite resides in `src/core/models/` and consists of 18 classes re-exported via `src/core/models/__init__.py`:

### `src/core/models/video.py`
1. **`VideoResolution` (StrEnum)**: `720p`, `1080p`, `1440p`, `4K`.
2. **`TargetPlatform` (StrEnum)**: `youtube`, `youtube_shorts`, `tiktok`.
3. **`PrivacyStatus` (StrEnum)**: `public`, `unlisted`, `private`.
4. **`Difficulty` (StrEnum)**: `EASY`, `MEDIUM`, `HARD`.
5. **`SEOMetadata` (BaseModel)**:
   - `youtube_title` (str, 1-100 chars, non-whitespace).
   - `youtube_description` (str, 1-5000 chars, non-whitespace).
   - `tags` (list[str], item non-whitespace, total char count <= 500).
   - `category_id` (int, default 27).
   - `privacy_status` (`PrivacyStatus`, default PUBLIC).
   - `chapter_timestamps` (list[dict[str, str]]).
6. **`VideoMetadata` (BaseModel)**:
   - `title`, `description`, `slug` (`^[a-z0-9-]+$`), `resolution`, `width`, `height`, `fps` (in `{24, 25, 30, 50, 60, 120}`), `tags`, `format`, `target_platform`, `category_id`, `privacy_status`, `language`, `problem_number`, `difficulty`, `seo_metadata`.
   - Invariant: Dimension-resolution alignment (e.g. 1080p -> 1920x1080).

### `src/core/models/plan.py`
7. **`PlanSection` (BaseModel)**: `section_id`, `section_type`, `title`, `narration`, `estimated_duration` (gt=0.0, finite float), `visual_cue_ids`, `order`.
8. **`CodeSnippet` (BaseModel)**: `snippet_id`, `language`, `code`, `explanation`, `line_highlights` (1-indexed >= 1).
9. **`VisualCue` (BaseModel)**: `cue_id`, `animation_type`, `description`, `parameters` (dict).
10. **`ConceptPrerequisite` (BaseModel)**: `concept` (non-whitespace), `description`.
11. **`LearningObjective` (BaseModel)**: `objective_id`, `description`, `taxonomic_level`.
12. **`EducationalPlan` (BaseModel)**:
    - `topic`, `slug` (`^[a-z0-9-]+$`), `target_audience`, `difficulty`, `learning_objectives` (at least 1 non-empty), `prerequisites`, `sections` (at least 1), `code_snippets`, `visual_cues`, `estimated_total_duration` (gt=0.0, finite float).
    - Invariant: No duplicate `section_id` in `sections`. `estimated_total_duration` must equal sum of section durations within 0.1s.

### `src/core/models/assets.py`
13. **`AssetReference` (BaseModel)**: `asset_id`, `asset_type`, `file_path`, `duration` (gt=0.0, finite float).
14. **`AudioAsset` (BaseModel)**: `audio_id`, `file_path`, `duration_seconds` (gt=0.0, finite float), `sample_rate`, `voice_model`.
15. **`VideoAsset` (BaseModel)**: `asset_id`, `file_path`, `duration_seconds` (gt=0.0, finite float), `resolution`, `fps`, `file_size_bytes`.
16. **`RenderSegment` (BaseModel)**:
    - `segment_id`, `segment_type` (in `{'intro', 'code_walkthrough', 'visual_anim', 'outro', 'narration'}`), `start_time`, `end_time`, `duration`, `asset_references`, `audio_path`, `visual_path`, `narration_text`, `volume`, `transition_in`, `transition_out`, `audio_asset`, `scene_type`, `visual_parameters`.
    - Invariant: `end_time > start_time`, `duration == end_time - start_time` (tol 1e-3), at least one asset reference present.
17. **`RenderManifest` (BaseModel)**: `pipeline_run_id`, `slug` (`^[a-z0-9-]+$`), `segments` (non-empty), `total_duration` (gt=0.0, finite float).
18. **`AssembledVideo` (BaseModel)**: `slug`, `final_video_path`, `thumbnail_path`, `total_duration_seconds`, `file_size_bytes`, `segments`, `assembled_at`.

---

## 5. Existing Test Framework & Mocking Conventions

From inspecting `tests/conftest.py` and `tests/models/test_validation.py`:

1. **Test Framework**: `pytest` 9.1+ with `pytest-cov`.
2. **Mocking Tools**: `pytest-mock` (`mocker` fixture) and `unittest.mock` (`MagicMock`, `patch`).
3. **Environment Setup**:
   - `conftest.py` automatically sets `os.environ["ENVIRONMENT"] = "testing"`.
   - Configuration is loaded via `src.core.config.load_config()`.
4. **Mocking Conventions for `tests/llm/test_providers.py`**:
   - **No real API calls during tests**: OpenAI and Anthropic client instances must use mocked API responses.
   - **Patching target**: Patch `langchain_openai.ChatOpenAI` and `langchain_anthropic.ChatAnthropic` (or their `with_structured_output` return values / underlying invoke methods).
   - **Equivalence Assertion**: The test suite must instantiate `OpenAIClient` and `AnthropicClient`, invoke `generate_structured` with identical prompts and schemas (e.g. `EducationalPlan`, `VideoMetadata`), and verify that both providers return identical Pydantic model instances.
   - **Resiliency Verification**: Mock transient errors (e.g., HTTP 429 RateLimit, HTTP 503 Service Unavailable) for the first N calls, verifying that the client retries and ultimately succeeds. Also test that exceeding max retries raises appropriate domain exceptions (`RateLimitError`, `NetworkError`).

---

## 6. Expected Interface Signatures & Class Specifications

### 6.1 `src/core/llm/provider.py`

Defines the abstract interface or protocol for LLM providers.

```python
from abc import ABC, abstractmethod
from typing import Any, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMProvider(ABC):
    """Abstract base class for resilient structured output LLM providers."""

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> T:
        """
        Generate structured output adhering strictly to the given Pydantic model schema.

        Args:
            prompt: The primary user prompt / input string.
            response_model: The Pydantic V2 model class defining expected output schema.
            system_prompt: Optional system prompt instructions.
            temperature: Sampling temperature (0.0 to 1.0).
            **kwargs: Provider-specific runtime parameter overrides.

        Returns:
            An instantiated and validated object of type `response_model`.

        Raises:
            ValidationError: If LLM output fails Pydantic schema validation.
            RateLimitError: If provider rate limit is exceeded after retries.
            NetworkError: If transient network connection fails after retries.
            PipelineError: For non-retryable provider errors.
        """
        pass
```

### 6.2 `src/core/llm/openai_client.py`

Concrete provider using `langchain_openai.ChatOpenAI`.

```python
class OpenAIClient(LLMProvider):
    """OpenAI LLM provider wrapper leveraging LangChain and structured output."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gpt-4o",
        max_retries: int = 3,
        request_timeout: float = 60.0,
    ) -> None:
        ...

    def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> T:
        ...
```

### 6.3 `src/core/llm/anthropic_client.py`

Concrete provider using `langchain_anthropic.ChatAnthropic`.

```python
class AnthropicClient(LLMProvider):
    """Anthropic LLM provider wrapper leveraging LangChain and structured output."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "claude-3-5-sonnet-20241022",
        max_retries: int = 3,
        request_timeout: float = 60.0,
    ) -> None:
        ...

    def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> T:
        ...
```

---

## 7. Edge Cases & Handling Strategy

## Edge Cases
| # | Feature | Input / Scenario | Observed / Expected Behavior |
|---|---------|------------------|------------------------------|
| 1 | Resiliency | Rate limit (HTTP 429) from LLM API | Retries with exponential backoff up to `max_retries`. If all fail, raises `src.core.exceptions.RateLimitError`. |
| 2 | Resiliency | Network timeout / connection reset | Retries with backoff up to `max_retries`. If all fail, raises `src.core.exceptions.NetworkError`. |
| 3 | Resiliency | Authentication Failure (HTTP 401/403) | Non-retryable. Immediately raises `src.core.exceptions.AuthenticationError`. |
| 4 | Structured Output | LLM returns JSON missing required Pydantic fields | LangChain / Pydantic raises `ValidationError`. Wrapped in `src.core.exceptions.ValidationError`. |
| 5 | Structured Output | LLM outputs whitespace string for required string field (e.g. title) | Pydantic model validator catches whitespace violation and raises `ValidationError`. |
| 6 | Structured Output | LLM outputs non-finite float (`inf`/`nan`) for duration fields | Custom model field validator rejects non-finite float with `ValidationError`. |
| 7 | Structured Output | `EducationalPlan` total duration != sum of section durations | `EducationalPlan` post-validator raises `ValidationError` due to tolerance check (>0.1s). |
| 8 | Structured Output | `RenderSegment` missing asset references | `RenderSegment` post-validator raises `ValidationError`. |
| 9 | Multi-Provider | Model name or API key missing from configuration | Raises `src.core.exceptions.ConfigurationError`. |
| 10 | Testing | Mock API response returns raw dict vs Pydantic object | Test mock must simulate `with_structured_output` returning instantiated Pydantic model. |

---

## 8. Summary of Deliverables to be Produced in Phase 06

1. `src/core/llm/provider.py`: Abstract provider interface.
2. `src/core/llm/openai_client.py`: Concrete OpenAI client implementation.
3. `src/core/llm/anthropic_client.py`: Concrete Anthropic client implementation.
4. `PromptBook/Phase06/01_LLM_Abstraction.md`: Complete strategy, retry, and architecture documentation.
5. `tests/llm/test_providers.py`: Comprehensive test suite with mocked OpenAI and Anthropic responses.
