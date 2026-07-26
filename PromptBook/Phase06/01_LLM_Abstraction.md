# Phase 06: LLM Provider Abstraction Architecture

## 1. Executive Summary & Architecture Overview

The **LLM Provider Abstraction Layer** provides a unified, resilient Python interface wrapping external Large Language Model providers (OpenAI, Anthropic) for the Automated DSA Educational YouTube Video Pipeline.

By leveraging LangChain's underlying `BaseChatModel` and `.with_structured_output()` mechanism, the abstraction guarantees that all LLM calls return strictly validated Pydantic V2 domain objects (`VideoMetadata`, `EducationalPlan`, `RenderSegment`, etc.) regardless of whether OpenAI's GPT models or Anthropic's Claude models generate the responses.

```
+-------------------------------------------------------------------------+
|                         Pipeline Stage Modules                          |
|         (Script Generator, Tag Explorer, RAG Summarizer, etc.)           |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                BaseLLMProvider.generate_structured(...)                 |
|  - Validates input prompt & Pydantic response_model                     |
|  - Manages retry loop (max_retries, exponential backoff + full jitter)  |
|  - Translates SDK exceptions into PipelineError domain types             |
+-------------------------------------------------------------------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
+-----------------------+                       +-----------------------+
|     OpenAIClient      |                       |    AnthropicClient    |
| (ChatOpenAI wrapper)  |                       | (ChatAnthropic wrap)  |
+-----------------------+                       +-----------------------+
            |                                               |
            v                                               v
+-------------------------------------------------------------------------+
|                  LangChain BaseChatModel Interface                      |
|                  .with_structured_output(schema)                        |
+-------------------------------------------------------------------------+
```

### Key Architectural Objectives
1. **Provider Neutrality**: Seamless interchangeability between OpenAI (GPT-4o) and Anthropic (Claude 3.5 Sonnet) without altering downstream pipeline logic.
2. **Strict Schema Guarantees**: Enforces 1-to-1 parity with Phase 05 Pydantic V2 schemas.
3. **Automated Resiliency**: Handles rate limits (HTTP 429) and transient network timeouts with exponential backoff retries and full jitter.
4. **Centralized Exception Mapping**: Translates raw vendor SDK exceptions into structured domain exceptions (`src/core/exceptions.py`).

---

## 2. Class Hierarchy & Interface Contracts

### 2.1 Base Provider (`src/core/llm/provider.py`)
`BaseLLMProvider` is an abstract base class enforcing standard initialization parameters and defining the core generation and retry logic:

- `__init__(model_name: str, api_key: str | None = None, temperature: float = 0.0, max_retries: int = 3, timeout: float = 60.0, initial_backoff: float = 1.0, backoff_factor: float = 2.0, max_backoff: float = 30.0)`
- `@abc.abstractmethod get_chat_model() -> BaseChatModel`: Must be implemented by concrete subclasses to return an initialized LangChain chat model.
- `generate_structured(prompt: str | list[Any], response_model: type[T]) -> T`: Public entrypoint that invokes `get_chat_model().with_structured_output(response_model)` within an exponential backoff retry loop.

### 2.2 Concrete Clients

#### `OpenAIClient` (`src/core/llm/openai_client.py`)
- Inherits from `BaseLLMProvider`.
- Wraps `langchain_openai.ChatOpenAI`.
- Resolves configuration settings from `load_config().llm.openai` or environment variable `OPENAI_API_KEY`.
- Passes `model`, `temperature`, `max_retries`, `request_timeout`, `api_key`, and `organization` parameters.

#### `AnthropicClient` (`src/core/llm/anthropic_client.py`)
- Inherits from `BaseLLMProvider`.
- Wraps `langchain_anthropic.ChatAnthropic`.
- Resolves configuration settings from `load_config().llm.anthropic` or environment variable `ANTHROPIC_API_KEY`.
- Passes `model`, `temperature`, `max_retries`, `default_request_timeout`, and `api_key` parameters.

### 2.3 Configuration Models (`src/core/config.py`)
The configuration system uses Pydantic Settings to load provider settings from environment variables or `.env` files using double-underscore syntax:

- `OpenAIConfig`: Default model `gpt-4o`, temperature `0.0`, retries `3`, timeout `60.0s`.
- `AnthropicConfig`: Default model `claude-3-5-sonnet-20240620`, temperature `0.0`, retries `3`, timeout `60.0s`.
- `LLMConfig`: Aggregates `openai` and `anthropic` configs and specifies `default_provider`.

