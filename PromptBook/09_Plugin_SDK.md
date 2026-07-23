# 09_Plugin_SDK.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Designed (Interfaces Only)

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Design Principles & Thread Safety](#2-design-principles--thread-safety)
3. [Data Models & State](#3-data-models--state)
4. [Core Interfaces (Protocols)](#4-core-interfaces-protocols)
5. [Orchestration Interfaces](#5-orchestration-interfaces)
6. [Usage Example](#6-usage-example)

---

# 1. Executive Summary

This document defines the **Plugin SDK** interfaces, enabling the YouTube Pipeline to be extended dynamically without modifying core infrastructure. Future capabilities like posting to Twitter, generating Notion pages, or syncing to GitHub can be authored as standalone plugins. 

By strictly relying on `typing.Protocol`, the SDK enforces structural subtyping. Developers building plugins do not need to subclass rigid base classes; they simply implement the required async methods.

---

# 2. Design Principles & Thread Safety

1. **Async-First Lifecycle:** All primary operations (`initialize`, `execute`, `shutdown`) are asynchronous to allow plugins to make non-blocking HTTP requests.
2. **Context Isolation:** Plugins are passed a `PluginContext` which acts as a proxy. They cannot access the raw global Dependency Injection `Container` directly, ensuring they only consume authorized services.
3. **Dependency Resolution:** The `PluginManager` uses a Topological Sort (DAG) via `PluginDependency` to initialize plugins in the correct order.
4. **Thread/Async Safety:** State transitions (`UNINITIALIZED` -> `ACTIVE`) must be protected via `asyncio.Lock` internally within the `PluginManager` to prevent race conditions during parallel event dispatching.

---

# 3. Data Models & State

Defines the fundamental data structures, statuses, and payloads.

```python
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

class PluginState(Enum):
    UNINITIALIZED = auto()
    INITIALIZING = auto()
    ACTIVE = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()


class PluginHealthStatus(Enum):
    HEALTHY = auto()
    DEGRADED = auto()
    UNHEALTHY = auto()


@dataclass(frozen=True)
class PluginHealth:
    status: PluginHealthStatus
    details: dict[str, str] = field(default_factory=dict)
    last_check_time: float = 0.0


@dataclass(frozen=True)
class PluginDependency:
    plugin_name: str
    min_version: str
    required: bool = True


@dataclass(frozen=True)
class PluginMetadata:
    name: str
    version: str
    author: str
    description: str
    dependencies: list[PluginDependency] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PluginConfig:
    enabled: bool = True
    config_dict: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginResult:
    success: bool
    data: Any = None
    error: str | None = None


@dataclass(frozen=True)
class PluginEvent:
    name: str
    payload: Any
    source_plugin: str


class PluginException(Exception):
    """Base exception for all plugin-related errors."""
    pass
```

---

# 4. Core Interfaces (Protocols)

The primary contracts implemented by Plugin Developers.

```python
from typing import Protocol, runtime_checkable
from collections.abc import Awaitable

@runtime_checkable
class PluginContext(Protocol):
    """Provides plugins with scoped, safe access to core system services."""
    @property
    def config(self) -> PluginConfig: ...
    
    def emit_event(self, event: PluginEvent) -> None: ...
    def get_service(self, service_name: str) -> Any: ...


@runtime_checkable
class BasePlugin(Protocol):
    """Core interface that all plugins must structurally implement."""
    @property
    def metadata(self) -> PluginMetadata: ...
    
    @property
    def state(self) -> PluginState: ...
    
    async def initialize(self, context: PluginContext) -> None: ...
    async def execute(self, payload: Any) -> PluginResult: ...
    async def shutdown(self) -> None: ...
    def check_health(self) -> PluginHealth: ...


@runtime_checkable
class PluginHook(Protocol):
    """Interface for attaching lifecycle middlewares or event observers."""
    async def on_event(self, event: PluginEvent) -> None: ...
    async def pre_execute(self, plugin: BasePlugin, payload: Any) -> Any: ...
    async def post_execute(self, plugin: BasePlugin, result: PluginResult) -> PluginResult: ...
```

---

# 5. Orchestration Interfaces

These interfaces define the internal infrastructure responsible for managing plugins.

```python
@runtime_checkable
class PluginRegistry(Protocol):
    """Maintains the index of all discovered and active plugins."""
    def register(self, plugin: BasePlugin) -> None: ...
    def unregister(self, plugin_name: str) -> None: ...
    def get_plugin(self, plugin_name: str) -> BasePlugin | None: ...
    def list_plugins(self) -> list[BasePlugin]: ...


@runtime_checkable
class PluginValidator(Protocol):
    """Validates plugin structure, semantic versions, and circular dependencies."""
    def validate_metadata(self, metadata: PluginMetadata) -> bool: ...
    def validate_dependencies(self, plugin: BasePlugin, registry: PluginRegistry) -> bool: ...


@runtime_checkable
class PluginFactory(Protocol):
    """Encapsulates the instantiation logic for translating raw classes into BasePlugins."""
    def create_plugin(self, plugin_class: type, config: PluginConfig) -> BasePlugin: ...


@runtime_checkable
class PluginLoader(Protocol):
    """Dynamically traverses directories, utilizing importlib to load Python modules."""
    def load_from_directory(self, directory: str) -> list[type]: ...
    def load_from_module(self, module_path: str) -> type: ...


@runtime_checkable
class PluginManager(Protocol):
    """
    The composition root for the SDK. Orchestrates validation, 
    instantiation, registry indexing, and lifecycle broadcasting.
    """
    @property
    def registry(self) -> PluginRegistry: ...
    
    async def bootstrap_plugins(self, directory: str) -> None: ...
    async def dispatch_event(self, event: PluginEvent) -> None: ...
    async def execute_plugin(self, plugin_name: str, payload: Any) -> PluginResult: ...
    async def shutdown_all(self) -> None: ...
```

---

# 6. Usage Example

How a developer would write a simple Twitter Plugin using the SDK:

```python
class TwitterAnnouncementPlugin:
    """A structural implementation of BasePlugin."""
    
    def __init__(self):
        self._state = PluginState.UNINITIALIZED
        self._context = None
        
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="TwitterAnnouncer",
            version="1.0.0",
            author="DataEngineer",
            description="Tweets when a new video is assembled."
        )
        
    @property
    def state(self) -> PluginState:
        return self._state

    async def initialize(self, context: PluginContext) -> None:
        self._context = context
        self._state = PluginState.ACTIVE
        
    async def execute(self, payload: Any) -> PluginResult:
        if self._state != PluginState.ACTIVE:
            return PluginResult(success=False, error="Plugin not active")
            
        video_url = payload.get("url")
        # .. logic to hit Twitter API ..
        
        self._context.emit_event(PluginEvent("TWEET_SENT", payload, "TwitterAnnouncer"))
        return PluginResult(success=True)

    async def shutdown(self) -> None:
        self._state = PluginState.STOPPED

    def check_health(self) -> PluginHealth:
        return PluginHealth(status=PluginHealthStatus.HEALTHY)
```
