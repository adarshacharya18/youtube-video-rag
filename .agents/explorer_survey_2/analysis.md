# Phase 06 Survey Analysis: LLM Provider Abstraction, LangChain Integration & Resiliency Strategy

## 1. Executive Summary

This report provides a comprehensive architectural investigation and design specification for **Phase 06: LLM Provider Abstraction** of the Automated DSA Educational YouTube Video Pipeline.

The goal of Phase 06 is to build a unified, resilient Python interface wrapping external Large Language Models (OpenAI and Anthropic) using **LangChain's `BaseChatModel`** and **`with_structured_output`**. This layer enforces strict structured output generation utilizing the Phase 05 Pydantic V2 data models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`).

Key findings and architectural decisions:
1. **LangChain Engine**: Both `ChatOpenAI` and `ChatAnthropic` inherit from `BaseChatModel` and implement `.with_structured_output(schema)`. When passed a Pydantic V2 `BaseModel` class, LangChain configures provider-native tool/function calling and returns a `RunnableSequence` that deserializes the LLM JSON response into a fully validated Pydantic model instance.
2. **Pydantic V2 Validation Rules**: All custom `@field_validator` and `@model_validator` logic defined in Phase 05 (such as non-whitespace constraints, finite float validations, slug regex enforcement, resolution dimension alignment, and total duration math) run automatically when LangChain instantiates the model. If LLM output violates constraints, Pydantic raises a `ValidationError`.
3. **Resiliency Strategy**: We recommend a **Dual-Layer Resiliency Pattern**:
   - **Layer 1 (Transport & Rate Limits)**: Utilizes `tenacity` exponential backoff with jitter to handle HTTP 429 Rate Limits, 5xx server errors, and connection timeouts.
   - **Layer 2 (Semantic Schema Validation)**: Catches Pydantic `ValidationError` and re-prompts or falls back to a secondary provider model if output parsing repeatedly fails.
4. **Provider Abstraction & Fallback**: Abstract base class `LLMProvider` in `src/core/llm/provider.py`, concrete implementations `OpenAIClient` (`src/core/llm/openai_client.py`) and `AnthropicClient` (`src/core/llm/anthropic_client.py`), with a composite `FallbackLLMProvider` for high-availability provider failover.
5. **Testing Strategy**: Acceptance criteria require `pytest tests/llm/test_providers.py` to run offline using mocked API responses (`unittest.mock`), asserting identical Pydantic V2 objects from both OpenAI and Anthropic clients.

---

## 2. LangChain `BaseChatModel` & Structured Output Deep-Dive

### 2.1 How `with_structured_output` Works in LangChain

`BaseChatModel.with_structured_output(schema, *, method=..., include_raw=...)` is LangChain's standard mechanism for enforcing structured responses from LLMs.

- **Signature**:
  ```python
  def with_structured_output(
      self,
      schema: Union[Dict, Type[BaseModel]],
      *,
      method: Optional[str] = None,
      include_raw: bool = False,
      **kwargs: Any,
  ) -> Runnable[LanguageModelInput, Union[Dict, BaseModel]]:
  ```
- **Return Value**: Returns a `RunnableSequence` (or `RunnableBinding`) that binds the LLM to tool calling / structured output parsing and yields an instantiated Pydantic object when `.invoke(prompt)` is called.

#### Provider Differences:
1. **`ChatOpenAI` (`langchain-openai`)**:
   - **Default Method**: Function / Tool calling (`method="function_calling"`) or OpenAI JSON Schema Structured Outputs (`method="json_schema"`).
   - **JSON Schema Mode (`strict=True`)**: OpenAI supports strict schema adherence at the API level, ensuring output JSON strictly matches the generated JSON Schema.
2. **`ChatAnthropic` (`langchain-anthropic`)**:
   - **Default Method**: Claude Tool Calling (`method="max_tokens"` / tool binding). Claude outputs a tool call named after the Pydantic schema, containing structured arguments.
   - **Parsing**: LangChain automatically extracts the tool call arguments and passes them to Pydantic for validation.

### 2.2 Compatibility & Validation with Phase 05 Pydantic V2 Models

Phase 05 defined strict Pydantic V2 models in `src/core/models/`:
- `VideoMetadata` (`video.py`): Field validators for non-whitespace string, slug pattern `^[a-z0-9-]+$`, FPS allowed set `{24,25,30,50,60,120}`, tag length limits, and `@model_validator` for resolution dimension alignment (`720p`, `1080p`, `4K`).
- `EducationalPlan` (`plan.py`): Non-finite float validation (`math.isfinite`), non-empty learning objectives, duplicate `section_id` checks, and `@model_validator` enforcing section duration sum matching `estimated_total_duration` within 0.1s tolerance.
- `RenderSegment` (`assets.py`): Asset reference requirements, valid segment types, non-finite float checks, and `end_time > start_time` invariant.

