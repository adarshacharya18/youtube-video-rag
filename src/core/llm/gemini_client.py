"""
Gemini LLM Provider Client Wrapper.

Provides GeminiClient wrapping LangChain's ChatGoogleGenerativeAI with structured output capabilities.
"""

import os
from typing import Any, Optional, Union

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from src.core.llm.provider import BaseLLMProvider


class GeminiClient(BaseLLMProvider):
    """
    Concrete LLM provider implementation for Google Gemini models.
    Wraps LangChain's ChatGoogleGenerativeAI with structured output capabilities.
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
        Initialize the Gemini client with configuration defaults and overrides.

        Args:
            model_name: Optional model override. Defaults to 'gemini-1.5-flash'.
            api_key: Optional API key override.
            temperature: Optional temperature override.
            max_retries: Optional max retries override.
            timeout: Optional timeout override in seconds.
            initial_backoff: Initial backoff delay in seconds (default 1.0).
            backoff_factor: Multiplier factor for backoff (default 2.0).
            max_backoff: Maximum backoff delay cap in seconds (default 30.0).
        """
        resolved_model = model_name or "gemini-3.5-flash"
        resolved_temp = temperature if temperature is not None else 0.0
        resolved_retries = max_retries if max_retries is not None else 3
        resolved_timeout = timeout if timeout is not None else 60.0

        resolved_api_key: str = ""
        if api_key is not None:
            resolved_api_key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        else:
            resolved_api_key = os.getenv("GEMINI_API_KEY", "")

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
        self._chat_model: Optional[ChatGoogleGenerativeAI] = None

    def get_chat_model(self) -> BaseChatModel:
        """
        Instantiate or return cached LangChain ChatGoogleGenerativeAI instance.

        Returns:
            Configured BaseChatModel instance (ChatGoogleGenerativeAI).
        """
        if self._chat_model is None:
            kwargs: dict[str, Any] = {
                "model": self.model_name,
                "temperature": self.temperature,
                "max_retries": self.max_retries,
                "timeout": self.timeout,
            }
            if self.api_key:
                kwargs["google_api_key"] = SecretStr(self.api_key)

            self._chat_model = ChatGoogleGenerativeAI(**kwargs)

        return self._chat_model
