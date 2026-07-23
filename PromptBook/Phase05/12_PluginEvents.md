# Phase05/12_PluginEvents.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Designed & Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Event Schemas: `src/plugins/events.py`](#2-event-schemas-srcpluginseventspy)
3. [Architecture Guidance](#3-architecture-guidance)
    * [Publishers](#publishers)
    * [Subscribers](#subscribers)
    * [Payload Ordering & Versioning](#payload-ordering--versioning)

---

# 1. Executive Summary

This document outlines the **Plugin Event Integration Architecture**. While the core engine uses direct asynchronous Python method calls (`await plugin.start()`) to execute commands, it broadcasts the *results* of those state changes globally across the Event Bus via standard Publish/Subscribe (Pub/Sub) mechanics.

By decoupling the execution from the observation, we allow future Dashboard UIs, Slack Notification Bots, and external Telemetry aggregators to listen to system state changes without requiring any modifications to the Core Plugin Manager.

---

# 2. Event Schemas: `src/plugins/events.py`

*(I have generated the actual Python dataclasses so the Event Bus will have strongly-typed objects to route in Phase 06).*

```python
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
```

---

# 3. Architecture Guidance

### Publishers
The primary publishers of these events are internal infrastructure components, **not** the plugin authors themselves.
- **`PluginDiscoverer`**: Publishes `PluginDiscoveredEvent` immediately upon finding and parsing a valid `manifest.yaml` during the initial file system scan.
- **`PluginLifecycleSupervisor`**: Publishes `PluginInitialized`, `PluginStarted`, `PluginPaused`, etc., upon successfully wrapping a third-party method.
- **`PluginHealthMonitor`**: Publishes `PluginFailedEvent` when a plugin strikes out (fails 3 heartbeats), and `PluginRecoveredEvent` if it bounces back.

By keeping publication inside the Supervisors rather than the Plugin Base Classes, we ensure that a maliciously authored plugin cannot falsify its state to the master Event Bus.

### Subscribers
The central Event Bus (Phase 06) will route these topics dynamically. Target subscribers include:
- **State Manager (`src/core/state.py`)**: Subscribes to all `Plugin*Event` topics to maintain an in-memory dictionary of the global system state for HTTP API queries.
- **Workflow Engine**: Subscribes to `PluginFailedEvent`. If the Video Builder plugin fails, the Workflow Engine instantly receives the broadcast and can gracefully halt the rendering pipeline.
- **Notification Plugin**: A custom Slack/Discord bot plugin could subscribe to `PluginFailedEvent` and `PluginRecoveredEvent` to alert administrators in real-time.

### Payload Ordering & Versioning
- **Ordering (Causality)**: Because these events are fired asynchronously, a subscriber (like a DB writer) might process a `PluginStarted` event before the `PluginInitialized` event due to thread contention. To solve this, all events generate an absolute UTC `timestamp` field at the exact moment of instantiation. Subscribers are instructed to drop events if a newer timestamp has already been processed for that specific `plugin_id`.
- **Versioning**: Every payload hardcodes `event_version = "1.0.0"`. If we ever change the schema of `PluginFailedEvent` to include a `memory_dump` binary payload, we will bump it to `"2.0.0"`. Subscribers can write simple `if event.event_version == "1.0.0":` logic to maintain backward compatibility during live rolling upgrades.
