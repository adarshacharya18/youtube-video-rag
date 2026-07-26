# Architectural Design Analysis: LLM Provider Abstraction (`src/core/llm/provider.py`)

**Author**: Design Explorer 1 (`explorer_iter1_1`)  
**Date**: 2026-07-26  
**Module**: `src/core/llm/provider.py`  
**Milestone**: M2 — LLM Provider Abstraction & Clients  
**Related Documents**: `ORIGINAL_REQUEST.md` (Phase 06), `PROJECT.md`, `src/core/exceptions.py`, `src/core/models/`

---

## 1. Overview & Architectural Role

The `src/core/llm/provider.py` module defines the abstract base interface (`BaseLLMProvider`) and resiliency engine for all Large Language Model integrations across the Automated DSA Educational YouTube Video Pipeline.

### Architectural Responsibilities
1. **Vendor-Agnostic Abstraction Layer**: Provides a uniform interface hiding provider-specific SDK details (OpenAI, Anthropic, Gemini, etc.) behind standard Python protocols.
2. **LangChain Structured Output Engine**: Leverages LangChain's `BaseChatModel` and `.with_structured_output()` mechanism to force LLM responses directly into Phase 05 Pydantic V2 models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`, etc.).
3. **Resiliency & Retry/Backoff Logic**: Implements exponential backoff with full jitter to handle rate limits (HTTP 429) and transient network failures automatically.
4. **Exception Translation Layer**: Traps provider-specific SDK exceptions (from `openai`, `anthropic`, `httpx`, `langchain`) and translates them into domain exceptions defined in `src/core/exceptions.py` (`RateLimitError`, `NetworkError`, `ValidationError`, `AuthenticationError`).
5. **Observability & Structural Logging**: Integrates with `structlog` to log retry attempts, backoff delays, timing metrics, and fatal errors.

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
|  - Manages retry loop (max_retries, exponential backoff + jitter)       |
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

---

## 2. Core Class Interface Design (`BaseLLMProvider`)

### 2.1 Interface Definition