#### Execution Pipeline when LLM Responds:
```
LLM Raw Response (JSON Tool Call)
       │
       ▼
LangChain Output Parser (PydanticOutputParser / JsonOutputKeyToolsParser)
       │
       ▼
Pydantic V2 model_validate / Schema Instantiation
       │
       ├──> Field Validators (@field_validator)
       └──> Model Validators (@model_validator)
       │
       ├──> SUCCESS: Valid Pydantic Instance returned
       └──> FAILURE: Raises pydantic.ValidationError or OutputParserException
```

#### Key Observation on Parsing Errors:
When an LLM produces output that violates a Phase 05 constraint (e.g., generating `estimated_total_duration = 30.0` but section durations sum to `45.0`), Pydantic raises `pydantic.ValidationError`. This exception is caught by our resiliency wrapper to trigger a re-prompt or provider fallback.

### 2.3 `include_raw=True` Option
When `include_raw=True` is set on `with_structured_output`:
- `chain.invoke(prompt)` returns a dictionary:
  ```python
  {
      "raw": AIMessage(...),           # Raw LLM message
      "parsed": VideoMetadata(...),    # Parsed Pydantic model (or None if failed)
      "parsing_error": Exception(...) # Captured exception (or None if succeeded)
  }
  ```
- This is useful for detailed logging into the `StateLedger` (storing raw token usage, latency, or raw message content alongside parsed outputs).

---

## 3. Resiliency, Retry/Backoff & Provider Strategy

### 3.1 Failure Modes & Exception Taxonomy

LLM API calls encounter distinct operational failure categories:

| Error Category | Specific Exceptions | Classification | Action Strategy |
| :--- | :--- | :--- | :--- |
| **Transient Network / HTTP 5xx** | `httpx.TimeoutException`, `httpx.ConnectError`, OpenAI `APIConnectionError`, Anthropic `InternalServerError` | `RetryableError` / `NetworkError` | Exponential backoff with jitter (1s - 60s, max 5 attempts) |
| **Rate Limits (HTTP 429)** | OpenAI `RateLimitError`, Anthropic `RateLimitError` | `RetryableError` / `RateLimitError` | Exponential backoff + jitter (respecting `retry-after` header if present) |
| **Authentication & Auth (401/403)** | OpenAI `AuthenticationError`, Anthropic `AuthenticationError` | `FatalError` / `AuthenticationError` | Immediately fail execution. Do NOT retry. |
| **Invalid Prompt / 400 Bad Request** | OpenAI `BadRequestError`, Anthropic `BadRequestError` | `FatalError` | Halt execution. Do NOT retry. |
| **Semantic Schema Validation** | `pydantic.ValidationError`, `OutputParserException` | `RetryableValidationError` | Re-prompt with error message or trigger fallback model/provider (max 2-3 attempts). |

### 3.2 Retry Implementation Options: LangChain `.with_retry()` vs `tenacity`

#### Option A: LangChain Built-in `.with_retry()`
```python
chain = llm.with_structured_output(VideoMetadata).with_retry(
    stop_after_attempt=3,
    wait_exponential_jitter=True,
    retry_if_exception_type=(NetworkError, RateLimitError),
)
```
- **Pros**: Declarative, chain-native, built into `langchain-core`.
- **Cons**: Limited hooks for detailed logging per attempt to `structlog` or `StateLedger`; harder to inject prompt feedback on `ValidationError`.

#### Option B: `tenacity` Library Wrapper (Recommended)
```python
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=60),
    retry=retry_if_exception_type((TransientError, RateLimitError)),
    before_sleep=log_retry_attempt,
    reraise=True,
)
def _invoke_with_retry(chain, prompt):
    return chain.invoke(prompt)
```
- **Pros**: Industry-standard resiliency library; full control over wait algorithms (jitter, multiplier); custom `before_sleep` callbacks for structured logging; clean integration with custom exception handling.
- **Cons**: Requires explicit function wrapping.

### 3.3 Recommended Dual-Layer Resiliency Architecture

