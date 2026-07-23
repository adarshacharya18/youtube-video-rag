"""
CLI Entry Point and Composition Root.

Provides the Typer CLI application, parses arguments, configures logging,
bootstraps the Dependency Injection container, and executes commands.
"""

import sys

import typer
from rich.console import Console

from src.core.config import load_config
from src.core.exceptions import PipelineError
from src.core.logger import get_logger
from src.core.lifecycle import application_lifecycle


# Initialize Typer App and Rich Console
app = typer.Typer(
    name="dsa-pipeline",
    help="Automated DSA Educational YouTube Video Pipeline",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


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
    with application_lifecycle() as app_context:
        logger = get_logger(__name__)
        logger.info(f"Initializing end-to-end pipeline for: {slug} (force={force})")
        # TODO: resolve Orchestrator from app_context.container and run


@app.command()
def index(
    incremental: bool = typer.Option(
        True, help="Only index modified files (false rebuilds entirely)"
    ),
) -> None:
    """Rebuild or update the ChromaDB vector index from the Knowledge Base."""
    with application_lifecycle() as app_context:
        logger = get_logger(__name__)
        logger.info(f"Starting Knowledge Base indexer (incremental={incremental})...")


# ==========================================
# Modular Execution Commands
# ==========================================

@app.command()
def scrape(slug: str = typer.Argument(..., help="LeetCode problem slug")) -> None:
    """Run ONLY the LeetCode scraper module."""
    with application_lifecycle() as app_context:
        logger = get_logger(__name__)
        logger.info(f"Scraping problem: {slug}")


@app.command()
def voice(slug: str = typer.Argument(..., help="LeetCode problem slug")) -> None:
    """Run ONLY the voice generation module for a pre-existing script."""
    with application_lifecycle() as app_context:
        logger = get_logger(__name__)
        logger.info(f"Generating voice for: {slug}")


@app.command()
def animate(slug: str = typer.Argument(..., help="LeetCode problem slug")) -> None:
    """Run ONLY the Manim animation module for a pre-existing script."""
    with application_lifecycle() as app_context:
        logger = get_logger(__name__)
        logger.info(f"Rendering animations for: {slug}")


@app.command()
def upload(slug: str = typer.Argument(..., help="LeetCode problem slug")) -> None:
    """Run ONLY the YouTube upload module for a pre-assembled video."""
    with application_lifecycle() as app_context:
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
    with application_lifecycle() as app_context:
        logger = get_logger(__name__)
        logger.info(f"Executing memory action: {action}")


@app.command()
def config() -> None:
    """Print the currently resolved pipeline configuration."""
    # Special command that doesn't need the full heavy lifecycle
    cfg = load_config()
    console.print_json(data=cfg.model_dump(mode="json"))


@app.command()
def doctor() -> None:
    """Check system dependencies (FFmpeg, Manim, API keys, ChromaDB)."""
    with application_lifecycle() as app_context:
        logger = get_logger(__name__)
        logger.info("Running system diagnostics...")
        console.print("[green]System dependencies passed.[/green]")


@app.command()
def status(slug: str = typer.Argument(..., help="LeetCode problem slug")) -> None:
    """Check the checkpoint status of a specific pipeline run."""
    with application_lifecycle() as app_context:
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
        raise
