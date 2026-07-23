# Phase03/11_Testing_Framework.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Pytest Configuration (`pytest.ini`)](#2-pytest-configuration-pytestini)
3. [Global Fixtures (`tests/conftest.py`)](#3-global-fixtures-testsconftestpy)
4. [Design Decisions](#4-design-decisions)

---

# 1. Executive Summary

This document establishes the robust, reusable testing infrastructure for the entire pipeline. Rather than writing brittle tests that pollute the local filesystem or hit live APIs, this framework guarantees complete test isolation. 

It accomplishes this via:
- **Pytest Markers:** Strict semantic categorization of tests (`@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.performance`).
- **Temporary Scoping:** Overriding the `PipelineConfig` to map the `data_dir` to pytest's ephemeral `tmp_path`, preventing tests from ever overwriting actual ChromaDB or output files.
- **Dependency Injection Mocks:** Reusing our `Container` to cleanly inject mocked services without resorting to global monkey-patching.

---

# 2. Pytest Configuration (`pytest.ini`)

To ensure standard test execution across all development environments, we lock the test runner configuration. This enables strict markers and automated coverage reports.

```ini
[pytest]
# Enforce strict markers so typos like @pytest.mark.uint fail immediately
addopts = --strict-markers --cov=src --cov-report=term-missing -v
testpaths = tests

# Marker definitions
markers =
    unit: Fast, isolated unit tests that do not touch the filesystem or network.
    integration: Tests that wire multiple modules together or hit the local filesystem.
    e2e: Full end-to-end pipeline execution tests.
    performance: Slow execution tests profiling time/memory (e.g. video rendering).
```

---

# 3. Global Fixtures (`tests/conftest.py`)

These fixtures are automatically available to every test file in the `tests/` tree.

```python
"""
Global pytest fixtures and configuration.

Provides temporary environments, mock DI containers, data factories,
and test utilities across the entire test suite.
"""

import os
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest

from src.core.config import PipelineConfig, load_config
from src.core.container import Container
from src.core.lifecycle import build_container

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


@pytest.fixture
def test_container(test_config: PipelineConfig) -> Container:
    """Returns a completely fresh, isolated DI Container for each test."""
    return build_container(test_config)


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
# Note: As domain models are implemented in Phase 4, these factories 
# will be updated to return actual strongly-typed dataclass instances.

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
```

---

# 4. Design Decisions

1. **`test_config` Override:** By overriding `data_dir` directly in the `test_config` fixture, we guarantee that no test will accidentally delete the developer's real `data/knowledge_base/` or `data/vector_store/`. When the test completes, `pytest` destroys the `tmp_path`.
2. **Factory Fixtures:** Returning a function from a fixture (`mock_problem_factory()`) allows the test to customize the dummy object:
   ```python
   def test_hard_problem_routing(mock_problem_factory):
       problem = mock_problem_factory(slug="n-queens", difficulty="Hard")
       assert problem["difficulty"] == "Hard"
   ```
3. **Strict Markers:** Using `--strict-markers` means we will catch spelling errors in our test decorators. Developers must categorize their tests as `unit`, `integration`, `e2e`, or `performance`. This allows CI pipelines to only run `@pytest.mark.unit` on pull requests to save time.
