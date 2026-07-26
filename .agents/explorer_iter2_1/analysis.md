# Fix Strategy Analysis — LLM Provider Abstraction (Iteration 2)

**Agent Identity**: `explorer_iter2_1` (Role: Fix Strategy Explorer)  
**Date**: 2026-07-26  
**Target Modules**:
- `src/core/llm/provider.py`
- `tests/llm/test_providers.py`

---

## 1. Executive Summary

In Iteration 1, Challenger 1 (`challenger_iter1_1`) identified 3 defects in `src/core/llm/provider.py` during empirical stress testing:
1. **Input Validation Defect**: `generate_structured()` does not validate empty prompt lists `[]`, non-string/non-list types (`int`, `dict`), or message objects/dicts with empty/whitespace content.
2. **Exception Translation Defect**: Asymmetrical keyword matching in `_translate_exception()` fails when vendor SDK or LangChain exceptions are wrapped in generic exception classes (e.g., `Exception("RateLimitError: ...")`), and fails to map Anthropic HTTP status 529 to retryable network errors.
3. **Dead Code**: Line 162 (`raise NetworkError(...)`) in `src/core/llm/provider.py` is unreachable.

This analysis provides the exact root causes, step-by-step logic chains, exact code replacement specifications for `src/core/llm/provider.py`, and test additions for `tests/llm/test_providers.py`.

---

## 2. Defect 1: Input Validation Defect in `generate_structured()`

### 2.1 Observation & Root Cause
- **Location**: `src/core/llm/provider.py`, lines 103–104:
  ```python
  if prompt is None or (isinstance(prompt, str) and not prompt.strip()):
      raise ValidationError("Prompt cannot be empty or null")
  ```
- **Root Cause**:
  - The check `isinstance(prompt, str) and not prompt.strip()` only executes when `prompt` is a `str`.
  - When `prompt` is an empty list `[]`, `isinstance(prompt, str)` evaluates to `False`. The check passes without raising `ValidationError`, and `structured_llm.invoke([])` is called.
  - When `prompt` is a non-string / non-list type (e.g. `12345` or `{"key": "val"}`), it passes line 103 validation and reaches the LLM runnable, causing unhandled runtime errors downstream.
  - When `prompt` is a message list containing empty content (e.g. `[HumanMessage(content="")]`, `[{"role": "user", "content": "  "}]`), line 103 passes because it does not inspect list element contents.

### 2.2 Exact Fix Strategy for `src/core/llm/provider.py`
Add a dedicated prompt validation helper method `_validate_prompt(self, prompt: Any) -> None` and invoke it at the start of `generate_structured()`.

```python
def _validate_prompt(self, prompt: Any) -> None:
    """
    Validate that prompt is a non-empty string or a non-empty list of valid messages.

    Raises:
        ValidationError: If prompt is None, empty, whitespace-only, wrong type,
                        or contains empty message contents.
    """
    if prompt is None:
        raise ValidationError("Prompt cannot be empty or null")

    if isinstance(prompt, str):
        if not prompt.strip():
            raise ValidationError("Prompt string cannot be empty or whitespace")
        return

    if isinstance(prompt, list):
        if len(prompt) == 0:
            raise ValidationError("Prompt message list cannot be empty")
        for item in prompt:
            if item is None:
                raise ValidationError("Prompt message list contains null item")
            
            # Extract content from message object, dictionary, or string
            if hasattr(item, "content"):
                content = item.content
            elif isinstance(item, dict):
                content = item.get("content", "")
            elif isinstance(item, str):
                content = item
            else:
                content = str(item)

            if isinstance(content, str):
                if not content.strip():
                    raise ValidationError("Prompt message list contains empty or whitespace-only message content")
            elif isinstance(content, list):
                has_text = any(
                    (isinstance(c, str) and bool(c.strip())) or
                    (isinstance(c, dict) and bool(str(c.get("text", "")).strip()))
                    for c in content
                )
                if not has_text:
                    raise ValidationError("Prompt message list contains empty or whitespace-only message content")
            elif not str(content).strip():
                raise ValidationError("Prompt message list contains empty or whitespace-only message content")
        return

    raise ValidationError(f"Prompt must be a string or list of messages, got {type(prompt).__name__}")
```

In `generate_structured()`, replace lines 103–104 with:
```python
self._validate_prompt(prompt)
```

---

## 3. Defect 2: Exception Translation Defect in `_translate_exception()`

