# Phase05/10_PluginLifecycle.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/plugins/lifecycle.py`](#2-source-code-srcpluginslifecyclepy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document specifies the **Plugin Lifecycle Supervisor**. 

In Phase 04, we built a generic `ModuleLifecycle` state machine (Finite State Machine). This Phase 05 component acts as a specialized Supervisor that permanently wraps a `PluginProtocol` instance. It maps the plugin's interface methods (`.start()`, `.stop()`, `.validate()`) directly to the State Machine's strict transition boundaries and timeout wrappers.

This acts as a "Sidecar" for plugins. The Plugin Manager and Workflow Engine never call `plugin.start()` directly; they call `supervisor.start()`, guaranteeing that if the plugin hangs or attempts an illegal transition, the Supervisor intervenes mathematically.

---

# 2. Source Code: `src/plugins/lifecycle.py`

```python
"""
Plugin Lifecycle Supervisor.

A specialized wrapper for plugins that manages their exact state transitions,
validates state requirements, and enforces timeout boundaries.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from src.core.exceptions import PipelineError
from src.core.module_lifecycle import ModuleLifecycle, ModuleState
from src.plugins.base import PluginProtocol
from src.plugins.context import PluginContext


class PluginLifecycleError(PipelineError):
    """Raised when a plugin fails a lifecycle transition or times out."""
    pass


class PluginLifecycleSupervisor:
    """
    Supervises a single Plugin instance.
    Validates transitions via the underlying ModuleLifecycle FSM and enforces timeouts.
    """

    def __init__(self, plugin: PluginProtocol) -> None:
        self.plugin = plugin
        self.manifest = plugin.manifest
        
        # Instantiate the underlying strict Finite State Machine
        self._fsm = ModuleLifecycle(self.manifest.id)
        self._logger = logging.getLogger(f"supervisor.{self.manifest.id}")

    @property
    def current_state(self) -> ModuleState:
        """Returns the mathematically verified state of the plugin."""
        return self._fsm.state

    async def _safe_execute(
        self, 
        action: Callable[[], Awaitable[Any]], 
        target_state: ModuleState, 
        timeout_sec: float
    ) -> Any:
        """
        Wraps the plugin's raw method execution in an asyncio timeout block.
        If it succeeds, transitions the FSM to the target state.
        If it times out, the underlying FSM automatically transitions to FAILED.
        """
        try:
            return await self._fsm.execute_with_timeout(action, target_state, timeout_sec)
        except Exception as e:
            raise PluginLifecycleError(f"Plugin transition failed: {e}") from e

    async def initialize(self, context: PluginContext) -> None:
        """Moves from DISCOVERED -> LOADED -> INITIALIZED."""
        # 1. We are safely imported into memory
        await self._fsm.transition(ModuleState.LOADED)
        
        # 2. Inject context securely
        async def _run() -> None:
            await self.plugin.initialize(context)
            
        await self._safe_execute(_run, ModuleState.INITIALIZED, timeout_sec=15.0)

    async def configure(self, config_overrides: dict[str, Any]) -> None:
        """Dynamic configuration updates."""
        # Configuration doesn't strictly change the FSM state permanently,
        # but must execute within safety boundaries.
        async def _run() -> None:
            await self.plugin.configure(config_overrides)
            
        await self._fsm.execute_with_timeout(_run, self._fsm.state, timeout_sec=5.0)

    async def validate(self) -> bool:
        """Moves from INITIALIZED -> VALIDATED."""
        async def _run() -> bool:
            return await self.plugin.validate()
            
        result = await self._safe_execute(_run, ModuleState.VALIDATED, timeout_sec=10.0)
        if not result:
            # If the plugin explicitly reports validation failure, we fail the FSM.
            self._logger.error("Plugin failed self-validation.")
            await self._fsm.transition(ModuleState.FAILED)
        return result

    async def start(self) -> None:
        """Moves from VALIDATED or STOPPED -> RUNNING."""
        async def _run() -> None:
            await self.plugin.start()
            
        await self._safe_execute(_run, ModuleState.RUNNING, timeout_sec=15.0)

    async def pause(self) -> None:
        """Moves from RUNNING -> PAUSED."""
        async def _run() -> None:
            await self.plugin.pause()
            
        await self._safe_execute(_run, ModuleState.PAUSED, timeout_sec=5.0)

    async def resume(self) -> None:
        """Moves from PAUSED -> RUNNING."""
        async def _run() -> None:
            await self.plugin.resume()
            
        await self._safe_execute(_run, ModuleState.RUNNING, timeout_sec=5.0)

    async def stop(self) -> None:
        """Moves from RUNNING or PAUSED -> STOPPED."""
        async def _run() -> None:
            await self.plugin.stop()
            
        await self._safe_execute(_run, ModuleState.STOPPED, timeout_sec=10.0)

    async def shutdown(self) -> None:
        """Terminal state: -> SHUTDOWN."""
        async def _run() -> None:
            await self.plugin.shutdown()
            
        await self._safe_execute(_run, ModuleState.SHUTDOWN, timeout_sec=15.0)

    async def recover(self, recovery_hook: Callable[[], Awaitable[bool]]) -> bool:
        """
        If the plugin has entered FAILED, attempts automated recovery.
        If successful, transitions to RECOVERED.
        """
        # We wrap the hook in a strict timeout to fix the unbounded vulnerability 
        # identified in the Phase 04/12 Architectural Review.
        async def _bounded_recovery() -> bool:
            try:
                return await asyncio.wait_for(recovery_hook(), timeout=30.0)
            except asyncio.TimeoutError:
                self._logger.error("Recovery hook timed out.")
                return False
                
        return await self._fsm.recover(_bounded_recovery)
```

---

# 3. Design Decisions

1. **The Sidecar Pattern:** Instead of having the Plugin Loader and Plugin Manager scatter `ModuleLifecycle` FSM checks and timeouts everywhere, the `PluginLifecycleSupervisor` acts as a permanent Sidecar object. 
2. **Review Patch Implemented (Unbounded Recovery Hooks):** During the Phase 04/12 Architectural Review, we noted that `ModuleLifecycle.recover()` was unbounded. This implementation directly patches that vulnerability by wrapping the `recovery_hook` inside a strict 30-second `asyncio.wait_for` before passing it to the core FSM.
3. **Graceful Validation Rejection:** If `plugin.validate()` completes safely but returns `False` (e.g., the Scraper plugin successfully booted but realized its API key was invalid), the Supervisor intervenes and physically flips the FSM to `FAILED`. This mathematically prevents the Plugin Manager from ever calling `start()`, protecting the Pipeline.
