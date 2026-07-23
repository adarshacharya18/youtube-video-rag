"""
Application Runtime.

The central orchestration object that manages the initialization, execution,
and teardown of all core subsystems (Event Bus, Plugin Manager, Workflow Engine).
"""

import asyncio
import logging
import uuid
from enum import Enum, auto
from typing import Any, Protocol, runtime_checkable

from src.core.config import PipelineConfig, load_config
from src.core.container import Container
from src.core.exceptions import PipelineError
from src.core.lifecycle import build_container, run_health_checks
from src.core.logger import configure_logging, get_logger


class RuntimeState(Enum):
    UNINITIALIZED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()


@runtime_checkable
class SubsystemProtocol(Protocol):
    """Protocol for core subsystems that require async lifecycle management."""
    async def start(self) -> None: ...
    async def stop(self) -> None: ...


class ApplicationRuntime:
    """
    The master control shell. Coordinates the startup and teardown of all
    core architectural components securely. Contains zero business logic.
    """

    def __init__(self) -> None:
        self._state = RuntimeState.UNINITIALIZED
        self._run_id = str(uuid.uuid4())
        self._logger = logging.getLogger(__name__)
        
        # State
        self.config: PipelineConfig | None = None
        self.container: Container | None = None
        
        # Core Subsystems (To be implemented and resolved via DI)
        self.event_bus: SubsystemProtocol | None = None
        self.plugin_manager: SubsystemProtocol | None = None
        self.workflow_engine: SubsystemProtocol | None = None

    async def start(self) -> None:
        """Executes the strict startup sequence."""
        if self._state in (RuntimeState.STARTING, RuntimeState.RUNNING):
            self._logger.warning("Runtime is already starting or running.")
            return

        self._state = RuntimeState.STARTING
        try:
            # 1. Configuration & Logging
            self.config = load_config()
            configure_logging(self.config, pipeline_id=self._run_id)
            self._logger = get_logger(__name__)
            self._logger.info("Starting Application Runtime...", run_id=self._run_id)
            
            # 2. Pre-flight Health Checks
            run_health_checks(self.config)
            
            # 3. DI Container Build
            self.container = build_container(self.config)
            
            # 5. Start Subsystems in Topological Order
            if self.event_bus: 
                await self.event_bus.start()
            if self.plugin_manager: 
                await self.plugin_manager.start()
            if self.workflow_engine: 
                await self.workflow_engine.start()
            
            self._state = RuntimeState.RUNNING
            self._logger.info("Runtime successfully transitioned to RUNNING.")
            
        except Exception as e:
            self._state = RuntimeState.ERROR
            self._logger.critical("Failed to start Application Runtime.", exc_info=True)
            await self.stop()
            raise PipelineError(f"Runtime startup failed: {e}") from e

    async def stop(self) -> None:
        """Executes graceful shutdown with strict timeouts and state persistence."""
        if self._state == RuntimeState.STOPPED:
            return
            
        self._logger.info("Initiating Runtime shutdown sequence...")
        self._state = RuntimeState.STOPPING
        
        # 1. Stop Workflow Engine (Stop accepting new jobs, trigger cancellations)
        if self.workflow_engine:
            self._logger.info("Halting Workflow Engine...")
            try: 
                await asyncio.wait_for(self.workflow_engine.stop(), timeout=10.0)
            except asyncio.TimeoutError:
                self._logger.error("Workflow Engine shutdown timed out. Forcing cancellation.")
            except Exception as e: 
                self._logger.error(f"Error stopping Workflow Engine: {e}", exc_info=True)
            
        # 2. Shutdown Plugins (Close API sessions, release DB locks)
        if self.plugin_manager:
            self._logger.info("Shutting down Plugins...")
            try: 
                await asyncio.wait_for(self.plugin_manager.stop(), timeout=15.0)
            except asyncio.TimeoutError:
                self._logger.error("Plugin Manager shutdown timed out. Force killing plugins.")
            except Exception as e: 
                self._logger.error(f"Error stopping Plugin Manager: {e}", exc_info=True)
            
        # 3. Drain Event Bus (Wait for in-flight events to flush to DLQ)
        if self.event_bus:
            self._logger.info("Draining Event Bus queues...")
            try: 
                await asyncio.wait_for(self.event_bus.stop(), timeout=10.0)
            except asyncio.TimeoutError:
                self._logger.error("Event Bus drain timed out. Unprocessed events may be lost.")
            except Exception as e: 
                self._logger.error(f"Error stopping Event Bus: {e}", exc_info=True)
                
        # 4. Metrics Persistence & Cache Flushing
        if self.container and self.config:
            self._logger.info("Persisting final telemetry to disk...")
            try:
                from src.core.metrics import MetricsRegistry
                import json
                
                # Attempt to resolve and save metrics
                metrics = self.container.resolve(MetricsRegistry)
                snap = metrics.snapshot()
                
                dump_path = self.config.temp_dir / f"metrics_{self._run_id}.json"
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(dump_path, "w") as f:
                    f.write(json.dumps({
                        "counters": snap.counters,
                        "timers_avg": snap.timers_avg
                    }, indent=4))
                self._logger.info(f"Telemetry saved to {dump_path}")
            except Exception as e:
                # We catch all exceptions here because failure to save metrics 
                # should never prevent the process from ultimately exiting.
                self._logger.warning(f"Could not persist final state: {e}")
            
        self._state = RuntimeState.STOPPED
        self._logger.info("Runtime shutdown sequence complete. Safe to exit.")

    async def restart(self) -> None:
        """Performs a full teardown and clean startup."""
        self._logger.info("Restarting Runtime...")
        await self.stop()
        
        # Reset trace ID for the new session
        self._run_id = str(uuid.uuid4())
        await self.start()

    async def reload(self) -> None:
        """
        Hot-reloads configuration without bringing down the Event Bus or Plugin Manager.
        """
        if self._state != RuntimeState.RUNNING:
            self._logger.warning("Cannot reload config. Runtime is not RUNNING.")
            return
            
        self._logger.info("Hot-reloading configuration...")
        try:
            new_config = load_config()
            self.config = new_config
            
            if self.container:
                self.container.register_singleton(PipelineConfig, self.config)
                
            self._logger.info("Configuration reloaded successfully.")
        except Exception as e:
            self._logger.error(f"Failed to reload configuration: {e}", exc_info=True)

    def status(self) -> dict[str, str]:
        """Returns the real-time health and state of the runtime."""
        return {
            "state": self._state.name,
            "run_id": self._run_id,
            "event_bus": "running" if self.event_bus else "uninitialized",
            "plugin_manager": "running" if self.plugin_manager else "uninitialized",
            "workflow_engine": "running" if self.workflow_engine else "uninitialized",
        }