### 3.1 Observation & Root Cause
- **Location**: `src/core/llm/provider.py`, lines 183–202:
  ```python
  # 1. Rate Limits (HTTP 429)
  if status_code == 429 or "ratelimit" in exc_name.lower() or "rate limit" in exc_str or "429" in exc_str:
      return RateLimitError(f"LLM rate limit exceeded: {exc}")

  # 2. Authentication / Authorization (HTTP 401, 403)
  if status_code in (401, 403) or "auth" in exc_name.lower() or "unauthorized" in exc_str or "api key" in exc_str:
      return AuthenticationError(f"LLM authentication failed: {exc}")

  # 3. Validation / Structured Output Parser Failures
  if "validation" in exc_name.lower() or "outputparser" in exc_name.lower() or "json" in exc_str:
      return ValidationError(f"LLM structured output validation failed: {exc}")

  # 4. Network / Timeouts / Connection / HTTP 5xx Server Errors
  if (
      isinstance(exc, (TimeoutError, ConnectionError))
      or status_code in (500, 502, 503, 504)
      or any(kw in exc_name.lower() for kw in ["timeout", "connection", "network", "httperror"])
      or any(kw in exc_str for kw in ["timeout", "connection refused", "503", "500", "overloaded"])
  ):
      return NetworkError(f"LLM network issue: {exc}")
  ```
- **Root Cause**:
  1. **Asymmetrical matching**: Keywords `"validation"` and `"auth"` were checked ONLY against `exc_name.lower()`, NOT against `exc_str`. When generic exception wrappers like `SDKError("RateLimitError: ...")` or `SDKError("ValidationError: ...")` or `SDKError("AuthenticationError: ...")` were raised, `exc_name` was `"SDKError"`, causing string match failures and falling through to `FatalError`.
  2. **Rate Limit string mismatch**: `exc_str` checked `"rate limit"` (with space), but SDK strings like `RateLimitError` produce `"ratelimiterror"` without space.
  3. **Anthropic HTTP 529 & Network Resets**: HTTP status code 529 (Anthropic overloaded) was missing from status code check `(500, 502, 503, 504)`. Generic connection reset strings like `"connection lost"` did not match `"connection refused"`.

### 3.2 Exact Fix Strategy for `src/core/llm/provider.py`
Symmetrize keyword searching by inspecting a combined search string `full_text = f"{exc_name} {exc_str}".lower()` and add status code 529 to retryable network error status codes.

```python
def _translate_exception(self, exc: Exception) -> PipelineError:
    """
    Translate external SDK exceptions into PipelineError domain types.
    """
    if isinstance(exc, PipelineError):
        return exc

    exc_name = exc.__class__.__name__
    exc_str = str(exc).lower()
    full_text = f"{exc_name} {exc_str}".lower()
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)

    # 1. Rate Limits (HTTP 429)
    if (
        status_code == 429
        or any(kw in full_text for kw in ["ratelimit", "rate limit", "rate_limit", "429", "too many requests", "tpm limit", "rpm limit", "quota exceeded"])
    ):
        return RateLimitError(f"LLM rate limit exceeded: {exc}")

    # 2. Authentication / Authorization (HTTP 401, 403)
    if (
        status_code in (401, 403)
        or any(kw in full_text for kw in ["auth", "unauthorized", "api key", "apikey", "permission", "access denied", "forbidden", "invalid key"])
    ):
        return AuthenticationError(f"LLM authentication failed: {exc}")

    # 3. Validation / Structured Output Parser Failures
    if any(kw in full_text for kw in ["validation", "outputparser", "json", "schema", "pydantic"]):
        return ValidationError(f"LLM structured output validation failed: {exc}")

    # 4. Network / Timeouts / Connection / HTTP 5xx Server Errors (including Anthropic HTTP 529)
    if (
        isinstance(exc, (TimeoutError, ConnectionError))
        or status_code in (500, 502, 503, 504, 529)
        or any(kw in full_text for kw in ["timeout", "connection", "network", "httperror", "overloaded", "529", "500", "502", "503", "504", "server error", "service unavailable"])
    ):
        return NetworkError(f"LLM network issue: {exc}")

    # Fallback for unexpected errors
    return FatalError(f"LLM provider unclassified error ({exc_name}): {exc}")
```

---

## 4. Defect 3: Unreachable Dead Code

### 4.1 Observation & Root Cause
- **Location**: `src/core/llm/provider.py`, line 162:
  ```python
  raise NetworkError(f"LLM request failed after {self.max_retries} retries")
  ```
