# Phase05/08_PluginManager.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/plugins/manager.py`](#2-source-code-srcpluginsmanagerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Plugin Manager**, the master orchestration layer for Phase 05. The Plugin Manager acts as the absolute authority over the entire Plugin ecosystem. 

It satisfies the `SubsystemProtocol` expected by the Core Application Runtime, meaning it natively integrates into the master startup and teardown sequences. It seamlessly coordinates the **Discoverer** (to parse and DAG-sort YAML manifests), the **Loader** (to isolate and instantiate Python code), and the **Registry** (to catalog active instances for the Workflow Engine).

---

# 2. Source Code: `src/plugins/manager.py`

```python
"""
Plugin Manager.

The master orchestration layer for the Plugin Subsystem.
Implements SubsystemProtocol to integrate securely with the Application Runtime.
Coordinates Discovery, Loading, and the Registry.
"""

import asyncio
import logging
from pathlib import Path

from src.core.container import Container
from src.core.context import RuntimeContext
from src.core.exceptions import PipelineError
from src.plugins.discovery import PluginDiscoverer
from src.plugins.loader import PluginLoader
from src.plugins.registry import PluginRegistry


class PluginManager:
    """
    Coordinates the entire plugin lifecycle: Discovery -> Loading -> Registration.
    Hooks directly into the master Application Runtime via start() and stop().
    """

    def __init__(self, runtime_context: RuntimeContext, container: Container, plugin_dir: Path) -> None:
        self._runtime = runtime_context
        self._container = container
        self._plugin_dir = plugin_dir
        self._logger = logging.getLogger(__name__)
        
        # Sub-components
        self.registry = PluginRegistry()
        self.discoverer = PluginDiscoverer(self._plugin_dir)
        self.loader = PluginLoader(self._runtime, self._container)

    async def start(self) -> None:
        """
        Executes the entire plugin bootstrap sequence.
        Discovers, mathematically sorts, loads, and starts all plugins.
        """
        self._logger.info("Starting Plugin Manager sequence...")
        
        # 1. Discover and Sort (DAG)
        with self._runtime.metrics.measure_time("plugin_manager.discovery_time"):
            sorted_manifests = self.discoverer.discover()
            
        if not sorted_manifests:
            self._logger.warning("No plugins discovered. The pipeline will have no execution capabilities.")
            return

        self._logger.info(f"Discovered {len(sorted_manifests)} valid plugins. Commencing load sequence...")

        # 2. Load and Initialize sequentially based on DAG topological order
        for manifest in sorted_manifests:
            try:
                # The Discoverer dynamically attached the _source_path during scanning
                plugin_path: Path = getattr(manifest, "_source_path", self._plugin_dir / manifest.id)
                
                with self._runtime.metrics.measure_time(f"plugin.load_time.{manifest.id}"):
                    # Instantiate and inject isolated context
                    instance = await self.loader.load_and_initialize(manifest, plugin_path)
                    
                # 3. Register it into the active in-memory database
                self.registry.register(instance)
                
                # 4. Start the plugin (Triggers background tasks and event bus subscriptions)
                with self._runtime.metrics.measure_time(f"plugin.start_time.{manifest.id}"):
                    await instance.start()
                    
                self._runtime.metrics.increment("plugin.successful_loads")
                
            except Exception as e:
                self._logger.error(f"Failed to load or start plugin [{manifest.id}]: {e}", exc_info=True)
                self._runtime.metrics.increment("plugin.failed_loads")
                # If a core plugin fails, the DAG is compromised. We halt the boot sequence.
                raise PipelineError(f"Fatal error loading plugin {manifest.id}: {e}") from e

        self._logger.info("Plugin Manager successfully booted all dependencies.")

    async def stop(self) -> None:
        """
        Safely tears down all active plugins in exact reverse topological order.
        """
        self._logger.info("Initiating Plugin Manager teardown...")
        
        # Get all active plugins, but reverse the list so dependencies are torn down last
        active_plugins = list(reversed(self.registry.get_all_active()))
        
        for plugin in active_plugins:
            manifest = plugin.manifest
            try:
                # The loader's unload() method handles strict timeouts automatically
                await self.loader.unload(plugin)
                self.registry.deregister(manifest.id)
            except Exception as e:
                # During shutdown, we swallow errors to ensure we attempt to close 
                # every single plugin, rather than crashing halfway through.
                self._logger.error(f"Error during teardown of [{manifest.id}]: {e}", exc_info=True)

        self._logger.info("Plugin Manager teardown complete.")

    async def reload_plugin(self, plugin_id: str) -> None:
        """Hot-reloads a single specific plugin without bringing down the system."""
        self._logger.info(f"Triggering hot-reload for [{plugin_id}]...")
        
        try:
            # 1. Fetch current instance and its path
            old_instance = self.registry.get(plugin_id)
            plugin_path = getattr(old_instance.manifest, "_source_path")
            
            # 2. Deregister from Active Memory to prevent traffic
            self.registry.disable(plugin_id)
            
            # 3. Use the Loader to Hot-Swap the Python module in sys.modules
            new_instance = await self.loader.reload(old_instance, plugin_path)
            
            # 4. Swap and Re-enable
            self.registry.deregister(plugin_id)
            self.registry.register(new_instance)
            await new_instance.start()
            
            self._logger.info(f"Hot-reload successful for [{plugin_id}].")
            
        except Exception as e:
            self._logger.error(f"Failed to hot-reload plugin [{plugin_id}]: {e}", exc_info=True)
            raise PipelineError(f"Hot-reload failed: {e}") from e
```

---

# 3. Design Decisions

1. **Topological Booting:** The `start()` loop iterates over the `sorted_manifests`. Because the Discoverer previously ran a DAG sort via `graphlib`, we are mathematically guaranteed that if `plugin A` depends on `plugin B`, `plugin B` will be loaded, initialized, registered, and `.start()`ed *before* the manager even attempts to look at `plugin A`.
2. **Reverse Teardown:** During the `stop()` event, the manager fetches all active plugins and reverses the array `list(reversed(...))`. This prevents massive cascade failures where a Database plugin is shut down while the Scraper plugin is still actively trying to write to it. 
3. **Hot-Reload Architecture:** The `reload_plugin()` method combines the soft-disable feature of the Registry with the hard `importlib` swap of the Loader. This allows administrators to push a bug fix for the Scraper plugin and reload it via CLI without having to bring down the central Event Bus or Workflow Engine.
4. **Telemetry Deep Integration:** The Manager natively wraps the discovery, loading, and starting sequences in `metrics.measure_time()`. If a plugin introduces a 5-second `time.sleep()` in its `.start()` method, the `MetricsRegistry` will instantly catch it and flag the anomaly.
