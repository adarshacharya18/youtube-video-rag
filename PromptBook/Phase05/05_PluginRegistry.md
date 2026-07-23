# Phase05/05_PluginRegistry.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/plugins/registry.py`](#2-source-code-srcpluginsregistrypy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document specifies the **Plugin Registry**. While the *Plugin Loader* is responsible for reading files from the disk and instantiating Python objects, the *Plugin Registry* is the thread-safe, in-memory database that catalogs these active instances.

The Registry acts as the bridge for the Workflow Engine. When a pipeline YAML file requests a "text-to-speech" node, the Workflow Engine queries the Registry using `search_by_capability("text-to-speech")`. The Registry dynamically resolves this request to the active `ElevenLabsPlugin` or `BarkPlugin`, preventing the Workflow Engine from being hardcoded to specific vendor implementations.

---

# 2. Source Code: `src/plugins/registry.py`

```python
"""
Plugin Registry.

A thread-safe, in-memory database of all loaded plugins, their metadata,
capabilities, and active states.
"""

import threading
from typing import Optional

from src.core.exceptions import PipelineError
from src.plugins.base import PluginProtocol
from src.plugins.manifest import PluginManifest


class PluginNotFoundError(PipelineError):
    """Raised when a requested plugin ID or alias cannot be found or is disabled."""
    pass


class PluginRegistry:
    """
    Thread-safe repository for active plugins.
    Allows dynamic lookup by ID, Alias, or Capability.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        
        # Core storage: plugin_id -> PluginProtocol instance
        self._plugins: dict[str, PluginProtocol] = {}
        
        # State tracking: plugin_id -> is_enabled
        self._enabled_states: dict[str, bool] = {}
        
        # Alias resolution: alias_name -> plugin_id
        self._aliases: dict[str, str] = {}

    def register(self, plugin: PluginProtocol, alias: Optional[str] = None) -> None:
        """
        Catalogs a loaded plugin into the database.
        Optionally assigns an alias (e.g., 'tts' -> 'core.voice.elevenlabs').
        """
        with self._lock:
            pid = plugin.manifest.id
            if pid in self._plugins:
                raise ValueError(f"Plugin with ID '{pid}' is already registered.")
            
            self._plugins[pid] = plugin
            self._enabled_states[pid] = True
            
            if alias:
                if alias in self._aliases:
                    raise ValueError(f"Alias '{alias}' is already mapped to {self._aliases[alias]}")
                self._aliases[alias] = pid

    def deregister(self, plugin_id: str) -> None:
        """Removes a plugin and its associated aliases entirely."""
        with self._lock:
            if plugin_id in self._plugins:
                del self._plugins[plugin_id]
                del self._enabled_states[plugin_id]
                
                # Prune aliases mapping to this plugin
                stale_aliases = [k for k, v in self._aliases.items() if v == plugin_id]
                for k in stale_aliases:
                    del self._aliases[k]

    def _resolve_id(self, identifier: str) -> str:
        """Helper to map an alias to a plugin_id if applicable."""
        return self._aliases.get(identifier, identifier)

    def get(self, identifier: str) -> PluginProtocol:
        """
        Retrieves an active plugin by its exact ID or its Alias.
        Raises PluginNotFoundError if missing or explicitly disabled.
        """
        with self._lock:
            pid = self._resolve_id(identifier)
            
            if pid not in self._plugins:
                raise PluginNotFoundError(f"Plugin '{identifier}' not found in Registry.")
            
            if not self._enabled_states.get(pid, False):
                raise PluginNotFoundError(f"Plugin '{identifier}' is currently disabled.")
                
            return self._plugins[pid]

    def get_manifest(self, identifier: str) -> PluginManifest:
        """Returns just the descriptive metadata of a plugin."""
        return self.get(identifier).manifest

    def enable(self, identifier: str) -> None:
        """Marks a plugin as active."""
        with self._lock:
            pid = self._resolve_id(identifier)
            if pid not in self._plugins:
                raise PluginNotFoundError(f"Cannot enable unknown plugin: {identifier}")
            self._enabled_states[pid] = True

    def disable(self, identifier: str) -> None:
        """
        Marks a plugin as inactive. 
        Calls to get() will raise PluginNotFoundError until enabled again.
        """
        with self._lock:
            pid = self._resolve_id(identifier)
            if pid not in self._plugins:
                raise PluginNotFoundError(f"Cannot disable unknown plugin: {identifier}")
            self._enabled_states[pid] = False

    def search_by_capability(self, capability: str) -> list[PluginProtocol]:
        """
        Finds all active plugins that declare a specific capability.
        (e.g., capability="video_render" might return the Manim and FFmpeg plugins)
        """
        with self._lock:
            results = []
            for pid, plugin in self._plugins.items():
                if not self._enabled_states.get(pid, False):
                    continue
                    
                if capability in plugin.manifest.capabilities:
                    results.append(plugin)
            return results

    def get_all_active(self) -> list[PluginProtocol]:
        """Returns all currently enabled plugins in the system."""
        with self._lock:
            return [
                plugin for pid, plugin in self._plugins.items() 
                if self._enabled_states.get(pid, False)
            ]
```

---

# 3. Design Decisions

1. **Thread-Safe Data Structures:** Because the Workflow Engine executes asynchronously, multiple workflow tasks might attempt to query `search_by_capability` at the exact millisecond the Application Runtime is attempting to `.disable()` a failing plugin. The `threading.RLock()` ensures atomic dictionary resolution, preventing race conditions.
2. **Alias Support (`_aliases`):** An alias system was included to completely decouple Workflows from Plugin IDs. A workflow YAML can specify `requires: ['database']`. The Registry transparently maps the alias `database` to `core.storage.postgres` depending on what was registered at startup.
3. **Soft Disabling:** The `disable()` and `enable()` methods represent a "Soft Disable". The Plugin object remains in memory, but any subsystem attempting to `get()` it will receive a `PluginNotFoundError`. This allows administrators to temporarily turn off a misbehaving plugin without triggering a full JVM/Python garbage collection reload cycle.
