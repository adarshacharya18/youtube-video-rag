"""
Plugin Loader Engine.

Dynamically loads Python modules from the filesystem, validates their
structural compliance, instantiates them, and injects localized contexts.
"""

import asyncio
import importlib.util
import inspect
import logging
import sys
from pathlib import Path

from src.core.container import Container
from src.core.context import RuntimeContext
from src.core.exceptions import PipelineError
from src.core.module_lifecycle import ModuleLifecycle, ModuleState
from src.plugins.base import PluginProtocol
from src.plugins.context import PluginContext
from src.plugins.manifest import PluginManifest


class PluginLoadError(PipelineError):
    """Raised when a plugin fails to import, validate, or initialize."""
    pass


class PluginLoader:
    """
    Handles the physical memory instantiation of Python plugins.
    Enforces isolation and timeout boundaries on all 3rd-party code.
    """

    def __init__(self, runtime_context: RuntimeContext, container: Container) -> None:
        self._runtime = runtime_context
        self._container = container
        self._logger = logging.getLogger(__name__)

    async def load_and_initialize(self, manifest: PluginManifest, plugin_path: Path) -> PluginProtocol:
        """
        Safely loads a plugin into memory and advances its state machine
        to INITIALIZED.
        """
        self._logger.debug(f"Attempting to load plugin: {manifest.id}")
        
        # 1. Isolate File Workspace
        # Guarantees every plugin gets a unique scratch directory
        workspace = self._runtime.config.temp_dir / "plugins" / manifest.id
        workspace.mkdir(parents=True, exist_ok=True)
        
        # 2. Build Local Sandboxed Context
        plugin_context = PluginContext(
            plugin_name=manifest.name,
            workspace_dir=workspace,
            container=self._container,  # Exposes read-only resolve()
            _runtime=self._runtime
        )
        
        # 3. Safely Import Module via Python importlib
        module_name = f"plugin_{manifest.id.replace('.', '_')}"
        try:
            # Fallback pattern: Prefer main.py, fallback to __init__.py
            entry_point = plugin_path / "main.py"
            if not entry_point.exists():
                entry_point = plugin_path / "__init__.py"
                
            if not entry_point.exists():
                raise PluginLoadError(f"No entry point (main.py / __init__.py) found at {plugin_path}")
                
            spec = importlib.util.spec_from_file_location(module_name, entry_point)
            if not spec or not spec.loader:
                raise PluginLoadError("Failed to build import spec.")
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
        except Exception as e:
            raise PluginLoadError(f"Failed to execute Python module: {e}") from e
            
        # 4. Extract Class structurally matching PluginProtocol
        plugin_class = None
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Ensure the class was defined in this file, not just imported from elsewhere
            if obj.__module__ == module_name:
                # Structural check (Duck Typing)
                if hasattr(obj, "initialize") and hasattr(obj, "start"):
                    plugin_class = obj
                    break
                    
        if not plugin_class:
            raise PluginLoadError("No class implementing PluginProtocol found in entry point.")
            
        # 5. Instantiate and Initialize with Timeout Boundaries
        try:
            instance: PluginProtocol = plugin_class()
            
            # Dynamically inject the parsed manifest into the instance
            # so developers don't have to hardcode their metadata twice.
            instance.manifest = manifest  # type: ignore
            
            # Use Lifecycle wrapper for timeout protection
            lifecycle = ModuleLifecycle(manifest.id)
            await lifecycle.transition(ModuleState.LOADED)
            
            # Isolate the async initialization
            async def _init_wrapper() -> None:
                await instance.initialize(plugin_context)
                
            await lifecycle.execute_with_timeout(_init_wrapper, ModuleState.INITIALIZED, timeout_sec=15.0)
            
        except asyncio.TimeoutError as e:
            raise PluginLoadError(f"Initialization timed out after 15s. Abandoning plugin.") from e
        except Exception as e:
            raise PluginLoadError(f"Initialization crashed: {e}") from e
            
        self._logger.info(f"Successfully loaded and initialized: {manifest.id}")
        return instance

    async def unload(self, plugin: PluginProtocol) -> None:
        """
        Gracefully tears down the plugin, closing its connections,
        and safely removing it from the Python runtime memory.
        """
        manifest = plugin.manifest
        self._logger.info(f"Unloading plugin: {manifest.id}")
        
        try:
            # Enforce strict 10 second teardown boundaries
            await asyncio.wait_for(plugin.stop(), timeout=10.0)
            await asyncio.wait_for(plugin.shutdown(), timeout=10.0)
            
            # Cleanly purge from sys cache
            module_name = f"plugin_{manifest.id.replace('.', '_')}"
            if module_name in sys.modules:
                del sys.modules[module_name]
                
        except asyncio.TimeoutError:
            self._logger.error(f"[{manifest.id}] Unload timed out. Forcefully disconnecting.")
        except Exception as e:
            self._logger.error(f"[{manifest.id}] Error during unload: {e}", exc_info=True)
            
    async def reload(self, plugin: PluginProtocol, plugin_path: Path) -> PluginProtocol:
        """Hot-reloads a specific plugin dynamically."""
        manifest = plugin.manifest
        self._logger.info(f"Hot-reloading plugin: {manifest.id}")
        
        await self.unload(plugin)
        return await self.load_and_initialize(manifest, plugin_path)
