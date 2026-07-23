"""
Runtime Context.

Provides a secure, immutable proxy to the core system components.
Plugins and workflow tasks consume this context instead of accessing 
the raw ApplicationRuntime or DI Container directly.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from src.core.cache import FileCache
from src.core.config import PipelineConfig


# ==========================================
# Proxy Protocols
# These protocols define the explicitly allowed surface area.
# Even if the underlying object has a .shutdown() method, 
# the Python type checker enforces that plugins cannot call it.
# ==========================================

@runtime_checkable
class EventBusProxy(Protocol):
    """Provides read-only access to publish events, without management rights."""
    async def publish(self, event: Any) -> None: ...


@runtime_checkable
class PluginRegistryProxy(Protocol):
    """Provides read-only discovery of other active plugins."""
    def get_plugin_metadata(self, name: str) -> Any: ...


@runtime_checkable
class WorkflowManagerProxy(Protocol):
    """Allows plugins to safely trigger child workflows without mutating engine state."""
    async def trigger_workflow(self, name: str, payload: Any) -> str: ...


@runtime_checkable
class MetricsProxy(Protocol):
    """Provides safe, fire-and-forget telemetry recording."""
    def increment(self, metric_name: str, value: int = 1) -> None: ...
    def record_time(self, metric_name: str, duration: float) -> None: ...


@runtime_checkable
class MemoryProxy(Protocol):
    """Provides safe access to the semantic graph memory store."""
    async def store(self, key: str, value: Any) -> None: ...
    async def retrieve(self, key: str) -> Any: ...


# ==========================================
# Cancellation Token
# ==========================================

class CancellationToken:
    """
    A strictly read-only wrapper around an asyncio.Event.
    Plugins can check if they should abort, but they cannot accidentally 
    or maliciously cancel the global pipeline by triggering the event themselves.
    """
    def __init__(self, event: asyncio.Event) -> None:
        self._event = event

    @property
    def is_cancelled(self) -> bool:
        """Synchronous check if cancellation was requested."""
        return self._event.is_set()

    async def wait(self) -> None:
        """Asynchronous wait that blocks until cancellation is requested."""
        await self._event.wait()


# ==========================================
# The Master Runtime Context
# ==========================================

@dataclass(frozen=True)
class RuntimeContext:
    """
    The immutable context object passed to all plugins upon initialization.
    Fields cannot be reassigned (frozen=True).
    """
    # Core Infrastructure
    config: PipelineConfig
    logger: logging.Logger
    
    # Proxied Subsystems
    event_bus: EventBusProxy
    plugin_registry: PluginRegistryProxy
    workflow_manager: WorkflowManagerProxy
    
    # Utilities
    metrics: MetricsProxy
    cache: FileCache
    memory: MemoryProxy
    
    # Filesystem State
    working_directory: Path
    temp_directory: Path
    
    # Lifecycle
    cancellation_token: CancellationToken

    def child_context(self, sub_logger_name: str) -> "RuntimeContext":
        """
        Creates a clone of this context with a specialized sub-logger.
        Useful when a Plugin spawns sub-tasks and wants isolated log traces.
        """
        import copy
        # Shallow copy is safe because all members are either protocols or thread-safe
        new_ctx = copy.copy(self)
        
        # Replace logger using the factory from core.logger if structlog is used, 
        # or standard logging.
        child_logger = self.logger.getChild(sub_logger_name)
        object.__setattr__(new_ctx, 'logger', child_logger)
        
        return new_ctx
