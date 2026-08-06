"""
Runtime Context module.
Defines RuntimeContext, CancellationToken, and service proxies for plugins.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


class CancellationToken:
    """Token to request operation cancellation."""

    def __init__(self) -> None:
        self._is_cancelled = False

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def cancel(self) -> None:
        self._is_cancelled = True


class EventBusProxy:
    def __init__(self, bus: Any = None) -> None:
        self.bus = bus


class MemoryProxy:
    def __init__(self, memory: Any = None) -> None:
        self.memory = memory


class MetricsProxy:
    def __init__(self, metrics: Any = None) -> None:
        self.metrics = metrics


class PluginRegistryProxy:
    def __init__(self, registry: Any = None) -> None:
        self.registry = registry


class WorkflowManagerProxy:
    def __init__(self, workflow: Any = None) -> None:
        self.workflow = workflow


@dataclass
class RuntimeContext:
    """Application runtime context passed to plugins."""
    cancellation_token: CancellationToken = field(default_factory=CancellationToken)
    event_bus: EventBusProxy = field(default_factory=EventBusProxy)
    memory: MemoryProxy = field(default_factory=MemoryProxy)
    metrics: MetricsProxy = field(default_factory=MetricsProxy)
    plugin_registry: PluginRegistryProxy = field(default_factory=PluginRegistryProxy)
    workflow_manager: WorkflowManagerProxy = field(default_factory=WorkflowManagerProxy)


__all__ = [
    "CancellationToken",
    "EventBusProxy",
    "MemoryProxy",
    "MetricsProxy",
    "PluginRegistryProxy",
    "WorkflowManagerProxy",
    "RuntimeContext",
]
