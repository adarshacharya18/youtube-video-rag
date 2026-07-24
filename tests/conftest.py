"""
Global pytest fixtures and configuration.

Provides temporary environments, data factories, and test utilities 
across the test suite.
"""

import os
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest

from src.core.config import PipelineConfig, load_config

# Force testing environment so .env.testing is loaded automatically
os.environ["ENVIRONMENT"] = "testing"


# ==========================================
# 1. Environment & Configuration
# ==========================================

@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Isolated temporary directory for test data generation."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def test_config(temp_data_dir: Path) -> PipelineConfig:
    """
    Returns a deterministic PipelineConfig where all file I/O 
    is safely re-routed to the pytest tmp_path.
    """
    return load_config(overrides={
        "data_dir": temp_data_dir,
        "scraper": {"max_retries": 1},  # Fail fast in tests
        "log_level": "DEBUG"
    })


# ==========================================
# 2. Mock Services & Utilities
# ==========================================

@pytest.fixture
def mock_logger(mocker: Any) -> MagicMock:
    """
    Mocks the structlog logger to prevent terminal spam during tests.
    Uses pytest-mock (mocker).
    """
    return mocker.patch("src.core.logger.get_logger")


# ==========================================
# 3. Data Factories
# ==========================================

@pytest.fixture
def mock_problem_factory() -> Callable[..., dict[str, Any]]:
    """Returns a factory function to generate dummy ScrapedProblem payload dicts."""
    def _create_problem(slug: str = "two-sum", difficulty: str = "Easy") -> dict[str, Any]:
        return {
            "slug": slug,
            "title": slug.replace("-", " ").title(),
            "difficulty": difficulty,
            "tags": ["Array", "Hash Table"],
            "cpp_code": "class Solution { public: vector<int> twoSum() {} };"
        }
    return _create_problem
