"""
Plugin SDK - Base Definitions.

Defines the absolute contract that all plugins must fulfill to be integrated
into the Application Runtime. Provides both a strict Protocol and a convenience
Abstract Base Class.
"""

import abc
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from src.core.module_lifecycle import ModuleState
from src.plugins.context import PluginContext


from src.plugins.manifest import PluginManifest


@dataclass(frozen=True)
class PluginHealth:
    """Health check snapshot returned to the master HealthMonitor."""
    is_healthy: bool
    details: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class PluginProtocol(Protocol):
    """
    Structural Subtyping contract for all plugins.
    Enforced by the DI Container's _validate_implementation() check.
    """
    @property
    def manifest(self) -> PluginManifest: ...
    
    @property
    def state(self) -> ModuleState: ...

    async def initialize(self, context: PluginContext) -> None: ...
    async def configure(self, config_overrides: dict[str, Any]) -> None: ...
    async def validate(self) -> bool: ...
    
    async def start(self) -> None: ...
    async def pause(self) -> None: ...
    async def resume(self) -> None: ...
    async def stop(self) -> None: ...
    async def shutdown(self) -> None: ...
    
    def health(self) -> PluginHealth: ...
    def events(self) -> list[str]: ...


class AbstractBasePlugin(abc.ABC):
    """
    Convenience base class providing default, thread-safe boilerplate 
    implementations for the PluginProtocol. Internal developers should 
    inherit from this to accelerate development.
    """
    
    def __init__(self) -> None:
        # Plugins start in DISCOVERED until the PluginLoader touches them
        self._state = ModuleState.DISCOVERED
        self._context: PluginContext | None = None
        self._logger = logging.getLogger(f"plugin.{self.manifest.name}")

    @property
    @abc.abstractmethod
    def manifest(self) -> PluginManifest:
        """Must be implemented by the child to define its identity."""
        pass

    @property
    def state(self) -> ModuleState:
        return self._state

    async def initialize(self, context: PluginContext) -> None:
        """
        Secures the immutable PluginContext proxy.
        Should NOT be overridden unless calling super().initialize()
        """
        self._context = context
        self._state = ModuleState.INITIALIZED
        self._logger.info(f"[{self.manifest.name}] Initialized v{self.manifest.version}")

    async def configure(self, config_overrides: dict[str, Any]) -> None:
        """Override to parse specific plugin configs (e.g., API keys)."""
        pass

    async def validate(self) -> bool:
        """
        Override to verify database connections or file paths before starting.
        If this returns False, the PluginManager transitions the plugin to FAILED.
        """
        self._state = ModuleState.VALIDATED
        return True

    async def start(self) -> None:
        """Override to bind Event Bus subscriptions and background tasks."""
        self._state = ModuleState.RUNNING
        self._logger.info(f"[{self.manifest.name}] Started executing.")

    async def pause(self) -> None:
        """Override to suspend consuming queue events temporarily."""
        self._state = ModuleState.PAUSED
        self._logger.info(f"[{self.manifest.name}] Paused.")

    async def resume(self) -> None:
        """Override to resume consuming queue events."""
        self._state = ModuleState.RUNNING
        self._logger.info(f"[{self.manifest.name}] Resumed.")

    async def stop(self) -> None:
        """Override to stop processing gracefully, but keep connections warm."""
        self._state = ModuleState.STOPPED
        self._logger.info(f"[{self.manifest.name}] Stopped.")

    async def shutdown(self) -> None:
        """Override to cleanly close SQLite connections, HTTP client sessions, etc."""
        self._state = ModuleState.SHUTDOWN
        self._logger.info(f"[{self.manifest.name}] Shut down successfully.")

    def health(self) -> PluginHealth:
        """Override to provide custom metrics (e.g., DB ping latency)."""
        return PluginHealth(
            is_healthy=self._state not in (ModuleState.FAILED, ModuleState.ERROR),
            details={"state": self._state.name}
        )

    def events(self) -> list[str]:
        """
        Override to explicitly document the Event Topics this plugin interacts with.
        Used by the PluginManager to trace cross-plugin dependencies.
        """
        return []
