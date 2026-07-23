# Phase 15 / 14: Evolution Tests

**Author:** Principal QA Automation Engineer  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `tests/evolution/test_evolution_suite.py`](#2-source-code-testsevolutiontest_evolution_suitepy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

Because the Phase 15 Evolution platform contains logic that literally mutates the pipeline's behavior over time (e.g., dynamically swapping models, changing prompts, running SQL `ALTER` statements), robust test coverage is absolutely mandatory. 

The **Evolution Test Suite** utilizes PyTest fixtures, dependency injection, and in-memory SQLite mocks to rigorously validate the Circuit Breaker model routing, the Prompt A/B testing Kill-Switch, Semantic Version validation, and Upgrade Saga Rollbacks.

---

# 2. Source Code: `tests/evolution/test_evolution_suite.py`

```python
"""
Evolution Subsystem Test Suite (Phase 15)

Unit and integration tests for the Platform Evolution components.
Tests Model Manager, Prompts, Plugins, Analytics, Compatibility, and Upgrades.
"""
import pytest
import os
import sqlite3
import json
from src.core.evolution.model_manager import ModelManager, ModelConfig
from src.core.evolution.feedback import FeedbackManager, FeedbackEntry
from src.core.evolution.prompt_manager import PromptManager, PromptTemplate
from src.core.evolution.compatibility_manager import CompatibilityManager
from src.core.evolution.analytics_dashboard import AnalyticsDashboard
from src.core.evolution.upgrade_manager import UpgradeManager, UpgradeTask

# --- Fixtures & Factories ---

@pytest.fixture
def mock_db_paths(tmp_path):
    """Provides isolated, temporary disk paths for database ledgers and artifacts."""
    prod_db = tmp_path / "prod.sqlite"
    feedback_db = tmp_path / "feedback.sqlite"
    storage_dir = tmp_path / "artifacts"
    os.makedirs(storage_dir, exist_ok=True)
    return str(prod_db), str(feedback_db), str(storage_dir)

@pytest.fixture
def feedback_manager(mock_db_paths):
    _, fb_path, _ = mock_db_paths
    return FeedbackManager(db_path=fb_path)

@pytest.fixture
def model_manager():
    mm = ModelManager()
    mm.register_model(ModelConfig("openai", "gpt-4", "llm", fallback_id="claude-3"))
    mm.register_model(ModelConfig("anthropic", "claude-3", "llm"))
    return mm

# --- Tests ---

def test_model_manager_fallback(model_manager):
    """Ensure ModelManager automatically routes to fallback on API failure."""
    def flaking_api(model_id):
        if model_id == "gpt-4":
            raise ConnectionError("503 Service Unavailable")
        return f"{model_id}_success"

    # Should catch the 503 and silently route to Claude
    result = model_manager.execute_with_fallback("llm", flaking_api)
    assert result == "claude-3_success"
    
    # Circuit breaker should have marked gpt-4 as permanently unhealthy
    assert model_manager._health_status["gpt-4"] is False

def test_prompt_ab_testing_and_regression(feedback_manager):
    """Ensure PromptManager routes traffic and triggers auto-kill-switch on regression."""
    pm = PromptManager(feedback_manager)
    pm.regression_threshold = 1.0
    
    pm.register_prompt(PromptTemplate("baseline_v1", "Base text", "1.0", is_baseline=True))
    # Configure experimental prompt with 100% routing weight for testing
    pm.register_prompt(PromptTemplate("exp_v2", "Exp text", "2.0", experiment_weight=1.0))

    # 1. Initial State: Should route to exp_v2 because weight is 1.0
    selected = pm.select_prompt("video_1")
    assert selected.prompt_id == "exp_v2"

    # 2. Simulate catastrophic feedback for exp_v2 into the Ledger
    # Baseline avg = 9.0
    feedback_manager.record_feedback(FeedbackEntry("v0", "judge", "baseline_v1", 9.0, {}, "2026"))
    # Exp avg = 7.0 (a catastrophic drop of 2.0 points, which is > threshold of 1.0)
    feedback_manager.record_feedback(FeedbackEntry("v1", "judge", "exp_v2", 7.0, {}, "2026"))

    # 3. Post-Regression State: Should auto-fallback to baseline despite weight=1.0
    selected_after_regression = pm.select_prompt("video_2")
    assert selected_after_regression.prompt_id == "baseline_v1"

def test_compatibility_manager_semver():
    """Ensure semantic versioning checks prevent illegal upgrades."""
    cm = CompatibilityManager(core_version="2.0.0")
    
    # Plugin requires exactly 2.0.0 or less
    assert cm.validate_plugin_compatibility("1.5.0", "old_plugin") is True
    # Plugin requires future core version
    assert cm.validate_plugin_compatibility("2.1.0", "future_plugin") is False

def test_analytics_dashboard_storage_calc(mock_db_paths):
    """Ensure Analytics calculates exact byte size of the artifacts folder."""
    prod, fb, storage = mock_db_paths
    
    # Create a 1KB mock file
    with open(os.path.join(storage, "mock_video.mp4"), "wb") as f:
        f.write(os.urandom(1024))
        
    dashboard = AnalyticsDashboard(prod_db_path=prod, feedback_db_path=fb, storage_dir=storage)
    report_json = dashboard.generate_dashboard_report()
    report = json.loads(report_json)
    
    assert report["storage_bytes"] == 1024

def test_upgrade_manager_rollback_saga(tmp_path):
    """Verify that a failing migration cleanly rolls back its steps."""
    state = {"flag": 0}
    def step1(): state["flag"] = 1
    def step2(): raise ValueError("Migration Failed")
    def rb1(): state["flag"] = 0
    
    task = UpgradeTask("TestUpgrade", "v1.1", "stable", [step1, step2], [rb1])
    um = UpgradeManager(backup_dir=str(tmp_path / "mock_backups"))
    
    # Override physical snapshot logic for pure unit testing
    um.create_state_snapshot = lambda x: None
    um.restore_state_snapshot = lambda x: None
    
    success = um.execute_upgrade(task)
    
    assert not success
    assert state["flag"] == 0 # Step 1 was successfully reversed!
```

---

# 3. Design Decisions

1. **Deterministic Dependency Injection:** By utilizing PyTest's `tmp_path` fixture (`mock_db_paths`), we dynamically inject safe, temporary OS paths into the `FeedbackManager` and `AnalyticsDashboard`. This ensures the test suite never accidentally truncates the actual production ledgers during a test run.
2. **Regression Kill-Switch Simulation:** The `test_prompt_ab_testing_and_regression` test mathematically proves that the auto-fallback safety logic works. It explicitly forces an experimental prompt to receive a terrible 7.0 score in the mock database, then asserts that the `select_prompt()` method instantly drops the experiment and reverts to the `baseline_v1` prompt.
3. **Rollback Saga Verification:** The `test_upgrade_manager_rollback_saga` test uses simple variable mutation closures (`step1`, `rb1`) to verify that if step 2 throws an exception, the Upgrade Manager correctly walks the tree backward and executes the rollback closures.
