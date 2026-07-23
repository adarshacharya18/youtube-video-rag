"""
Plugin Event Definitions.

Defines the strongly-typed payload schemas for all Plugin lifecycle events
broadcast to the central Event Bus.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    """Returns a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _uuid() -> str:
    """Generates a unique tracking ID for the event."""
    return str(uuid.uuid4())


@dataclass(frozen=True)
class PluginEventBase:
    """Base schema ensuring all events have standard tracking headers."""
    plugin_id: str
    event_id: str = field(default_factory=_uuid)
    timestamp: datetime = field(default_factory=_now)
    event_version: str = "1.0.0"


@dataclass(frozen=True)
class PluginDiscoveredEvent(PluginEventBase):
    plugin_version: str
    dependencies: list[str]


@dataclass(frozen=True)
class PluginLoadedEvent(PluginEventBase):
    pass


@dataclass(frozen=True)
class PluginInitializedEvent(PluginEventBase):
    pass


@dataclass(frozen=True)
class PluginStartedEvent(PluginEventBase):
    pass


@dataclass(frozen=True)
class PluginPausedEvent(PluginEventBase):
    pass


@dataclass(frozen=True)
class PluginResumedEvent(PluginEventBase):
    pass


@dataclass(frozen=True)
class PluginStoppedEvent(PluginEventBase):
    pass


@dataclass(frozen=True)
class PluginFailedEvent(PluginEventBase):
    error_message: str
    stack_trace: str = ""


@dataclass(frozen=True)
class PluginRecoveredEvent(PluginEventBase):
    pass


@dataclass(frozen=True)
class PluginUnloadedEvent(PluginEventBase):
    pass
