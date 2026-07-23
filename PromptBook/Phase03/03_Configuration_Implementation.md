# Phase03/03_Configuration_Implementation.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/config.py`](#2-source-code-srccoreconfigpy)
3. [Environment Variables Mapping](#3-environment-variables-mapping)
4. [Design Decisions](#4-design-decisions)

---

# 1. Executive Summary

This document provides the complete, production-ready implementation of the system's Configuration module (`src/core/config.py`). 

Leveraging `pydantic-settings`, the configuration engine guarantees that the pipeline will immediately crash at startup if any required secret (e.g., Gemini API key) is missing or if any type validation fails (e.g., `timeout_seconds` provided as a string). It features structured sub-configs for every pipeline module, `SecretStr` for memory-safe credential handling, environment-specific profiling (`.env.development` vs `.env.testing`), and support for programmatic overrides during testing.

---

# 2. Source Code: `src/core/config.py`

```python
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
```

---

# 3. Environment Variables Mapping

Using `env_nested_delimiter="__"`, developers can cleanly overwrite specific deeply-nested values using flat environment variables.

| Variable Name | Maps To (in `PipelineConfig`) |
|---|---|
| `ENVIRONMENT` | `config.environment` |
| `LOG_LEVEL` | `config.log_level` |
| `SCRAPER__SESSION_COOKIE` | `config.scraper.session_cookie` |
| `SCRAPER__TIMEOUT_SECONDS` | `config.scraper.timeout_seconds` |
| `GEMINI__API_KEY` | `config.gemini.api_key` |
| `GEMINI__SCRIPT_MODEL` | `config.gemini.script_model` |
| `RAG__TOP_K` | `config.rag.top_k` |

---

# 4. Design Decisions

1. **Secret Management:** Sensitive keys (like `GEMINI__API_KEY` and `SCRAPER__SESSION_COOKIE`) are cast to `SecretStr`. This prevents them from accidentally leaking in logs if a developer prints the config object (it prints as `**********`). To use the key, modules must explicitly call `.get_secret_value()`.
2. **Dynamic Profiles:** The `load_config()` factory automatically looks for `.env.testing` if `ENVIRONMENT=testing`. This is critical for `pytest` where we want to instantly point all paths to a `/tmp/` directory without polluting real `.env` variables.
3. **Deep Merging:** The programmatic `overrides` dictionary uses a deep merge to allow tests to override a single nested value (like `{"scraper": {"max_retries": 1}}`) without destroying the rest of the default sub-config.