```python
import abc
import random
import time
from typing import Any, Generic, TypeVar, Union

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel
import structlog

from src.core.exceptions import (
    AuthenticationError,
    FatalError,
    NetworkError,
    PipelineError,
    RateLimitError,
    RetryableError,
    ValidationError,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(abc.ABC):
    """
    Abstract Base Class for LLM providers supplying structured output generation.
    
    Subclasses (such as OpenAIClient and AnthropicClient) implement `get_chat_model()`
    to configure and return their specific LangChain `BaseChatModel`.
    
    The base class provides `generate_structured()` with built-in exponential backoff
    retries for transient errors and exception mapping to pipeline domain exceptions.
    """

    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        temperature: float = 0.0,
        max_retries: int = 3,
        timeout: float = 60.0,
        initial_backoff: float = 1.0,
        backoff_factor: float = 2.0,
        max_backoff: float = 30.0,
    ) -> None:
        """
        Initialize the LLM Provider configuration.

        Args:
            model_name: Provider model string (e.g. 'gpt-4o', 'claude-3-5-sonnet-20240620').
            api_key: Secret API key. If None, falls back to environment variable configuration.
            temperature: Sampling temperature (default 0.0 for deterministic structured outputs).
            max_retries: Maximum retry attempts for retryable errors (default 3).
            timeout: Request timeout in seconds (default 60.0).
            initial_backoff: Initial delay in seconds for exponential backoff (default 1.0).
            backoff_factor: Multiplier for exponential backoff (default 2.0).
            max_backoff: Maximum delay cap in seconds (default 30.0).
        """
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout
        self.initial_backoff = initial_backoff
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.logger = logger.bind(provider=self.__class__.__name__, model=self.model_name)

    @abc.abstractmethod
    def get_chat_model(self) -> BaseChatModel:
        """
        Factory method returning an initialized LangChain `BaseChatModel` instance.
        
        Must be implemented by concrete provider subclasses.
        """
        pass

    def generate_structured(
        self,
        prompt: str | list[Any],
        response_model: type[T],
    ) -> T:
        """
        Generate a strictly-typed structured response using a Pydantic model schema.

        Args:
            prompt: Text prompt string or list of LangChain message objects/dicts.
            response_model: Pydantic V2 BaseModel subclass specifying the target schema.

        Returns:
            An instance of `response_model` populated with parsed and validated LLM output.

        Raises:
            ValidationError: If prompt is invalid or LLM output fails schema validation.
            RateLimitError: If API rate limits (HTTP 429) persist after max retries.
            NetworkError: If transient network/timeout errors persist after max retries.
            AuthenticationError: If API key authentication fails (HTTP 401/403).
            PipelineError: For unexpected fatal provider errors.
        """
        if not prompt:
            raise ValidationError("Prompt cannot be empty or null")

        chat_model = self.get_chat_model()
        structured_llm = chat_model.with_structured_output(response_model)

        attempt = 1
        max_attempts = self.max_retries + 1

        while attempt <= max_attempts:
            try:
                self.logger.debug(
                    "executing_llm_request",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    response_model=response_model.__name__,
                )
                start_time = time.perf_counter()
                result = structured_llm.invoke(prompt)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                if result is None:
                    raise ValidationError(
                        f"LLM returned null or empty structured output for model {response_model.__name__}"
                    )

                self.logger.info(
                    "llm_request_successful",
                    attempt=attempt,
                    elapsed_ms=round(elapsed_ms, 2),
                    response_model=response_model.__name__,
                )
                return result

            except Exception as raw_exc:
                translated_exc = self._translate_exception(raw_exc)

                if isinstance(translated_exc, RetryableError) and attempt < max_attempts:
                    delay = self._calculate_backoff_delay(attempt)
                    self.logger.warning(
                        "llm_request_failed_retryable",
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay_seconds=round(delay, 2),
                        error_type=translated_exc.__class__.__name__,
                        error_message=str(translated_exc),
                    )
                    time.sleep(delay)
                    attempt += 1
                else:
                    self.logger.error(
                        "llm_request_failed_fatal",
                        attempt=attempt,
                        max_attempts=max_attempts,
                        error_type=translated_exc.__class__.__name__,
                        error_message=str(translated_exc),
                    )
                    raise translated_exc from raw_exc

        # Safety fallback (unreachable under normal flow)
        raise NetworkError(f"LLM call failed after {self.max_retries} retries")

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with full jitter.
        
        Formula: delay = min(max_backoff, initial_backoff * (backoff_factor ** (attempt - 1)))
        Jitter: delay = random.uniform(0, calculated_delay)
        """
        exponential_delay = self.initial_backoff * (self.backoff_factor ** (attempt - 1))
        capped_delay = min(self.max_backoff, exponential_delay)
        # Apply full jitter to prevent synchronized retry thundering herd
        jittered_delay = random.uniform(0.5 * capped_delay, capped_delay)
        return jittered_delay

    def _translate_exception(self, exc: Exception) -> PipelineError:
        """
        Translate third-party SDK and network exceptions into centralized PipelineError types.
        """
        if isinstance(exc, PipelineError):
            return exc

        exc_name = exc.__class__.__name__
        exc_str = str(exc).lower()
        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)

        # 1. Rate Limit Errors (HTTP 429)
        if status_code == 429 or "ratelimit" in exc_name.lower() or "rate limit" in exc_str or "429" in exc_str:
            return RateLimitError(f"LLM provider rate limit exceeded: {exc}")

        # 2. Authentication / Authorization Errors (HTTP 401, 403)
        if status_code in (401, 403) or "auth" in exc_name.lower() or "unauthorized" in exc_str or "invalid api key" in exc_str:
            return AuthenticationError(f"LLM provider authentication failed: {exc}")

        # 3. Validation / Schema Output Parsing Errors
        if "validation" in exc_name.lower() or "outputparser" in exc_name.lower() or "json" in exc_str:
            return ValidationError(f"LLM structured output validation failed: {exc}")

        # 4. Network / Connection / Timeout / 5xx Server Errors
        if (
            isinstance(exc, (TimeoutError, ConnectionError))
            or status_code in (500, 502, 503, 504)
            or any(kw in exc_name.lower() for kw in ["timeout", "connection", "network", "httperror"])
            or any(kw in exc_str for kw in ["timeout", "connection refused", "503", "500", "overloaded"])
        ):
            return NetworkError(f"LLM provider network issue: {exc}")

        # Default fallback
        return FatalError(f"LLM provider unclassified error ({exc_name}): {exc}")
```

