"""
Unit tests for configuration hydration via Pydantic V2 and pydantic-settings.
"""

import os
from pathlib import Path
import pytest
from pydantic import ValidationError
from src.core.config import (
    Environment,
    GeminiConfig,
    PipelineConfig,
    RAGConfig,
    ScraperConfig,
    YouTubeConfig,
    load_config,
)


def test_default_config_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that PipelineConfig initializes with sensible defaults."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    config = PipelineConfig()
    assert config.environment == Environment.DEVELOPMENT
    assert config.log_level == "INFO"
    assert config.data_dir == Path("data")
    assert isinstance(config.scraper, ScraperConfig)
    assert isinstance(config.rag, RAGConfig)
    assert isinstance(config.gemini, GeminiConfig)
    assert isinstance(config.youtube, YouTubeConfig)
    assert config.scraper.timeout_seconds == 10
    assert config.scraper.max_retries == 3
    assert config.rag.collection_name == "dsa_knowledge"


def test_environment_variable_hydration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that environment variables correctly hydrate root and nested Pydantic settings."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DATA_DIR", "/custom/data/path")
    monkeypatch.setenv("SCRAPER__TIMEOUT_SECONDS", "25")
    monkeypatch.setenv("SCRAPER__MAX_RETRIES", "5")
    monkeypatch.setenv("GEMINI__API_KEY", "test-gemini-key-12345")
    monkeypatch.setenv("RAG__COLLECTION_NAME", "custom_rag_collection")

    config = PipelineConfig()

    assert config.environment == Environment.PRODUCTION
    assert config.log_level == "DEBUG"
    assert config.data_dir == Path("/custom/data/path")
    assert config.scraper.timeout_seconds == 25
    assert config.scraper.max_retries == 5
    assert config.gemini.api_key.get_secret_value() == "test-gemini-key-12345"
    assert config.rag.collection_name == "custom_rag_collection"


def test_load_config_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the load_config() utility function with environment overrides and programmatic overrides."""
    monkeypatch.setenv("ENVIRONMENT", "testing")
    
    overrides = {
        "log_level": "WARNING",
        "scraper": {"max_retries": 10},
    }
    
    config = load_config(overrides=overrides)
    assert config.environment == Environment.TESTING
    assert config.log_level == "WARNING"
    assert config.scraper.max_retries == 10


def test_invalid_config_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that invalid values raise Pydantic ValidationError."""
    monkeypatch.setenv("SCRAPER__TIMEOUT_SECONDS", "0")  # Violates ge=1 constraint

    with pytest.raises(ValidationError):
        PipelineConfig()


def test_secret_str_handling() -> None:
    """Test SecretStr protection for sensitive API keys."""
    config = GeminiConfig(api_key="secret-key-abc")
    assert str(config.api_key) == "**********" or "secret-key-abc" not in str(config.api_key)
    assert config.api_key.get_secret_value() == "secret-key-abc"
