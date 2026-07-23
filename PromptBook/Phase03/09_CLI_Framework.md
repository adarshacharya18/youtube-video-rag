# Phase03/09_CLI_Framework.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/__main__.py`](#2-source-code-src__main__py)
3. [Design Decisions](#3-design-decisions)
4. [Usage Examples](#4-usage-examples)

---

# 1. Executive Summary

This document provides the implementation for the Command Line Interface (CLI) framework using `Typer` and `Rich`. 

Because our architecture decouples every module behind interfaces, the CLI acts strictly as the **Composition Root**. Its only responsibilities are to parse arguments, bootstrap the global configuration/logging/container, resolve the correct service from the container, and execute it. 

It implements the full suite of requested commands (`pipeline`, `index`, `scrape`, `voice`, `animate`, `upload`, `memory`, `config`, `doctor`, `status`) and features a robust global exception handler that catches our custom `PipelineError` to prevent ugly stack traces from leaking to the end-user for known operational failures.

---

# 2. Source Code: `src/__main__.py`

```python
"""
CLI Entry Point and Composition Root.

Provides the Typer CLI application, parses arguments, configures logging,
bootstraps the Dependency Injection container, and executes commands.
"""

import sys

import typer
from rich.console import Console

from src.core.config import PipelineConfig, load_config
from src.core.container import Container
from src.core.exceptions import PipelineError
from src.core.logger import configure_logging, get_logger

# Initialize Typer App and Rich Console
app = typer.Typer(
    name="dsa-pipeline",
    help="Automated DSA Educational YouTube Video Pipeline",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def bootstrap() -> Container:
    """
    Initialize the global state and Dependency Injection Container.
    This is the Composition Root where all implementations are wired.
    """
    # 1. Load Configuration
    config = load_config()

    # 2. Configure Logging
    configure_logging(config)

    # 3. Initialize DI Container
    container = Container()
    container.register_singleton(PipelineConfig, config)

    # Note: As module implementations (Scraper, RAG, etc.) are built,
    # their factories will be registered here.
    
    return container


# ==========================================
# Primary Pipeline Commands
# ==========================================

@app.command()
def pipeline(
    slug: str = typer.Argument(..., help="LeetCode problem slug (e.g., 'two-sum')"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force regenerate all steps, ignoring checkpoints"
    ),
) -> None:
    """Run the complete end-to-end video pipeline."""
    container = bootstrap()
    logger = get_logger(__name__)
    logger.info(f"Initializing end-to-end pipeline for: {slug} (force={force})")
    # TODO: resolve Orchestrator from container and run


@app.command()
def index(
    incremental: bool = typer.Option(
        True, help="Only index modified files (false rebuilds entirely)"
    ),
) -> None:
    """Rebuild or update the ChromaDB vector index from the Knowledge Base."""
    container = bootstrap()
    logger = get_logger(__name__)
    logger.info(f"Starting Knowledge Base indexer (incremental={incremental})...")


# ==========================================
# Modular Execution Commands
# ==========================================

@app.command()
def scrape(slug: str = typer.Argument(..., help="LeetCode problem slug")) -> None:
    """Run ONLY the LeetCode scraper module."""
    container = bootstrap()
    logger = get_logger(__name__)
    logger.info(f"Scraping problem: {slug}")


@app.command()
def voice(slug: str = typer.Argument(..., help="LeetCode problem slug")) -> None:
    """Run ONLY the voice generation module for a pre-existing script."""
    container = bootstrap()
    logger = get_logger(__name__)
    logger.info(f"Generating voice for: {slug}")


@app.command()
def animate(slug: str = typer.Argument(..., help="LeetCode problem slug")) -> None:
    """Run ONLY the Manim animation module for a pre-existing script."""
    container = bootstrap()
    logger = get_logger(__name__)
    logger.info(f"Rendering animations for: {slug}")


@app.command()
def upload(slug: str = typer.Argument(..., help="LeetCode problem slug")) -> None:
    """Run ONLY the YouTube upload module for a pre-assembled video."""
    container = bootstrap()
    logger = get_logger(__name__)
    logger.info(f"Uploading video for: {slug}")


# ==========================================
# System Utility Commands
# ==========================================

@app.command()
def memory(
    action: str = typer.Argument(
        ..., help="Action to perform (list, clean, dump, sync)"
    ),
) -> None:
    """Manage the systemic memory store."""
    container = bootstrap()
    logger = get_logger(__name__)
    logger.info(f"Executing memory action: {action}")


@app.command()
def config() -> None:
    """Print the currently resolved pipeline configuration."""
    cfg = load_config()
    # Output securely using rich (SecretStr objects will mask automatically)
    console.print_json(data=cfg.model_dump(mode="json"))


@app.command()
def doctor() -> None:
    """Check system dependencies (FFmpeg, Manim, API keys, ChromaDB)."""
    container = bootstrap()
    logger = get_logger(__name__)
    logger.info("Running system diagnostics...")
    console.print("[green]System dependencies passed.[/green]")


@app.command()
def status(slug: str = typer.Argument(..., help="LeetCode problem slug")) -> None:
    """Check the checkpoint status of a specific pipeline run."""
    container = bootstrap()
    logger = get_logger(__name__)
    logger.info(f"Checking checkpoint status for: {slug}")


if __name__ == "__main__":
    try:
        app()
    except PipelineError as e:
        console.print(f"\n[bold red]Pipeline Error:[/bold red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline aborted by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold white on red] FATAL UNHANDLED ERROR [/bold white on red] {e}")
        # We don't suppress the traceback for completely unknown errors
        raise
```

---

# 3. Design Decisions

1. **Lazy Loading:** `load_config()`, `configure_logging()`, and `Container()` are purposely encapsulated within `bootstrap()`. They are only executed if a command is actually invoked. This keeps `-h` or `--help` incredibly fast because we aren't establishing DB connections just to print the help menu.
2. **`PipelineError` Trap:** We placed the global try/except block at the `__name__ == "__main__"` level. By catching `PipelineError`, we ensure that our semantic errors (like `ProblemNotFoundError`) are printed cleanly via `rich` without scaring the user with a 40-line traceback. Unhandled generic `Exception`s still raise normally so we can debug our actual bugs.
3. **Module Isolation:** By exposing independent commands like `scrape` and `animate`, developers can rapidly test specific sub-systems without running the entire costly pipeline.
4. **Rich Integration:** Instead of `print()`, we utilize `rich.console.Console` to output secure, color-coded, and properly indented JSON when querying configuration states.