---

## 3. Resiliency Engine & Exponential Backoff Retry Logic

### 3.1 Exponential Backoff with Full Jitter
To prevent thundering herd problems when API rate limits are hit by concurrent pipeline workers, `BaseLLMProvider` implements exponential backoff with full randomized jitter:

$$\text{delay}_{\text{exponential}} = \text{initial\_backoff} \times (\text{backoff\_factor}^{\text{attempt} - 1})$$
$$\text{delay}_{\text{capped}} = \min(\text{max\_backoff}, \text{delay}_{\text{exponential}})$$
$$\text{delay}_{\text{jittered}} = \text{random.uniform}(0.5 \times \text{delay}_{\text{capped}}, \text{delay}_{\text{capped}})$$

### 3.2 Retry Control Flow
1. Validate prompt upfront; raise `ValidationError` immediately if empty or null.
2. Attempt generation up to `max_retries + 1` times.
3. Catch raw exceptions and pass through `_translate_exception(raw_exc)`.
4. If translated exception is a `RetryableError` (`RateLimitError`, `NetworkError`) AND attempts remain, calculate backoff delay, sleep, and retry.
5. If non-retryable (`ValidationError`, `AuthenticationError`, `FatalError`) or retries are exhausted, log error and re-raise translated exception with `raise translated_exc from raw_exc`.

---

## 4. Exception Mapping Matrix

The abstraction layer intercepts vendor SDK exceptions and maps them to centralized pipeline exceptions defined in `src/core/exceptions.py`:

| Raw Exception Source / Signal | Matching Condition | Translated Exception Class | Operational Classification | Action Taken |
|---|---|---|---|---|
| HTTP 429 / `RateLimitError` | `status_code == 429` or "rate limit" in exception | `src.core.exceptions.RateLimitError` | `RetryableError` | Exponential backoff retry |
| Timeout / Connection Error | `TimeoutError`, `ConnectionError`, HTTP 500/502/503/504 | `src.core.exceptions.NetworkError` | `RetryableError` | Exponential backoff retry |
| Output Parsing Failure / Schema Validation Error | `OutputParserException`, `ValidationError`, JSON syntax error | `src.core.exceptions.ValidationError` | `FatalError` | Immediate halt (no retry) |
| HTTP 401 / HTTP 403 / Bad Credentials | `status_code in (401, 403)` or "auth" / "api key" | `src.core.exceptions.AuthenticationError` | `FatalError` | Immediate halt (no retry) |
| Unclassified Exception | Any unmatched exception | `src.core.exceptions.FatalError` | `FatalError` | Immediate halt (no retry) |

---

## 5. Fallback Mechanisms

When operating in multi-provider production deployments, stages can implement fallback execution using provider try-catch blocks:

```python
from src.core.exceptions import AuthenticationError, RateLimitError
from src.core.llm.openai_client import OpenAIClient
from src.core.llm.anthropic_client import AnthropicClient
from src.core.models import VideoMetadata

def generate_video_metadata_with_fallback(prompt: str) -> VideoMetadata:
    primary = OpenAIClient()
    secondary = AnthropicClient()

    try:
        return primary.generate_structured(prompt, VideoMetadata)
    except (RateLimitError, AuthenticationError) as exc:
        # Failover to secondary provider on primary failure
        return secondary.generate_structured(prompt, VideoMetadata)
```

---

## 6. Verification & Test Guide

### 6.1 Executing Provider Tests
Run the dedicated provider unit test suite using Pytest:

```bash
./.venv/bin/pytest tests/llm/test_providers.py
```

To run all core and LLM tests together:
```bash
./.venv/bin/pytest tests/llm/test_providers.py tests/core tests/models
```

### 6.2 Test Architecture
The test suite in `tests/llm/test_providers.py` uses Pytest fixtures and `unittest.mock`:
- **Mocked LangChain Models**: Mocks `ChatOpenAI` and `ChatAnthropic` constructors so tests run 100% offline without active network calls or real API keys.
- **Identical Pydantic Schema Assertions**: Verifies that both OpenAI and Anthropic clients return identical Pydantic V2 objects (`VideoMetadata`, `EducationalPlan`, `RenderSegment`).
- **Resiliency Verification**: Simulates transient HTTP 429 and connection timeout exceptions to verify retry counts and delay timing.
- **Error Translation Verification**: Verifies immediate raising of `ValidationError` and `AuthenticationError` on non-retryable failures.
