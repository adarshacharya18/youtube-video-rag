# Comprehensive Design Document: OpenAI & Anthropic Clients and LLM Configuration

## Executive Summary

This design specification details the concrete LLM client wrappers `OpenAIClient` (`src/core/llm/openai_client.py`) and `AnthropicClient` (`src/core/llm/anthropic_client.py`), alongside the configuration structures (`OpenAIConfig`, `AnthropicConfig`, `LLMConfig`) to be added to `src/core/config.py`.

Both client classes subclass `BaseLLMProvider` (defined in `src/core/llm/provider.py`) and wrap LangChain's underlying `ChatOpenAI` and `ChatAnthropic` chat models. They leverage LangChain's `.with_structured_output()` mechanism to enforce strict output schema validation using Phase 05 Pydantic V2 models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`, `SEOMetadata`).

---

## 1. Configuration Architecture (`src/core/config.py`)

To support typed, validated configuration loading from environment variables and `.env` files via Pydantic Settings, three new configuration models will be added to `src/core/config.py`.

### 1.1 `OpenAIConfig`
Configuration model for OpenAI provider settings.

```python
class OpenAIConfig(BaseSettings):
    """Configuration for OpenAI LLM provider."""

    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="OpenAI API secret key"
    )
    default_model: str = Field(
        default="gpt-4o",
        description="Default OpenAI model identifier"
    )
    temperature: float = Field(
        default=0.0, ge=0.0, le=2.0,
        description="Sampling temperature for text generation"
    )
    max_retries: int = Field(
        default=3, ge=0,
        description="Maximum retry attempts for transient errors"
    )
    timeout_seconds: float = Field(
        default=60.0, ge=1.0,
        description="HTTP request timeout in seconds"
    )
    organization: str | None = Field(
        default=None,
        description="Optional OpenAI Organization ID"
    )
```

### 1.2 `AnthropicConfig`
Configuration model for Anthropic provider settings.

```python
class AnthropicConfig(BaseSettings):
    """Configuration for Anthropic LLM provider."""

    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Anthropic API secret key"
    )
    default_model: str = Field(
        default="claude-3-5-sonnet-20240620",
        description="Default Anthropic model identifier"
    )
    temperature: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Sampling temperature for text generation"
    )
    max_retries: int = Field(
        default=3, ge=0,
        description="Maximum retry attempts for transient errors"
    )
    timeout_seconds: float = Field(
        default=60.0, ge=1.0,
        description="HTTP request timeout in seconds"
    )
```

### 1.3 `LLMConfig` & Root `PipelineConfig` Integration
Root LLM configuration structure that aggregates provider configs and designates the active default provider.

```python
class LLMConfig(BaseSettings):
    """Root configuration aggregator for LLM providers."""

    default_provider: str = Field(
        default="openai",
        description="Default LLM provider name ('openai' or 'anthropic')"
    )
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
```

In `PipelineConfig`:
```python
class PipelineConfig(BaseSettings):
    ...
    # Existing sub-configs
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig)
    
    # New sub-config for LLM abstraction
    llm: LLMConfig = Field(default_factory=LLMConfig)
```

#### Environment Variable Overrides
Using Pydantic Settings' `env_nested_delimiter="__"`:
- `LLM__DEFAULT_PROVIDER="anthropic"`
- `LLM__OPENAI__API_KEY="sk-..."`
- `LLM__OPENAI__DEFAULT_MODEL="gpt-4o-mini"`
- `LLM__ANTHROPIC__API_KEY="sk-ant-..."`
- Standard env variables `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are also checked as fallback.

---

## 2. OpenAI Client Design (`src/core/llm/openai_client.py`)

### 2.1 Class Structure & Initialization Strategy
`OpenAIClient` inherits from `BaseLLMProvider` and wraps `langchain_openai.ChatOpenAI`.

