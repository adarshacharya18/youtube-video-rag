"""
Configuration management via Pydantic Settings.

This module provides strongly-typed configuration loaded from environment
variables, .env files, and programmatic overrides. It uses Pydantic's
env_nested_delimiter to parse sub-configurations (e.g., SCRAPER__MAX_RETRIES).
"""

import os
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment profiles."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class ScraperConfig(BaseSettings):
    """Configuration for LeetCode scraping (Module 1)."""

    session_cookie: SecretStr = Field(
        default=SecretStr(""), 
        description="LeetCode LEETCODE_SESSION cookie"
    )
    timeout_seconds: int = Field(default=10, ge=1)
    max_retries: int = Field(default=3, ge=0)
    graphql_url: str = Field(default="https://leetcode.com/graphql")


class RAGConfig(BaseSettings):
    """Configuration for RAG Knowledge Engine (Module 3)."""

    chroma_db_dir: Path = Field(default=Path("data/vector_store/chroma"))
    knowledge_base_dir: Path = Field(default=Path("data/knowledge_base"))
    collection_name: str = Field(default="dsa_knowledge")
    top_k: int = Field(default=10, ge=1, le=50)
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    embedding_model: str = Field(default="text-embedding-3-small")
    embedding_dim: int = Field(default=1536)
    use_mock_embedder: bool = Field(default=False)



class GeminiConfig(BaseSettings):
    """Configuration for Gemini LLM calls (Modules 2 & 4)."""

    api_key: SecretStr = Field(
        default=SecretStr(""), 
        description="Google Gemini API Key"
    )
    script_model: str = Field(default="gemini-1.5-pro")
    tag_model: str = Field(default="gemini-1.5-flash")


class YouTubeConfig(BaseSettings):
    """Configuration for YouTube Upload (Module 8)."""

    api_key: SecretStr = Field(
        default=SecretStr(""), 
        description="YouTube Data API Key"
    )
    client_secret_file: Path = Field(default=Path("config/client_secrets.json"))


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


class PromptConfig(BaseSettings):
    """Configuration for Prompt Loader and Jinja2 Template Library."""

    template_dir: Path = Field(
        default=Path("src/core/llm/prompts"),
        description="Root directory containing versioned Jinja2 prompt templates",
    )
    default_version: str = Field(
        default="v1",
        description="Default prompt template version folder",
    )


class LLMConfig(BaseSettings):
    """Root configuration aggregator for LLM providers."""

    default_provider: str = Field(
        default="openai",
        description="Default LLM provider name ('openai' or 'anthropic')"
    )
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    prompts: PromptConfig = Field(default_factory=PromptConfig)


class PipelineConfig(BaseSettings):
    """
    Root configuration object spanning the entire pipeline.
    
    Sub-configurations can be overridden using the double-underscore syntax
    in environment variables. For example, to override the scraper timeout,
    set SCRAPER__TIMEOUT_SECONDS=20.
    """

    environment: Environment = Field(default=Environment.DEVELOPMENT)
    log_level: str = Field(default="INFO")
    data_dir: Path = Field(default=Path("data"))
    
    # Sub-configs
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    prompts: PromptConfig = Field(default_factory=PromptConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


def load_config(
    env_file: str | Path | None = None, 
    overrides: dict[str, Any] | None = None
) -> PipelineConfig:
    """
    Load configuration from environment variables, .env files, and overrides.
    
    The target environment is determined by the `ENVIRONMENT` env var.
    It attempts to load `.env.{environment}` if it exists, falling back to 
    `.env` if no specific file is found. Programmatic overrides take highest precedence.

    Args:
        env_file: Optional explicit path to a .env file.
        overrides: Dictionary of config overrides (useful for dependency injection in tests).

    Returns:
        A validated PipelineConfig instance.
    """
    # 1. Determine Environment
    env_name = os.getenv("ENVIRONMENT", Environment.DEVELOPMENT.value)
    
    # 2. Determine File
    target_env_file = env_file
    if not target_env_file:
        specific_env = Path(f".env.{env_name}")
        target_env_file = specific_env if specific_env.exists() else Path(".env")
        
    # 3. Load & Validate (Pydantic automatically pulls from OS env vars + env file)
    config = PipelineConfig(_env_file=target_env_file)
    
    # 4. Apply manual programmatic overrides
    if overrides:
        # We recursively dump and merge dicts to allow overriding nested fields easily
        config_dict = config.model_dump()
        _deep_merge(config_dict, overrides)
        config = PipelineConfig.model_validate(config_dict)
        
    return config


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> None:
    """Recursively merge dictionary `updates` into `base`."""
    for key, value in updates.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