- **Root Cause**: The loop condition `while attempt <= max_attempts:` handles all iterations. On success, line 135 returns `result`. On error, if `attempt == max_attempts`, line 160 raises `translated_exc`. Line 162 is unreachable under all conditions.

### 4.2 Exact Fix Strategy for `src/core/llm/provider.py`
Remove line 162 completely.

---

## 5. Complete Proposed Replacement Code for `src/core/llm/provider.py`

```python
"""
LLM Provider Abstraction Module.

Defines the abstract base class BaseLLMProvider for structured LLM generation,
implementing exponential backoff retry logic and central exception translation.
"""

import abc
import random
import time
from typing import Any, TypeVar

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
    Abstract base class for LLM providers providing structured output generation.

    Subclasses must implement `get_chat_model()` to configure and return a
    LangChain `BaseChatModel` instance.
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
        Initialize base LLM provider configurations.

        Args:
            model_name: Name of the LLM model (e.g. 'gpt-4o', 'claude-3-5-sonnet-20240620').
            api_key: Optional secret API key string.
            temperature: Sampling temperature (default 0.0).
            max_retries: Maximum number of retries for retryable errors (default 3).
            timeout: HTTP request timeout in seconds (default 60.0).
            initial_backoff: Initial backoff delay in seconds (default 1.0).
            backoff_factor: Exponential multiplier factor (default 2.0).
            max_backoff: Maximum delay ceiling in seconds (default 30.0).
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
        Abstract factory method returning configured LangChain BaseChatModel instance.
        """
        pass

    def _validate_prompt(self, prompt: Any) -> None:
        """
        Validate that prompt is a non-empty string or a non-empty list of valid messages.

        Raises:
            ValidationError: If prompt is None, empty string/list, wrong data type,
                            or contains empty message contents.
        """
        if prompt is None:
            raise ValidationError("Prompt cannot be empty or null")

        if isinstance(prompt, str):
            if not prompt.strip():
                raise ValidationError("Prompt string cannot be empty or whitespace")
            return

        if isinstance(prompt, list):
            if len(prompt) == 0:
                raise ValidationError("Prompt message list cannot be empty")
            for item in prompt:
                if item is None:
                    raise ValidationError("Prompt message list contains null item")

                if hasattr(item, "content"):
                    content = item.content
                elif isinstance(item, dict):
                    content = item.get("content", "")
                elif isinstance(item, str):
                    content = item
                else:
                    content = str(item)

                if isinstance(content, str):
                    if not content.strip():
                        raise ValidationError("Prompt message list contains empty or whitespace-only message content")
                elif isinstance(content, list):
                    has_text = any(
                        (isinstance(c, str) and bool(c.strip()))
                        or (isinstance(c, dict) and bool(str(c.get("text", "")).strip()))
                        for c in content
                    )
                    if not has_text:
                        raise ValidationError("Prompt message list contains empty or whitespace-only message content")
                elif not str(content).strip():
                    raise ValidationError("Prompt message list contains empty or whitespace-only message content")
            return

        raise ValidationError(f"Prompt must be a string or list of messages, got {type(prompt).__name__}")

    def generate_structured(
        self,
        prompt: str | list[Any],
        response_model: type[T],
    ) -> T:
        """
        Generate a structured output enforced by a Pydantic model schema.

        Args:
            prompt: User prompt string or list of message objects.
            response_model: Target Pydantic model class.

        Returns:
            An instance of `response_model` populated with parsed output.

        Raises:
            ValidationError: If prompt is empty/invalid or output parsing/validation fails.
            RateLimitError: If provider rate limit persists after max retries.
            NetworkError: If network issue persists after max retries.
            AuthenticationError: If API authentication fails.
            PipelineError: For fatal provider issues.
        """
        self._validate_prompt(prompt)

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

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.
        """
        exponential_delay = self.initial_backoff * (self.backoff_factor ** (attempt - 1))
        capped_delay = min(self.max_backoff, exponential_delay)
        return random.uniform(0.5 * capped_delay, capped_delay)

    def _translate_exception(self, exc: Exception) -> PipelineError:
        """
        Translate external SDK exceptions into PipelineError domain types.
        """
        if isinstance(exc, PipelineError):
            return exc

        exc_name = exc.__class__.__name__
        exc_str = str(exc).lower()
        full_text = f"{exc_name} {exc_str}".lower()
        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)

        # 1. Rate Limits (HTTP 429)
        if (
            status_code == 429
            or any(
                kw in full_text
                for kw in ["ratelimit", "rate limit", "rate_limit", "429", "too many requests", "tpm limit", "rpm limit", "quota exceeded"]
            )
        ):
            return RateLimitError(f"LLM rate limit exceeded: {exc}")

        # 2. Authentication / Authorization (HTTP 401, 403)
        if (
            status_code in (401, 403)
            or any(
                kw in full_text
                for kw in ["auth", "unauthorized", "api key", "apikey", "permission", "access denied", "forbidden", "invalid key"]
            )
        ):
            return AuthenticationError(f"LLM authentication failed: {exc}")

        # 3. Validation / Structured Output Parser Failures
        if any(kw in full_text for kw in ["validation", "outputparser", "json", "schema", "pydantic"]):
            return ValidationError(f"LLM structured output validation failed: {exc}")

        # 4. Network / Timeouts / Connection / HTTP 5xx Server Errors (including Anthropic 529)
        if (
            isinstance(exc, (TimeoutError, ConnectionError))
            or status_code in (500, 502, 503, 504, 529)
            or any(
                kw in full_text
                for kw in [
                    "timeout",
                    "connection",
                    "network",
                    "httperror",
                    "overloaded",
                    "529",
                    "500",
                    "502",
                    "503",
                    "504",
                    "server error",
                    "service unavailable",
                ]
            )
        ):
            return NetworkError(f"LLM network issue: {exc}")

        # Fallback for unexpected errors
        return FatalError(f"LLM provider unclassified error ({exc_name}): {exc}")
```