```
                       User Prompt / Schema Request
                                    │
                                    ▼
                ┌──────────────────────────────────────┐
                │   Layer 2: Semantic Retry & Fallback │
                │   (Catches Pydantic ValidationError, │
                │    re-prompts or switches provider)   │
                └──────────────────┬───────────────────┘
                                   │
                                   ▼
                ┌──────────────────────────────────────┐
                │   Layer 1: Transport & Rate Limit    │
                │   (Tenacity: Handles HTTP 429, 5xx,  │
                │    Timeouts with Backoff + Jitter)   │
                └──────────────────┬───────────────────┘
                                   │
                                   ▼
                ┌──────────────────────────────────────┐
                │    LangChain BaseChatModel Client    │
                │   (ChatOpenAI / ChatAnthropic)       │
                └──────────────────────────────────────┘
```

### 3.4 Provider Abstraction & Fallback Mechanics

#### 1. Core Interface (`src/core/llm/provider.py`):
```python
from abc import ABC, abstractmethod
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMProvider(ABC):
    """Abstract interface for LLM providers enforcing structured output."""

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        output_schema: Type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generate a validated Pydantic model instance from prompt."""
        pass
```

#### 2. Concrete OpenAI Client (`src/core/llm/openai_client.py`):
```python
from langchain_openai import ChatOpenAI
from src.core.llm.provider import LLMProvider

class OpenAIClient(LLMProvider):
    def __init__(self, api_key: str, model_name: str = "gpt-4o", temperature: float = 0.7):
        self.llm = ChatOpenAI(api_key=api_key, model=model_name, temperature=temperature)

    def generate_structured(self, prompt: str, output_schema: Type[T], system_prompt: str | None = None) -> T:
        chain = self.llm.with_structured_output(output_schema)
        # Apply tenacity backoff & execution
        return execute_with_resiliency(chain, prompt, system_prompt)
```

#### 3. Concrete Anthropic Client (`src/core/llm/anthropic_client.py`):
```python
from langchain_anthropic import ChatAnthropic
from src.core.llm.provider import LLMProvider

class AnthropicClient(LLMProvider):
    def __init__(self, api_key: str, model_name: str = "claude-3-5-sonnet-20241022", temperature: float = 0.7):
        self.llm = ChatAnthropic(api_key=api_key, model=model_name, temperature=temperature)

    def generate_structured(self, prompt: str, output_schema: Type[T], system_prompt: str | None = None) -> T:
        chain = self.llm.with_structured_output(output_schema)
        # Apply tenacity backoff & execution
        return execute_with_resiliency(chain, prompt, system_prompt)
```

#### 4. Composite Fallback Client (`FallbackLLMProvider`):
```python
class FallbackLLMProvider(LLMProvider):
    def __init__(self, primary: LLMProvider, secondary: LLMProvider):
        self.primary = primary
        self.secondary = secondary

    def generate_structured(self, prompt: str, output_schema: Type[T], system_prompt: str | None = None) -> T:
        try:
            return self.primary.generate_structured(prompt, output_schema, system_prompt)
        except Exception as e:
            logger.warning("Primary LLM provider failed, failing over to secondary", error=str(e))
            return self.secondary.generate_structured(prompt, output_schema, system_prompt)
```

### 3.5 Integration with System Configuration (`src/core/config.py`)

Extend `PipelineConfig` in `src/core/config.py` to include LLM configuration models:
```python
class LLMConfig(BaseSettings):
    """Configuration for LLM Provider Abstraction (Phase 06)."""
    
    primary_provider: str = Field(default="openai", description="openai | anthropic")
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = Field(default="gpt-4o")
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022")
    max_retries: int = Field(default=3, ge=1)
    timeout_seconds: int = Field(default=30, ge=5)
    enable_fallback: bool = Field(default=True)
```

---

## 4. PromptBook Documentation Requirements (`PromptBook/Phase06/01_LLM_Abstraction.md`)

The file `PromptBook/Phase06/01_LLM_Abstraction.md` must be created to document Phase 06 architecture. It should be structured into the following mandatory sections:

1. **Title & Document Metadata**: Phase 06 LLM Provider Abstraction Architecture & Resiliency Specification.
2. **Unified Interface Architecture**:
   - Class diagrams (Mermaid) showing `LLMProvider` interface, `OpenAIClient`, `AnthropicClient`, and `FallbackLLMProvider`.
   - Explanations of how `BaseChatModel` and `with_structured_output` form the foundation.
