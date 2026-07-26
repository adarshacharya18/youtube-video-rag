"""
LLM Provider Abstraction Module.

Provides unified abstract base interface BaseLLMProvider and concrete client wrappers
(OpenAIClient, AnthropicClient) for structured output generation across the pipeline.
"""

from src.core.llm.anthropic_client import AnthropicClient
from src.core.llm.openai_client import OpenAIClient
from src.core.llm.provider import BaseLLMProvider

__all__ = [
    "BaseLLMProvider",
    "OpenAIClient",
    "AnthropicClient",
]
