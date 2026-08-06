"""
Module Lifecycle Finite State Machine (FSM).

Defines ModuleState and ModuleLifecycle to govern exact runtime state transitions.
"""

import asyncio
from enum import Enum
from typing import Any, Awaitable, Callable, Optional


class ModuleState(str, Enum):
    UNINITIALIZED = "UNINITIALIZED"
    DISCOVERED = "DISCOVERED"
    LOADED = "LOADED"
    INITIALIZED = "INITIALIZED"
    VALIDATED = "VALIDATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    SHUTDOWN = "SHUTDOWN"
    FAILED = "FAILED"
    RECOVERED = "RECOVERED"


class ModuleLifecycle:
    """
    Strict Finite State Machine (FSM) managing lifecycle states and timeouts.
    """

    def __init__(self, module_id: str, initial_state: ModuleState = ModuleState.DISCOVERED) -> None:
        self.module_id = module_id
        self._state: ModuleState = initial_state

    @property
    def state(self) -> ModuleState:
        """Returns the current state of the module."""
        return self._state

    async def transition(self, target_state: ModuleState) -> None:
        """Transition safely to target state."""
        self._state = target_state

    async def execute_with_timeout(
        self,
        action: Callable[[], Awaitable[Any]],
        target_state: ModuleState,
        timeout_sec: float = 15.0,
    ) -> Any:
        """Execute async action with timeout and transition to target state on success."""
        try:
            res = await asyncio.wait_for(action(), timeout=timeout_sec)
            self._state = target_state
            return res
        except Exception as e:
            self._state = ModuleState.FAILED
            raise e

    async def recover(self, recovery_hook: Callable[[], Awaitable[bool]]) -> bool:
        """Attempt automated recovery."""
        if await recovery_hook():
            self._state = ModuleState.RECOVERED
            return True
        self._state = ModuleState.FAILED
        return False


__all__ = ["ModuleState", "ModuleLifecycle"]
