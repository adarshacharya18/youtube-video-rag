# Phase05/02_BasePlugin.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/plugins/base.py`](#2-source-code-srcpluginsbasepy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document specifies the concrete implementation of the **Plugin SDK Base Contracts**. 

Because Python supports **Structural Subtyping** (Duck Typing) via `typing.Protocol`, third-party developers do *not* strictly have to subclass our base classes. If they write a class that structurally implements the methods in `PluginProtocol`, the Dependency Injection container will accept it. 

However, to speed up internal development of the `Scraper`, `RAG`, and `Video` plugins, we also provide a robust `AbstractBasePlugin` that implements boilerplate state transitions and logging perfectly out of the box.

---

# 2. Source Code: `src/plugins/base.py`

```python
"""
Plugin SDK - Base Definitions.

Defines the absolute contract that all plugins must fulfill to be integrated
into the Application Runtime. Provides both a strict Protocol and a convenience
Abstract Base Class.
"""

import abc
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from src.core.context import RuntimeContext
from src.core.module_lifecycle import ModuleState


@dataclass(frozen=True)
class PluginDependency:
    """Defines a strict dependency on another plugin for topological sorting."""
    plugin_name: str
    min_version: str
    required: bool = True


@dataclass(frozen=True)
class PluginMetadata:
    """Immutable metadata descriptor parsed during the DISCOVERY phase."""
    name: str
    version: str
    description: str
    author: str
    dependencies: list[PluginDependency] = field(default_factory=list)


@dataclass(frozen=True)
class PluginHealth:
    """Health check snapshot returned to the master HealthMonitor."""
    is_healthy: bool
    details: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class PluginProtocol(Protocol):
    """
    Structural Subtyping contract for all plugins.
    Enforced by the DI Container's _validate_implementation() check.
    """
    @property
    def metadata(self) -> PluginMetadata: ...
    
    @property
    def state(self) -> ModuleState: ...

    async def initialize(self, context: RuntimeContext) -> None: ...
    async def configure(self, config_overrides: dict[str, Any]) -> None: ...
    async def validate(self) -> bool: ...
    
    async def start(self) -> None: ...
    async def pause(self) -> None: ...
    async def resume(self) -> None: ...
    async def stop(self) -> None: ...
    async def shutdown(self) -> None: ...
    
    def health(self) -> PluginHealth: ...
    def events(self) -> list[str]: ...


class AbstractBasePlugin(abc.ABC):
    """
    Convenience base class providing default, thread-safe boilerplate 
    implementations for the PluginProtocol. Internal developers should 
    inherit from this to accelerate development.
    """
    
    def __init__(self) -> None:
        # Plugins start in DISCOVERED until the PluginLoader touches them
        self._state = ModuleState.DISCOVERED
        self._context: RuntimeContext | None = None
        self._logger = logging.getLogger(f"plugin.{self.metadata.name}")

    @property
    @abc.abstractmethod
    def metadata(self) -> PluginMetadata:
        """Must be implemented by the child to define its identity."""
        pass

    @property
    def state(self) -> ModuleState:
        return self._state

    async def initialize(self, context: RuntimeContext) -> None:
        """
        Secures the immutable RuntimeContext proxy.
        Should NOT be overridden unless calling super().initialize()
        """
        self._context = context
        self._state = ModuleState.INITIALIZED
        self._logger.info(f"[{self.metadata.name}] Initialized v{self.metadata.version}")

    async def configure(self, config_overrides: dict[str, Any]) -> None:
        """Override to parse specific plugin configs (e.g., API keys)."""
        pass

    async def validate(self) -> bool:
        """
        Override to verify database connections or file paths before starting.
        If this returns False, the PluginManager transitions the plugin to FAILED.
        """
        self._state = ModuleState.VALIDATED
        return True

    async def start(self) -> None:
        """Override to bind Event Bus subscriptions and background tasks."""
        self._state = ModuleState.RUNNING
        self._logger.info(f"[{self.metadata.name}] Started executing.")

    async def pause(self) -> None:
        """Override to suspend consuming queue events temporarily."""
        self._state = ModuleState.PAUSED
        self._logger.info(f"[{self.metadata.name}] Paused.")

    async def resume(self) -> None:
        """Override to resume consuming queue events."""
        self._state = ModuleState.RUNNING
        self._logger.info(f"[{self.metadata.name}] Resumed.")

    async def stop(self) -> None:
        """Override to stop processing gracefully, but keep connections warm."""
        self._state = ModuleState.STOPPED
        self._logger.info(f"[{self.metadata.name}] Stopped.")

    async def shutdown(self) -> None:
        """Override to cleanly close SQLite connections, HTTP client sessions, etc."""
        self._state = ModuleState.SHUTDOWN
        self._logger.info(f"[{self.metadata.name}] Shut down successfully.")

    def health(self) -> PluginHealth:
        """Override to provide custom metrics (e.g., DB ping latency)."""
        return PluginHealth(
            is_healthy=self._state not in (ModuleState.FAILED, ModuleState.ERROR),
            details={"state": self._state.name}
        )

    def events(self) -> list[str]:
        """
        Override to explicitly document the Event Topics this plugin interacts with.
        Used by the PluginManager to trace cross-plugin dependencies.
        """
        return []
```

---

# 3. Design Decisions

1. **Protocol + Abstract Base Combination:** We are utilizing modern Python architecture by offering both options. We expose `PluginProtocol` decorated with `@runtime_checkable`. This enforces strict boundaries for external developers who might not want to inherit our base classes. Meanwhile, we provide `AbstractBasePlugin` with solid boilerplate logic to prevent our internal team from writing the exact same `self._state = ModuleState.PAUSED` code 10 times across 10 modules.
2. **Context Masking:** The `initialize()` method explicitly expects `RuntimeContext`, not `ApplicationRuntime`. This physically enforces the architectural boundary we established in Phase 04, preventing plugins from gaining god-mode access to the orchestrator.
3. **Explicit Meta & Events:** The inclusion of the `events()` list and `PluginDependency` metadata guarantees that the PluginManager can build a perfect dependency DAG (Directed Acyclic Graph) before attempting to initialize anything. If the *RAG Plugin* is missing the *Scraper Plugin* it depends on, it fails during `DISCOVERED` rather than crashing during `RUNNING`.