```python
"""OpenAI LLM provider client wrapper."""

import os
from typing import Any, Optional, Union

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from src.core.config import load_config
from src.core.llm.provider import BaseLLMProvider


class OpenAIClient(BaseLLMProvider):
    """
    Concrete LLM provider implementation for OpenAI models.
    Wraps LangChain's ChatOpenAI with structured output capabilities.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[Union[str, SecretStr]] = None,
        temperature: Optional[float] = None,
        max_retries: Optional[int] = None,
        timeout: Optional[float] = None,
        organization: Optional[str] = None,
    ) -> None:
        """
        Initialize the OpenAI client with configuration defaults and overrides.

        Args:
            model_name: Optional override for model name (defaults to OpenAIConfig.default_model).
            api_key: Optional override for API key (defaults to OpenAIConfig or env var OPENAI_API_KEY).
            temperature: Optional override for temperature (defaults to OpenAIConfig.temperature).
            max_retries: Optional override for retry count (defaults to OpenAIConfig.max_retries).
            timeout: Optional override for request timeout in seconds (defaults to OpenAIConfig.timeout_seconds).
            organization: Optional OpenAI Organization ID.
        """
        config = load_config().llm.openai

        resolved_model = model_name or config.default_model
        resolved_temp = temperature if temperature is not None else config.temperature
        resolved_retries = max_retries if max_retries is not None else config.max_retries
        resolved_timeout = timeout if timeout is not None else config.timeout_seconds
        resolved_org = organization or config.organization

        # API Key Fallback Chain: passed arg -> config -> env var
        resolved_api_key: str = ""
        if api_key is not None:
            resolved_api_key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        elif config.api_key.get_secret_value():
            resolved_api_key = config.api_key.get_secret_value()
        else:
            resolved_api_key = os.getenv("OPENAI_API_KEY", "")

        super().__init__(
            model_name=resolved_model,
            api_key=resolved_api_key,
            temperature=resolved_temp,
            max_retries=resolved_retries,
            timeout=resolved_timeout,
        )
        self.organization = resolved_org
        self._chat_model: Optional[ChatOpenAI] = None

    def get_chat_model(self) -> BaseChatModel:
        """
        Instantiate or return cached LangChain ChatOpenAI instance.

        Returns:
            Configured BaseChatModel instance (ChatOpenAI).
        """
        if self._chat_model is None:
            kwargs: dict[str, Any] = {
                "model": self.model_name,
                "temperature": self.temperature,
                "max_retries": self.max_retries,
                "request_timeout": self.timeout,
            }
            if self.api_key:
                kwargs["api_key"] = SecretStr(self.api_key)
            if self.organization:
                kwargs["organization"] = self.organization

            self._chat_model = ChatOpenAI(**kwargs)
            
        return self._chat_model
```

---

## 3. Anthropic Client Design (`src/core/llm/anthropic_client.py`)

### 3.1 Class Structure & Initialization Strategy
`AnthropicClient` inherits from `BaseLLMProvider` and wraps `langchain_anthropic.ChatAnthropic`.

```python
"""Anthropic LLM provider client wrapper."""

import os
from typing import Any, Optional, Union

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from src.core.config import load_config
from src.core.llm.provider import BaseLLMProvider


class AnthropicClient(BaseLLMProvider):
    """
    Concrete LLM provider implementation for Anthropic Claude models.
    Wraps LangChain's ChatAnthropic with structured output capabilities.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[Union[str, SecretStr]] = None,
        temperature: Optional[float] = None,
        max_retries: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Initialize the Anthropic client with configuration defaults and overrides.

        Args:
            model_name: Optional override for model name (defaults to AnthropicConfig.default_model).
            api_key: Optional override for API key (defaults to AnthropicConfig or env var ANTHROPIC_API_KEY).
            temperature: Optional override for temperature (defaults to AnthropicConfig.temperature).
            max_retries: Optional override for retry count (defaults to AnthropicConfig.max_retries).
            timeout: Optional override for request timeout in seconds (defaults to AnthropicConfig.timeout_seconds).
        """
        config = load_config().llm.anthropic

        resolved_model = model_name or config.default_model
        resolved_temp = temperature if temperature is not None else config.temperature
        resolved_retries = max_retries if max_retries is not None else config.max_retries
        resolved_timeout = timeout if timeout is not None else config.timeout_seconds

        # API Key Fallback Chain: passed arg -> config -> env var
        resolved_api_key: str = ""
        if api_key is not None:
            resolved_api_key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        elif config.api_key.get_secret_value():
            resolved_api_key = config.api_key.get_secret_value()
        else:
            resolved_api_key = os.getenv("ANTHROPIC_API_KEY", "")

        super().__init__(
            model_name=resolved_model,
            api_key=resolved_api_key,
            temperature=resolved_temp,
            max_retries=resolved_retries,
            timeout=resolved_timeout,
        )
        self._chat_model: Optional[ChatAnthropic] = None

    def get_chat_model(self) -> BaseChatModel:
        """
        Instantiate or return cached LangChain ChatAnthropic instance.

        Returns:
            Configured BaseChatModel instance (ChatAnthropic).
        """
        if self._chat_model is None:
            kwargs: dict[str, Any] = {
                "model": self.model_name,
                "temperature": self.temperature,
                "max_retries": self.max_retries,
                "default_request_timeout": self.timeout,
            }
            if self.api_key:
                kwargs["api_key"] = SecretStr(self.api_key)

            self._chat_model = ChatAnthropic(**kwargs)

        return self._chat_model
```

