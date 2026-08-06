"""
Anthropic LLM Provider Client Wrapper.

Provides AnthropicClient wrapping LangChain's ChatAnthropic with structured output capabilities.
"""

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
        initial_backoff: float = 1.0,
        backoff_factor: float = 2.0,
        max_backoff: float = 30.0,
    ) -> None:
        """
        Initialize the Anthropic client with configuration defaults and overrides.

        Args:
            model_name: Optional model override (defaults to config.llm.anthropic.default_model).
            api_key: Optional API key override.
            temperature: Optional temperature override.
            max_retries: Optional max retries override.
            timeout: Optional timeout override in seconds.
            initial_backoff: Initial backoff delay in seconds (default 1.0).
            backoff_factor: Multiplier factor for backoff (default 2.0).
            max_backoff: Maximum backoff delay cap in seconds (default 30.0).
        """
        try:
            config = load_config().llm.anthropic
        except Exception:
            # Fallback if config loading fails in testing environments
            config = None

        env_model = os.getenv("ANTHROPIC_MODEL")
        resolved_model = model_name or env_model or (config.default_model if config else "claude-3-5-sonnet-20240620")
        resolved_temp = (
            temperature if temperature is not None else (config.temperature if config else 0.0)
        )
        resolved_retries = (
            max_retries if max_retries is not None else (config.max_retries if config else 3)
        )
        resolved_timeout = (
            timeout if timeout is not None else (config.timeout_seconds if config else 60.0)
        )

        resolved_api_key: str = ""
        if api_key is not None:
            resolved_api_key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        elif config and config.api_key.get_secret_value():
            resolved_api_key = config.api_key.get_secret_value()
        else:
            resolved_api_key = os.getenv("ANTHROPIC_API_KEY", "")

        super().__init__(
            model_name=resolved_model,
            api_key=resolved_api_key,
            temperature=resolved_temp,
            max_retries=resolved_retries,
            timeout=resolved_timeout,
            initial_backoff=initial_backoff,
            backoff_factor=backoff_factor,
            max_backoff=max_backoff,
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