3. **Structured Output & Schema Enforcement**:
   - Integration with Phase 05 Pydantic V2 models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`).
   - Detailed breakdown of Pydantic validation rules and failure handling.
4. **Resiliency & Retry Strategy**:
   - Detailed specification of `tenacity` retry configuration (exponential backoff parameters, max attempts, jitter policy).
   - Rate limit (HTTP 429) handling and HTTP 5xx error recovery.
5. **Provider Fallback Mechanics**:
   - Step-by-step sequence diagram (Mermaid) illustrating primary provider attempt -> retry loop -> failover to secondary provider -> validated Pydantic object returned.
6. **Testing & Offline Verification**:
   - Unit testing patterns for `tests/llm/test_providers.py` using `unittest.mock`.
   - Code snippets showing how to mock OpenAI and Anthropic clients to return identical Pydantic V2 schema instances.
7. **Acceptance Criteria Traceability Matrix**:
   - Mapping requirements R1-R4 to concrete implementation files and pytest assertions.

---

## 5. Verification & Testing Strategy for Implementer

### 5.1 Test Suite File Structure
- Test file: `tests/llm/test_providers.py`
- Executable: `./.venv/bin/pytest tests/llm/test_providers.py`

### 5.2 Mocking Strategy Blueprint (`tests/llm/test_providers.py`)
To satisfy acceptance criteria without requiring real API keys:
1. Mock `ChatOpenAI` and `ChatAnthropic` `with_structured_output` using `unittest.mock.MagicMock` / `pytest-mock`.
2. Construct deterministic Phase 05 model instances (`sample_video_metadata`, `sample_educational_plan`, `sample_render_segment`).
3. Assert that both `OpenAIClient.generate_structured(...)` and `AnthropicClient.generate_structured(...)` return identical Pydantic V2 model instances.
4. Test rate limit retry simulation (mocking transient failure on 1st call, success on 2nd call).
5. Test fallback provider triggering when primary provider raises an unrecoverable exception.

```python
"""Unit tests for LLM provider abstraction and structured output in Phase 06."""

from unittest.mock import MagicMock, patch
import pytest
from src.core.llm.openai_client import OpenAIClient
from src.core.llm.anthropic_client import AnthropicClient
from src.core.models.video import VideoMetadata, VideoResolution, TargetPlatform, PrivacyStatus

@pytest.fixture
def expected_video_metadata():
    return VideoMetadata(
        title="Two Sum Algorithm",
        description="Complete guide to solving Two Sum in Python.",
        slug="two-sum-algorithm",
        resolution=VideoResolution.R_1080P,
        fps=30,
        tags=["python", "leetcode"],
        target_platform=TargetPlatform.YOUTUBE,
    )

def test_openai_and_anthropic_return_identical_pydantic_objects(expected_video_metadata):
    # Mock OpenAI
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_openai_cls:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = expected_video_metadata
        mock_openai_cls.return_value.with_structured_output.return_value = mock_chain
        
        openai_client = OpenAIClient(api_key="mock-key")
        result_openai = openai_client.generate_structured("prompt", VideoMetadata)

    # Mock Anthropic
    with patch("src.core.llm.anthropic_client.ChatAnthropic") as mock_anthropic_cls:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = expected_video_metadata
        mock_anthropic_cls.return_value.with_structured_output.return_value = mock_chain
        
        anthropic_client = AnthropicClient(api_key="mock-key")
        result_anthropic = anthropic_client.generate_structured("prompt", VideoMetadata)

    # Assert identical Pydantic objects
    assert result_openai == result_anthropic == expected_video_metadata
```

---

## 6. Target Files Summary for Phase 06 Implementation

| Target File Path | Purpose / Description |
| :--- | :--- |
| `src/core/llm/__init__.py` | Package initialization for LLM module. |
| `src/core/llm/provider.py` | Abstract interface `LLMProvider` and composite `FallbackLLMProvider`. |
| `src/core/llm/openai_client.py` | `OpenAIClient` concrete implementation using `ChatOpenAI` and `with_structured_output`. |
| `src/core/llm/anthropic_client.py` | `AnthropicClient` concrete implementation using `ChatAnthropic` and `with_structured_output`. |
| `src/core/exceptions.py` | Addition of LLM operational exceptions (`LLMProviderError`, `LLMRateLimitError`, `LLMValidationError`). |
| `src/core/config.py` | Addition of `LLMConfig` to `PipelineConfig`. |
| `PromptBook/Phase06/01_LLM_Abstraction.md` | Architectural documentation and resiliency specification. |
| `tests/llm/test_providers.py` | Pytest suite validating structured output and resiliency via mocked responses. |