---

## 4. Structured Output Integration with Phase 05 Pydantic Models

### 4.1 How `with_structured_output` Works Across Providers
Both `OpenAIClient` and `AnthropicClient` leverage `BaseLLMProvider.generate_structured(prompt, response_model)`.
Under the hood:
1. `chat_model = self.get_chat_model()` fetches `ChatOpenAI` or `ChatAnthropic`.
2. `structured_llm = chat_model.with_structured_output(schema=response_model)` produces a Runnable chain.
   - For `ChatOpenAI`: converts Pydantic schema (`VideoMetadata`, `EducationalPlan`, etc.) into OpenAI tool/function definitions or JSON schema enforcement.
   - For `ChatAnthropic`: converts Pydantic schema into Anthropic Tool Use definitions (`tools=[...]`).
3. Executing `structured_llm.invoke(prompt)` sends the request to the underlying model provider API and parses the response directly into an instance of `response_model`.

### 4.2 Supported Phase 05 Models
- `src.core.models.video.VideoMetadata`
- `src.core.models.plan.EducationalPlan`
- `src.core.models.assets.RenderSegment`
- `src.core.models.assets.AssetManifest`
- `src.core.models.video.SEOMetadata`

### 4.3 Execution Flow Diagram
```
[ Caller ] 
    │
    ▼ generate_structured(prompt, VideoMetadata)
[ OpenAIClient / AnthropicClient ] (inherits from BaseLLMProvider)
    │
    ▼ get_chat_model()
[ ChatOpenAI / ChatAnthropic ]
    │
    ▼ with_structured_output(VideoMetadata)
[ RunnableStructuredOutput ]
    │ (invokes API with retry/backoff)
    ▼
[ Parsed Pydantic Instance (VideoMetadata) ]
```

---

## 5. Resiliency & Provider Exception Handling

### 5.1 Provider Error Mapping Matrix

| Underlying Provider Exception | Cause | Target Pipeline Exception (`src/core/exceptions.py`) | Operational Classification |
|---|---|---|---|
| `openai.RateLimitError` / `anthropic.RateLimitError` | HTTP 429 Too Many Requests | `RateLimitError` | `RetryableError` |
| `openai.APIConnectionError` / `anthropic.APIConnectionError` | TCP/HTTP timeout or connection reset | `NetworkError` | `RetryableError` |
| `openai.InternalServerError` / `anthropic.InternalServerError` | HTTP 5xx server-side failure | `RetryableError` | `RetryableError` |
| `openai.AuthenticationError` / `anthropic.AuthenticationError` | Invalid or missing API Key | `AuthenticationError` | `FatalError` |
| `langchain_core.exceptions.OutputParserException` / `pydantic.ValidationError` | Invalid LLM JSON response failing schema | `ValidationError` | `FatalError` |

### 5.2 Retry Logic Coordination
The retry/backoff mechanism is centrally implemented in `BaseLLMProvider.generate_structured()`, which wraps the `structured_llm.invoke()` call inside exponential backoff retry loops using standard `tenacity` or custom backoff retry loops, filtering on `RetryableError` types.

---

## 6. Summary of Proposed Code Changes

1. **`src/core/config.py`**:
   - Add `OpenAIConfig`, `AnthropicConfig`, `LLMConfig`.
   - Add `llm: LLMConfig = Field(default_factory=LLMConfig)` to `PipelineConfig`.
2. **`src/core/llm/openai_client.py`**:
   - Implement `OpenAIClient(BaseLLMProvider)` wrapping `ChatOpenAI`.
3. **`src/core/llm/anthropic_client.py`**:
   - Implement `AnthropicClient(BaseLLMProvider)` wrapping `ChatAnthropic`.