---

## 3. Detailed Exception Mapping Matrix

The retry logic relies on differentiating transient issues (`RetryableError`) from unrecoverable issues (`FatalError`).

| External Source / Exception | Inspected Attributes | Translated Pipeline Exception | Impact Hierarchy | Retry Action |
|---|---|---|---|---|
| `openai.RateLimitError`<br>`anthropic.RateLimitError` | `status_code == 429`<br>Class name contains `RateLimit` | `src.core.exceptions.RateLimitError` | `RetryableError` (inherits `PipelineError`) | Retry with exponential backoff & jitter |
| `httpx.TimeoutException`<br>`httpx.ConnectError`<br>`openai.APITimeoutError`<br>`openai.APIConnectionError`<br>`anthropic.APIConnectionError` | `status_code in (500, 502, 503, 504)`<br>Inherits `TimeoutError` / `ConnectionError` | `src.core.exceptions.NetworkError` | `RetryableError` (inherits `PipelineError`) | Retry with exponential backoff & jitter |
| `langchain_core.exceptions.OutputParserException`<br>`pydantic.ValidationError` | Exception name contains `OutputParser` or `Validation` | `src.core.exceptions.ValidationError` | `FatalError` (inherits `PipelineError`) | Immediate halt (`raise`) |
| `openai.AuthenticationError`<br>`anthropic.AuthenticationError` | `status_code in (401, 403)`<br>"Invalid API key" | `src.core.exceptions.AuthenticationError` | `FatalError` (inherits `PipelineError`) | Immediate halt (`raise`) |
| Unhandled / Unexpected Runtime Exception | Generic fallback | `src.core.exceptions.FatalError` | `FatalError` (inherits `PipelineError`) | Immediate halt (`raise`) |

---

## 4. Exponential Backoff & Retry Sequence Flow

```
[Start generate_structured]
           |
           v
    Check prompt validity ---> Empty/None ---> Raise ValidationError
           |
           v
  Initialize attempt = 1
           |
           v
+-------------------------------------------------------------+
| Loop: attempt <= max_retries + 1                            |
|                                                             |
|   Try:                                                      |
|     Invoke structured_llm(prompt)                           |
|     If result is None: raise ValidationError                |
|     Log success & Return result                             |
|                                                             |
|   Except raw_exc:                                           |
|     translated = _translate_exception(raw_exc)              |
|                                                             |
|     Is translated a RetryableError?                         |
|     +-- NO  (FatalError, ValidationError, AuthError):      |
|     |     Log fatal error                                   |
|     |     Raise translated_exc from raw_exc                 |
|     |                                                       |
|     +-- YES (RateLimitError, NetworkError):                 |
|           Is attempt < max_attempts?                        |
|           +-- NO:  Log retries exhausted -> Raise translated|
|           +-- YES: Calculate delay = _calculate_backoff()   |
|                    Log warning with structlog               |
|                    time.sleep(delay)                        |
|                    attempt += 1 -> Repeat loop              |
+-------------------------------------------------------------+
```

---

## 5. Concrete Client Integration Strategy

