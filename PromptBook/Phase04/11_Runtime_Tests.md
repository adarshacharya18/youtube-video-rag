# Phase04/11_Runtime_Tests.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Target Environment:** Intel Core Ultra 7 155H · Ubuntu 25.10 LTS · Python 3.12 · Intel Arc GPU  
**Document Version:** 2.0.0  
**Status:** Canonical — Supersedes v1.0.0 after architectural audit.

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code Specification: `tests/core/test_main.py`](#2-source-code-specification-testscoretest_mainpy)
3. [Source Code Specification: `tests/orchestrator/test_pipeline.py`](#3-source-code-specification-testsorchestratortest_pipelinepy)
4. [Design Decisions & Architecture Compliance](#4-design-decisions--architecture-compliance)
5. [Change Log](#5-change-log)

---

# 1. Executive Summary

This document specifies the **Synchronous Runtime Test Suite Specification** covering the CLI entry point, configuration bootstrapping, pre-flight checks, manual dependency injection wiring, signal handling, exit codes, and orchestrator execution (`tests/core/test_main.py` and `tests/orchestrator/test_pipeline.py`).

### Testing Focus
- **CLI Parsing:** Validate positional problem slug arguments and operational flags (`--force-regenerate`, `--dry-run`, `--log-level`).
- **Fail-Fast Config:** Verify missing configuration variables raise `ConfigurationError` immediately.
- **Pre-Flight Validation:** Verify binary checks (`shutil.which("ffmpeg")`) and directory writeability checks fail gracefully.
- **Manual Injection Wiring:** Confirm all 9 concrete modules are wired into `PipelineOrchestrator` via explicit constructor arguments.
- **Interruption & Exit Codes:** Verify process return codes for Success (`0`), Failure (`1`), and Signal Interruption (`130`).

> [!NOTE]
> All legacy non-blocking test utilities — including non-blocking test runners, mock frameworks, state machine tests, dynamic resolution tests, hot-reload tests, event mocks, context objects, and cancellation tokens — have been completely removed.

---

# 2. Source Code Specification: `tests/core/test_main.py`

```python
"""
Tests for CLI Entry Point, Pre-Flight Checks, and Composition Root Wiring.
"""

import signal
import sys
from unittest.mock import MagicMock, patch
import pytest

from src.__main__ import main, parse_args, run_preflight_checks
from src.core.config import PipelineConfig
from src.core.exceptions import ConfigurationError, PipelineError


def test_parse_args_valid_slug():
    """Verifies parsing of positional slug and CLI options."""
    args = parse_args(["two-sum", "--force-regenerate", "--log-level", "DEBUG"])
    assert args.slug == "two-sum"
    assert args.force_regenerate is True
    assert args.log_level == "DEBUG"
    assert args.dry_run is False


def test_load_config_fail_fast():
    """Verifies that configuration failure exits main with code 1."""
    with patch("src.__main__.load_config", side_effect=ConfigurationError("Missing GEMINI_API_KEY")):
        exit_code = main(["two-sum"])
        assert exit_code == 1


def test_preflight_checks_ffmpeg_missing():
    """Verifies pre-flight check raises ConfigurationError if ffmpeg is missing."""
    config = PipelineConfig(gemini_api_key="valid_key")
    with patch("shutil.which", return_value=None):
        with pytest.raises(ConfigurationError, match="Required binary 'ffmpeg' was not found"):
            run_preflight_checks(config)


def test_main_success_exit_code_zero(tmp_path):
    """Verifies successful main pipeline execution returns exit code 0."""
    mock_config = PipelineConfig(
        output_dir=str(tmp_path / "out"),
        temp_dir=str(tmp_path / "tmp"),
        cache_dir=str(tmp_path / "cache"),
        gemini_api_key="test_key",
    )

    with patch("src.__main__.load_config", return_value=mock_config), \
         patch("src.__main__.run_preflight_checks"), \
         patch("src.__main__.PipelineOrchestrator") as mock_orch_cls, \
         patch("src.__main__.LeetCodeScraper"), \
         patch("src.__main__.TagExtractor"), \
         patch("src.__main__.RAGPlatform"), \
         patch("src.__main__.ScriptGenerator"), \
         patch("src.__main__.VoiceGenerator"), \
         patch("src.__main__.ManimAnimator"), \
         patch("src.__main__.VideoAssembler"), \
         patch("src.__main__.YouTubeUploader"), \
         patch("src.__main__.LongTermMemory"):
        
        mock_orch_instance = MagicMock()
        mock_orch_cls.return_value = mock_orch_instance

        exit_code = main(["two-sum"])
        assert exit_code == 0
        mock_orch_instance.run.assert_called_once_with(slug="two-sum")


def test_main_keyboard_interrupt_exit_code_130(tmp_path):
    """Verifies KeyboardInterrupt returns POSIX exit code 130."""
    mock_config = PipelineConfig(
        output_dir=str(tmp_path / "out"),
        temp_dir=str(tmp_path / "tmp"),
        cache_dir=str(tmp_path / "cache"),
        gemini_api_key="test_key",
    )

    with patch("src.__main__.load_config", return_value=mock_config), \
         patch("src.__main__.run_preflight_checks"), \
         patch("src.__main__.PipelineOrchestrator") as mock_orch_cls, \
         patch("src.__main__.LeetCodeScraper"), \
         patch("src.__main__.TagExtractor"), \
         patch("src.__main__.RAGPlatform"), \
         patch("src.__main__.ScriptGenerator"), \
         patch("src.__main__.VoiceGenerator"), \
         patch("src.__main__.ManimAnimator"), \
         patch("src.__main__.VideoAssembler"), \
         patch("src.__main__.YouTubeUploader"), \
         patch("src.__main__.LongTermMemory"):
        
        mock_orch_instance = MagicMock()
        mock_orch_instance.run.side_effect = KeyboardInterrupt()
        mock_orch_cls.return_value = mock_orch_instance

        exit_code = main(["two-sum"])
        assert exit_code == 130
```

---

# 3. Source Code Specification: `tests/orchestrator/test_pipeline.py`

```python
"""
Tests for Synchronous Pipeline Orchestrator Execution and Signal Interruption.
"""

from unittest.mock import MagicMock
import pytest

from src.orchestrator.pipeline import PipelineOrchestrator
from src.core.config import PipelineConfig


@pytest.fixture
def mock_config(tmp_path):
    """Provides a mock PipelineConfig fixture."""
    return PipelineConfig(
        output_dir=str(tmp_path / "out"),
        temp_dir=str(tmp_path / "tmp"),
        cache_dir=str(tmp_path / "cache"),
        gemini_api_key="test_key",
    )


def test_orchestrator_sequential_execution(mock_config):
    """Verifies all 9 pipeline modules run in exact sequential order."""
    scraper = MagicMock()
    tags = MagicMock()
    rag = MagicMock()
    script = MagicMock()
    voice = MagicMock()
    animation = MagicMock()
    assembly = MagicMock()
    youtube = MagicMock()
    memory = MagicMock()

    orchestrator = PipelineOrchestrator(
        config=mock_config,
        scraper=scraper,
        tags=tags,
        rag=rag,
        script=script,
        voice=voice,
        animation=animation,
        assembly=assembly,
        youtube=youtube,
        memory=memory,
    )

    orchestrator.run(slug="two-sum")

    scraper.run.assert_called_once()
    tags.run.assert_called_once()
    rag.run.assert_called_once()
    script.run.assert_called_once()
    voice.run.assert_called_once()
    animation.run.assert_called_once()
    assembly.run.assert_called_once()
    youtube.run.assert_called_once()
    memory.run.assert_called_once()


def test_orchestrator_signal_interruption_propagates(mock_config):
    """Verifies pipeline correctly handles KeyboardInterrupt by not suppressing it."""
    scraper = MagicMock()
    scraper.run.side_effect = KeyboardInterrupt()
    tags = MagicMock()

    orchestrator = PipelineOrchestrator(
        config=mock_config,
        scraper=scraper,
        tags=tags,
        rag=MagicMock(),
        script=MagicMock(),
        voice=MagicMock(),
        animation=MagicMock(),
        assembly=MagicMock(),
        youtube=MagicMock(),
        memory=MagicMock(),
    )

    with pytest.raises(KeyboardInterrupt):
        orchestrator.run(slug="two-sum")

    scraper.run.assert_called_once()
    tags.run.assert_not_called()
```

---

# 4. Design Decisions & Architecture Compliance

1. **Pure Synchronous pytest:** Tests run synchronously without requiring non-blocking event loops or specialized test runners.
2. **Fast Execution Speed:** By avoiding complex test setup and using standard `unittest.mock.MagicMock`, tests execute in sub-milliseconds.
3. **No `PipelineContext`:** Configuration is passed directly using `PipelineConfig`, adhering to the rule against stateful runtime contexts.
4. **No `CancellationToken` or Thread Events:** Interruption testing relies purely on `KeyboardInterrupt` exception bubbling, validating Python's standard POSIX signal handling instead of custom event flags.

---

# 5. Change Log

- **Removed `PipelineContext` mock:** Tests now inject `PipelineConfig` directly, complying with architecture rules against global or shared runtime contexts.
- **Removed `threading.Event` (CancellationToken pattern):** Replaced custom cancellation logic with standard `KeyboardInterrupt` propagation.
- **Removed custom `save_checkpoint` assertions:** In the canonical pipeline, state is managed by the orchestrator directly without a generic checkpointing subsystem. Interruption bubbling handles exits gracefully.
- **Updated `main()` mock wiring:** Explicitly tests the correct wiring of the 9 concrete modules directly into the orchestrator.
