"""
Plugin Context.

A specialized wrapper around the RuntimeContext tailored specifically
for an individual plugin. It provides plugin-specific loggers, workspaces,
and strictly scoped service resolution.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.cache import FileCache
from src.core.config import PipelineConfig
from src.core.container import ResolverProtocol
from src.core.context import (
    CancellationToken,
    EventBusProxy,
    MemoryProxy,
    MetricsProxy,
    PluginRegistryProxy,
    RuntimeContext,
    WorkflowManagerProxy,
)


@dataclass(frozen=True)
class PluginContext:
    """
    The immutable context injected into a specific plugin.
    It encapsulates the global RuntimeContext while providing localized
    directories and strict read-only access to the DI Container.
    """
    
    # Plugin-specific localization
    plugin_name: str
    workspace_dir: Path
    
    # Read-only DI Container (Resolves dependencies, cannot register overrides)
    container: ResolverProtocol
    
    # The Global Context
    _runtime: RuntimeContext

    # ==========================================
    # Global System Proxies (Forwarded)
    # ==========================================
    
    @property
    def config(self) -> PipelineConfig:
        return self._runtime.config

    @property
    def event_bus(self) -> EventBusProxy:
        return self._runtime.event_bus

    @property
    def plugin_registry(self) -> PluginRegistryProxy:
        return self._runtime.plugin_registry

    @property
    def workflow_manager(self) -> WorkflowManagerProxy:
        return self._runtime.workflow_manager

    @property
    def metrics(self) -> MetricsProxy:
        return self._runtime.metrics

    @property
    def cache(self) -> FileCache:
        return self._runtime.cache

    @property
    def memory(self) -> MemoryProxy:
        return self._runtime.memory

    @property
    def cancellation_token(self) -> CancellationToken:
        return self._runtime.cancellation_token

    # ==========================================
    # Localized Proxies (Specialized per plugin)
    # ==========================================
    
    @property
    def logger(self) -> logging.Logger:
        """Returns a specialized sub-logger tagged with the plugin's name."""
        return self._runtime.logger.getChild(self.plugin_name)
