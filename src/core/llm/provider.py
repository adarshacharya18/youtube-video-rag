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
