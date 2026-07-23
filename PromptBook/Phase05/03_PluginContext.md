# Phase05/03_PluginContext.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/plugins/context.py`](#2-source-code-srcpluginscontextpy)
3. [Source Code Update: `src/plugins/base.py`](#3-source-code-update-srcpluginsbasepy)
4. [Design Decisions](#4-design-decisions)

---

# 1. Executive Summary

This document specifies the **Plugin Context**. While the `RuntimeContext` (built in Phase 04) represents the global, immutable state of the Application Runtime, the `PluginContext` is a specialized, localized wrapper generated exclusively for a single Plugin.

When the Plugin Manager initializes the *Scraper Plugin*, it takes the global `RuntimeContext`, generates a unique `workspace_dir` just for the Scraper, creates a specialized sub-logger (`plugin.scraper`), and provides a read-only `ResolverProtocol` so the plugin can resolve utilities from the DI container without being able to overwrite system registrations.

---

# 2. Source Code: `src/plugins/context.py`

```python
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
        # E.g., if global is 'dsa_pipeline', this becomes 'dsa_pipeline.scraper'
        return self._runtime.logger.getChild(self.plugin_name)

```

---

# 3. Source Code Update: `src/plugins/base.py`

*(The base plugin classes have been refactored to require the `PluginContext` instead of the raw `RuntimeContext`.)*

```python
# Updated snippet for src/plugins/base.py

from src.plugins.context import PluginContext

@runtime_checkable
class PluginProtocol(Protocol):
    # ...
    async def initialize(self, context: PluginContext) -> None: ...
    # ...

class AbstractBasePlugin(abc.ABC):
    # ...
    async def initialize(self, context: PluginContext) -> None:
        self._context = context
        self._state = ModuleState.INITIALIZED
        self._logger.info(f"[{self.metadata.name}] Initialized v{self.metadata.version}")
```

---

# 4. Design Decisions

1. **Service Container Shielding:** In Phase 04, we intentionally hid the `Container` from the `RuntimeContext` because passing the root `Container` gives a plugin God-mode (the ability to overwrite system singletons). Here, we pass the `ResolverProtocol`. This is an interface (from `src/core/container.py`) that *only* exposes the `.resolve()` method. The Plugin can safely pull utilities from the DI container, but the Python type checker mathematically prevents it from calling `.register_singleton()`.
2. **Workspace Isolation:** Every plugin receives its own `workspace_dir` (e.g., `/tmp/dsa/plugins/ffmpeg/`). If the FFmpeg plugin crashes and leaves gigabytes of corrupted MP4 files, a cleanup routine can confidently purge the `workspace_dir` without accidentally deleting the cache files belonging to the `RAG` plugin.
3. **Transparent Forwarding:** By exposing `@property` accessors for `metrics`, `event_bus`, etc., the `PluginContext` maintains the exact same API surface area as the original `RuntimeContext`, ensuring developer ergonomics remain smooth.
