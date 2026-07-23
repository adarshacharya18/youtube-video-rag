# Phase04/02_Application_Runtime.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Target Environment:** Intel Core Ultra 7 155H · Ubuntu 25.10 LTS · Python 3.12 · Intel Arc GPU  
**Document Version:** 2.0.0  
**Status:** Canonical — Supersedes v1.0.0 after architectural audit.

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code Specification: `src/__main__.py`](#2-source-code-specification-src__main__py)
3. [Design Decisions & Architecture Compliance](#3-design-decisions--architecture-compliance)
4. [Change Log](#4-change-log)

---

# 1. Executive Summary

This document specifies the concrete implementation of the **CLI Entry Point and Composition Root** (`src/__main__.py`).

The application runtime operates as a **thin, synchronous orchestration shell**. It encapsulates zero business logic and serves as the single location where system dependencies are wired, environment configuration is loaded, logging is initialized, pre-flight checks are validated, and the pipeline orchestrator is executed.

### Core Responsibilities
1. **CLI Parsing:** Parse command-line flags and positional arguments (`slug`, `--force-regenerate`, `--dry-run`, `--log-level`) using `argparse`.
2. **Config Loading:** Call `load_config()` once to construct an immutable `PipelineConfig` instance. No hot-reloading is supported.
3. **Logger Initialization:** Initialize structured `structlog` logging using the canonical `get_logger` method.
4. **Pre-flight Validation:** Execute `run_preflight_checks()` to sequentially verify binary dependencies (`ffmpeg`), directory availability, and API secrets.
5. **Manual Constructor Injection:** Instantiates all 9 pipeline modules explicitly with their respective configuration sub-objects and structured logger.
6. **Pipeline Orchestration:** Pass wired modules and the configuration into `PipelineOrchestrator` and trigger execution via `run(slug)`.
7. **Standard Exit Codes:** Terminate with standard POSIX exit codes: `0` (Success), `1` (Fatal Error), or `130` (Interrupted via `KeyboardInterrupt`).

> [!NOTE]
> All legacy v1.0.0 abstractions — including `ApplicationRuntime` state machines, runtime state enums, `RuntimeContext`, subsystem protocols, non-blocking startup/shutdown loops, dynamic resolution mechanisms, event buses, plugin managers, service containers, and workflow engines — have been completely removed.

---

# 2. Source Code Specification: `src/__main__.py`

```python
"""
Application Entry Point and Composition Root.

CLI entry point that parses command-line arguments, loads configuration,
initializes structured logging, executes pre-flight checks, manually wires
all 9 pipeline modules into PipelineOrchestrator via constructor injection,
and executes the video generation pipeline.
"""

import argparse
import shutil
import sys
from typing import Optional

from src.core.config import PipelineConfig, load_config
from src.core.exceptions import ConfigurationError, PipelineError
from src.core.logger import configure_logging, get_logger
from src.core.paths import ensure_dir

from src.orchestrator.pipeline import PipelineOrchestrator

# Concrete module implementations
from src.scraper.leetcode import LeetCodeScraper
from src.tags.explorer import GeminiTagExplorer
from src.rag.engine import ChromaRAGEngine
from src.script.generator import GeminiScriptGenerator
from src.voice.synthesizer import KokoroVoiceSynthesizer
from src.animation.renderer import ManimAnimationRenderer
from src.assembly.assembler import FFmpegVideoAssembler
from src.youtube.uploader import YouTubeAPIUploader
from src.memory.store import JSONMemoryStore


def parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parses command-line arguments for the video pipeline CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m src",
        description="Automated DSA Educational YouTube Video Generation Pipeline",
    )
    parser.add_argument(
        "slug",
        type=str,
        help="LeetCode problem slug (e.g., 'two-sum', 'reverse-linked-list')",
    )
    parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="Force regeneration of all intermediate artifacts, ignoring cache",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute pipeline validation without rendering final video or uploading",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override logging level specified in configuration",
    )
    return parser.parse_args(args)


def run_preflight_checks(config: PipelineConfig) -> None:
    """Executes synchronous pre-flight environment validation."""
    if not shutil.which("ffmpeg"):
        raise ConfigurationError("Required binary 'ffmpeg' not found on system PATH.")
    
    for dir_path in [config.output_dir, config.temp_dir, config.cache_dir]:
        try:
            ensure_dir(dir_path)
        except Exception as e:
            raise ConfigurationError(f"Failed to access directory '{dir_path}': {e}") from e

    if not config.gemini_api_key:
        raise ConfigurationError("Missing required API key: 'GEMINI_API_KEY'.")


def main(argv: Optional[list[str]] = None) -> int:
    """Main composition root execution flow."""
    try:
        args = parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1

    try:
        cli_overrides = {}
        if args.log_level:
            cli_overrides["log_level"] = args.log_level
        config = load_config(cli_overrides=cli_overrides)
    except ConfigurationError as e:
        print(f"CRITICAL: Configuration loading failed: {e}", file=sys.stderr)
        return 1

    configure_logging(config)
    logger = get_logger("pipeline")
    logger.info("Starting pipeline runtime", slug=args.slug)

    try:
        run_preflight_checks(config)
    except ConfigurationError as e:
        logger.error("Preflight check failed", error=str(e))
        return 1

    try:
        # Manual DI: Instantiate all 9 concrete modules
        scraper = LeetCodeScraper(config.scraper, get_logger("scraper"))
        tags = GeminiTagExplorer(config.tags, get_logger("tags"))
        rag = ChromaRAGEngine(config.rag, get_logger("rag"))
        script = GeminiScriptGenerator(config.script, get_logger("script"))
        voice = KokoroVoiceSynthesizer(config.voice, get_logger("voice"))
        animation = ManimAnimationRenderer(config.animation, get_logger("animation"))
        assembly = FFmpegVideoAssembler(config.assembly, get_logger("assembly"))
        youtube = YouTubeAPIUploader(config.youtube, get_logger("youtube"))
        memory = JSONMemoryStore(config.memory, get_logger("memory"))

        # Wire modules into PipelineOrchestrator
        orchestrator = PipelineOrchestrator(
            config=config,
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

        # Execute pipeline explicitly without task queues or state managers
        orchestrator.run(
            slug=args.slug,
            force_regenerate=args.force_regenerate,
            dry_run=args.dry_run
        )
        
        logger.info("Pipeline completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        return 130
    except PipelineError as e:
        logger.critical("Fatal pipeline error", error=str(e), exc_info=True)
        return 1
    except Exception as e:
        logger.critical("Uncaught runtime exception", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

# 3. Design Decisions & Architecture Compliance

1. **Single Composition Root:** `src/__main__.py` is the only location in the codebase where concrete component classes are constructed. No dynamic locators or DI containers are permitted.
2. **Explicit Manual Dependency Injection:** Module instantiation uses straightforward constructor injection. No DI Container class, no `register()`, no `resolve()`.
3. **No `RuntimeContext`:** The orchestrator and modules receive `config` and `logger` directly. `PipelineContext` is completely eliminated.
4. **No Custom SIGINT `signal.signal()` Handlers / `shutdown_event` / `CancellationToken`:** Standard `KeyboardInterrupt` handling is sufficient for a single-batch script. Setting global thread events or passing cancellation tokens into components is forbidden.
5. **No `HealthMonitor` / `StateManager`:** Pre-flight checks are implemented as simple inline validation functions (`run_preflight_checks`) that execute before any heavy computation starts. State tracking is done solely within the orchestrator sequence, not in external state managers.

# 4. Change Log
- **Removed `PipelineContext`:** Completely removed domain context logic. Passed `config` and `logger` directly to orchestrator and modules.
- **Removed `shutdown_event` & signal handlers:** Replaced overengineered posix signal listeners with standard `KeyboardInterrupt` catch block.
- **Removed `Typer`:** Standardized on built-in `argparse`.
- **Simplified Dependency Injection:** Instantiation perfectly aligns with the canonical `def main()` composition root pattern without any DI framework.
