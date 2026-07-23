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
