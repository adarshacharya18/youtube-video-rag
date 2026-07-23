"""
Module Lifecycle Manager.

A robust state machine governing the execution state of modules and plugins.
Enforces allowed transitions, timeouts, and automated recovery logic.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from enum import Enum, auto
from typing import Any

from src.core.exceptions import PipelineError


class ModuleState(Enum):
    """The complete set of states a module can occupy during its lifetime."""
    DISCOVERED = auto()
    LOADED = auto()
    INITIALIZED = auto()
    VALIDATED = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    FAILED = auto()
    RECOVERED = auto()
    SHUTDOWN = auto()


class StateTransitionError(PipelineError):
    """Raised when an illegal state transition is attempted."""
    pass


class ModuleLifecycle:
    """
    State machine that manages the lifecycle of a discrete module/plugin.
    Guarantees thread-safe transitions and provides timeout protections.
    """

    # Defines strictly allowed state transitions to prevent corruption.
    _ALLOWED_TRANSITIONS: dict[ModuleState, set[ModuleState]] = {
        ModuleState.DISCOVERED: {ModuleState.LOADED, ModuleState.FAILED},
        ModuleState.LOADED: {ModuleState.INITIALIZED, ModuleState.FAILED},
        ModuleState.INITIALIZED: {ModuleState.VALIDATED, ModuleState.FAILED},
        ModuleState.VALIDATED: {ModuleState.RUNNING, ModuleState.FAILED, ModuleState.SHUTDOWN},
        ModuleState.RUNNING: {ModuleState.PAUSED, ModuleState.STOPPED, ModuleState.FAILED},
        ModuleState.PAUSED: {ModuleState.RUNNING, ModuleState.STOPPED, ModuleState.FAILED},
        ModuleState.STOPPED: {ModuleState.RUNNING, ModuleState.SHUTDOWN},
        ModuleState.FAILED: {ModuleState.RECOVERED, ModuleState.SHUTDOWN},
        ModuleState.RECOVERED: {ModuleState.VALIDATED, ModuleState.RUNNING, ModuleState.SHUTDOWN},
        ModuleState.SHUTDOWN: set(),  # Terminal state
    }

    def __init__(self, name: str) -> None:
        self.name = name
        self._state = ModuleState.DISCOVERED
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger(f"lifecycle.{name}")

    @property
    def state(self) -> ModuleState:
        return self._state

    async def transition(self, target: ModuleState) -> None:
        """Safely transition to a new state if allowed."""
        async with self._lock:
            allowed = self._ALLOWED_TRANSITIONS.get(self._state, set())
            if target not in allowed:
                raise StateTransitionError(
                    f"[{self.name}] Illegal transition: {self._state.name} -> {target.name}"
                )
            self._logger.debug(f"State changed: {self._state.name} -> {target.name}")
            self._state = target

    async def execute_with_timeout(
        self,
        action: Callable[[], Awaitable[Any]],
        target_success_state: ModuleState,
        timeout_sec: float = 30.0,
    ) -> Any:
        """
        Executes an asynchronous action. If it succeeds, transitions to target state.
        If it times out or throws an error, forcefully transitions to FAILED.
        """
        try:
            result = await asyncio.wait_for(action(), timeout=timeout_sec)
            await self.transition(target_success_state)
            return result
        except asyncio.TimeoutError as e:
            self._logger.error(f"Action timed out after {timeout_sec}s.")
            await self.transition(ModuleState.FAILED)
            raise PipelineError(f"[{self.name}] Timeout Error") from e
        except Exception as e:
            self._logger.error(f"Action failed: {e}", exc_info=True)
            await self.transition(ModuleState.FAILED)
            raise

    async def recover(self, recovery_hook: Callable[[], Awaitable[bool]]) -> bool:
        """
        Attempts to run a recovery hook if the module is in a FAILED state.
        If successful, transitions to RECOVERED.
        """
        if self._state != ModuleState.FAILED:
            self._logger.warning("Recovery attempted but module is not FAILED.")
            return False

        self._logger.info("Attempting automated recovery sequence...")
        try:
            # We don't apply standard timeouts to recovery hooks by default, 
            # assuming the hook manages its own boundaries.
            success = await recovery_hook()
            if success:
                await self.transition(ModuleState.RECOVERED)
                self._logger.info("Recovery successful.")
                return True
            else:
                self._logger.error("Recovery hook reported failure.")
                return False
        except Exception as e:
            self._logger.error(f"Recovery hook crashed: {e}")
            return False