---

## 6. Proposed Test Additions for `tests/llm/test_providers.py`

Append the following unit test functions to `tests/llm/test_providers.py`:

```python
from langchain_core.messages import HumanMessage


@pytest.mark.parametrize(
    "invalid_prompt",
    [
        [],
        12345,
        {"key": "val"},
        [""],
        ["   "],
        [HumanMessage(content="")],
        [HumanMessage(content="   ")],
        [{"role": "user", "content": "  "}],
    ],
)
def test_provider_boundary_prompt_validation_failures(monkeypatch_api_keys, invalid_prompt):
    """Test boundary prompt inputs (empty list, int, dict, empty message content) raise ValidationError upfront."""
    client = OpenAIClient()
    with pytest.raises(ValidationError) as exc_info:
        client.generate_structured(invalid_prompt, VideoMetadata)

    assert "prompt" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()


def test_provider_exception_translation_wrapped_sdk_errors(monkeypatch_api_keys):
    """Test translation of generic wrapped SDK exceptions into domain exception types."""
    client = OpenAIClient(max_retries=1, initial_backoff=0.01)

    class CustomSDKError(Exception):
        pass

    # 1. Wrapped Rate Limit Error
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_cls, patch("time.sleep"):
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        mock_runnable.invoke.side_effect = CustomSDKError("RateLimitError: 30000 TPM limit exceeded")
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_cls.return_value = mock_inst

        with pytest.raises(RateLimitError):
            client.generate_structured("Valid prompt", VideoMetadata)

    # 2. Wrapped Authentication Error
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_cls:
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        mock_runnable.invoke.side_effect = CustomSDKError("AuthenticationError: invalid key provided")
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_cls.return_value = mock_inst

        with pytest.raises(AuthenticationError):
            client.generate_structured("Valid prompt", VideoMetadata)

    # 3. Wrapped Validation Error
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_cls:
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        mock_runnable.invoke.side_effect = CustomSDKError("ValidationError: 1 validation error for VideoMetadata")
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_cls.return_value = mock_inst

        with pytest.raises(ValidationError):
            client.generate_structured("Valid prompt", VideoMetadata)

    # 4. Anthropic HTTP 529 Overloaded Error
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_cls, patch("time.sleep"):
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        err_529 = CustomSDKError("Error code: 529 - Anthropic Overloaded")
        err_529.status_code = 529
        mock_runnable.invoke.side_effect = err_529
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_cls.return_value = mock_inst

        with pytest.raises(NetworkError):
            client.generate_structured("Valid prompt", VideoMetadata)

    # 5. Connection Reset Error String
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_cls, patch("time.sleep"):
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        mock_runnable.invoke.side_effect = CustomSDKError("ConnectionResetError: Connection lost")
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_cls.return_value = mock_inst

        with pytest.raises(NetworkError):
            client.generate_structured("Valid prompt", VideoMetadata)
```
