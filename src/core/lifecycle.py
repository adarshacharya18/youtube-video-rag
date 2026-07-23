"""
Application Lifecycle and Bootstrapping.

Handles startup, dependency injection container initialization,
signal handling, graceful shutdown, and pre-flight health checks.
"""

import shutil
import signal
import sys
import threading
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from src.core.base import Lifecycle
from src.core.cache import FileCache
from src.core.config import PipelineConfig, load_config
from src.core.container import Container, ResolverProtocol
from src.core.exceptions import ConfigurationError, PipelineError
from src.core.logger import configure_logging, get_logger


# Global event to signal long-running loops to terminate early
shutdown_event = threading.Event()


class Application:
    """Encapsulates the global state of the application during execution."""

    def __init__(self, container: Container, run_id: str) -> None:
        self.container = container
        self.run_id = run_id
        self._logger = get_logger(__name__)
        self._active_services: list[Lifecycle] = []

    def register_active_service(self, service: Any) -> None:
        """
        Register a service to be shut down during cleanup.
        Only keeps a reference if the service implements the Lifecycle protocol.
        """
        if isinstance(service, Lifecycle):
            self._logger.debug(f"Tracking lifecycle for {service.__class__.__name__}")
            self._active_services.append(service)

    def shutdown(self) -> None:
        """Gracefully shut down all active services in reverse order of initialization."""
        if not self._active_services:
            return

        self._logger.info("Initiating graceful shutdown sequence...")
        for service in reversed(self._active_services):
            try:
                self._logger.debug(f"Shutting down {service.__class__.__name__}...")
                service.shutdown()
            except Exception as e:
                self._logger.error(
                    f"Error shutting down {service.__class__.__name__}: {e}", 
                    exc_info=True
                )
        self._active_services.clear()
        self._logger.info("Shutdown sequence complete.")


def run_health_checks(config: PipelineConfig) -> None:
    """Run systemic pre-flight health checks."""
    logger = get_logger(__name__)
    
    # 1. Filesystem Permissions & Directories
    try:
        config.data_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise ConfigurationError(f"Cannot write to data directory: {config.data_dir}")

    # 2. External Dependencies (FFmpeg)
    if not shutil.which("ffmpeg"):
        logger.warning(
            "FFmpeg not found in system PATH. Video assembly module will fail if invoked."
        )

    # 3. Environment Secrets Validation
    if not config.gemini.api_key.get_secret_value():
        logger.warning(
            "GEMINI_API_KEY is missing. RAG and Script Generation will fail if invoked."
        )


def build_container(config: PipelineConfig) -> Container:
    """Assemble the dependency injection container and register infrastructure."""
    container = Container()
    
    # Register Core Singletons
    container.register_singleton(PipelineConfig, config)
    
    # Register Core Factories
    def build_cache(resolver: ResolverProtocol) -> FileCache:
        cfg = resolver.resolve(PipelineConfig)
        return FileCache(cfg.data_dir / "cache")
        
    container.register_factory(FileCache, build_cache)
    
    # Module factories (Scraper, RAG, etc.) will be registered here in Phase 04.
    
    return container


@contextmanager
def application_lifecycle() -> Generator[Application, None, None]:
    """
    Context manager that controls the entire application execution window.
    Initializes config, logging, container, and handles OS termination signals.
    """
    # 1. Bootstrapping
    run_id = str(uuid.uuid4())
    config = load_config()
    configure_logging(config, pipeline_id=run_id)
    logger = get_logger(__name__)
    
    logger.info("Bootstrapping DSA Educational Pipeline...", pipeline_id=run_id)
    
    # 2. Health Checks
    run_health_checks(config)
    
    # 3. DI Container Assembly
    container = build_container(config)
    app = Application(container, run_id)
    
    # 4. OS Signal Handling (Ctrl+C, Docker stop)
    shutdown_event.clear()

    def handle_signal(signum: int, frame: Any) -> None:
        logger.warning(f"Received termination signal {signum}. Halting pipeline...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        # Yield execution control to the Typer CLI command
        yield app
    except Exception as e:
        # Log unexpected errors before tearing down
        if not isinstance(e, PipelineError):
            logger.critical("Unhandled fatal exception detected.", exc_info=True)
        raise
    finally:
        # 5. Guaranteed Cleanup (Runs even if exceptions are thrown above)
        app.shutdown()