### 5.1 `OpenAIClient` (`src/core/llm/openai_client.py`)
Subclasses `BaseLLMProvider` and overrides `get_chat_model()`:
```python
from langchain_openai import ChatOpenAI
from src.core.llm.provider import BaseLLMProvider

class OpenAIClient(BaseLLMProvider):
    def get_chat_model(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key, # If None, langchain handles OPENAI_API_KEY env var
            temperature=self.temperature,
            request_timeout=self.timeout,
            max_retries=0, # Retries handled explicitly by BaseLLMProvider
        )
```
*Note*: `max_retries=0` is passed to the underlying SDK/LangChain model constructor so that retries are handled deterministically by `BaseLLMProvider`'s central retry loop.

### 5.2 `AnthropicClient` (`src/core/llm/anthropic_client.py`)
Subclasses `BaseLLMProvider` and overrides `get_chat_model()`:
```python
from langchain_anthropic import ChatAnthropic
from src.core.llm.provider import BaseLLMProvider

class AnthropicClient(BaseLLMProvider):
    def get_chat_model(self) -> ChatAnthropic:
        return ChatAnthropic(
            model_name=self.model_name,
            api_key=self.api_key, # If None, langchain handles ANTHROPIC_API_KEY env var
            temperature=self.temperature,
            default_request_timeout=self.timeout,
            max_retries=0, # Retries handled explicitly by BaseLLMProvider
        )
```

---

## 6. Edge Cases & Safeguards

1. **Null Structured Output**:
   - Some models might return `None` or an empty object if structured output parsing fails silently. `generate_structured` explicitly checks `if result is None:` and raises `ValidationError`.
2. **Empty Prompt Inputs**:
   - Calling `generate_structured("", response_model)` checks prompt presence upfront and raises `ValidationError("Prompt cannot be empty or null")` before making an API call.
3. **Thundering Herd Mitigation**:
   - The exponential backoff algorithm uses full jitter (`random.uniform(0.5 * capped_delay, capped_delay)`) so that concurrent pipeline workers do not synchronize retry requests against rate-limited endpoints.
4. **Preservation of Exception Chain**:
   - When raising translated exceptions, `raise translated_exc from raw_exc` is used so that original stack traces are preserved for debugging.

---

## 7. Verification & Testing Strategy (`tests/llm/test_providers.py`)

### 7.1 Test Cases for `BaseLLMProvider`
1. **Successful Structured Generation**:
   - Mock `get_chat_model().with_structured_output().invoke()` returning a valid `VideoMetadata` object.
   - Assert `generate_structured()` returns exact object without error.
2. **Retry on Rate Limit (HTTP 429)**:
   - Mock `invoke()` raising `openai.RateLimitError` on attempts 1 and 2, and succeeding on attempt 3.
   - Assert method retries 2 times, sleeps for backoff, and returns result on 3rd attempt.
3. **Retry Exhaustion**:
   - Mock `invoke()` raising `RateLimitError` on all attempts (e.g. max_retries=3 -> 4 attempts).
   - Assert `RateLimitError` is raised after 4 attempts.
4. **Immediate Fatal Failure on Validation/Auth Error**:
   - Mock `invoke()` raising `pydantic.ValidationError` or `openai.AuthenticationError`.
   - Assert exception is translated immediately into `ValidationError` or `AuthenticationError` on attempt 1 without retrying.

---

## 8. Summary of Interface Contracts

- **File**: `src/core/llm/provider.py`
- **Class**: `BaseLLMProvider(abc.ABC)`
- **Constructor Signature**:
  `__init__(model_name: str, api_key: str | None = None, temperature: float = 0.0, max_retries: int = 3, timeout: float = 60.0, initial_backoff: float = 1.0, backoff_factor: float = 2.0, max_backoff: float = 30.0)`
- **Abstract Method**: `@abc.abstractmethod get_chat_model() -> BaseChatModel`
- **Primary Method**: `generate_structured(prompt: str | list[Any], response_model: type[T]) -> T`
- **Helper Methods**: `_translate_exception(exc: Exception) -> PipelineError`, `_calculate_backoff_delay(attempt: int) -> float`
