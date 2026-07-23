# 12_Event_Schemas.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Designed  

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Event Envelope & Metadata (Base Schema)](#2-event-envelope--metadata-base-schema)
3. [Data & Reasoning Payloads](#3-data--reasoning-payloads)
4. [Content Generation Payloads](#4-content-generation-payloads)
5. [Assembly & Distribution Payloads](#5-assembly--distribution-payloads)
6. [System & Orchestration Payloads](#6-system--orchestration-payloads)
7. [Validation & Serialization Contracts](#7-validation--serialization-contracts)

---

# 1. Executive Summary

This document specifies the concrete Python `dataclass` representations for the Event-Driven Architecture defined in Step 10 & 11. By splitting the event into a standard **Envelope/Metadata** object and a strictly typed **Payload** object, the `EventBus` can route, trace, and prioritize messages without needing to understand the underlying business payload.

All schemas are `@dataclass(frozen=True)` to guarantee immutability. Once a plugin emits an event, it cannot be accidentally mutated by another plugin.

---

# 2. Event Envelope & Metadata (Base Schema)

This is the universal wrapper for all events in the system.

```python
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any, Generic, TypeVar

# Payload Type Variable
T = TypeVar("T")

class EventPriority(IntEnum):
    CRITICAL = 0
    HIGH = 2
    NORMAL = 5
    LOW = 8

@dataclass(frozen=True)
class EventMetadata:
    """Standardized metadata ensuring traceability and routing compatibility."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    
    # Traceability
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str | None = None
    pipeline_id: str = "default_pipeline"
    user_context: dict[str, str] = field(default_factory=dict)
    
    # Origin & Versioning
    plugin_id: str = "system"
    version: str = "1.0.0"
    
    # Routing & Retry State
    priority: EventPriority = EventPriority.NORMAL
    retry_count: int = 0


@dataclass(frozen=True)
class IntegrationEvent(Generic[T]):
    """
    The canonical Event Wrapper.
    T is heavily restricted to frozen dataclasses representing the payload.
    """
    name: str
    metadata: EventMetadata
    payload: T
```

---

# 3. Data & Reasoning Payloads

```python
@dataclass(frozen=True)
class ScrapeCompletePayload:
    slug: str
    title: str
    difficulty: str
    raw_content: str
    source_url: str

@dataclass(frozen=True)
class TagsExtractedPayload:
    slug: str
    tags: list[str]
    confidence: float

@dataclass(frozen=True)
class ContextReadyPayload:
    slug: str
    retrieved_chunks: list[str]
    educational_plan: str
    
@dataclass(frozen=True)
class GraphUpdatedPayload:
    slug: str
    nodes_added: int
    edges_added: int
```

---

# 4. Content Generation Payloads

```python
@dataclass(frozen=True)
class ScriptGenerationCompletePayload:
    slug: str
    voiceover_text: str
    visual_cues: list[dict[str, Any]]
    duration_estimate_sec: int
    prompt_version: str

@dataclass(frozen=True)
class AudioRenderedPayload:
    slug: str
    audio_path: str
    duration: float
    tts_engine_used: str

@dataclass(frozen=True)
class RenderCompletePayload:
    slug: str
    video_path: str
    resolution: str
    render_time_sec: float
```

---

# 5. Assembly & Distribution Payloads

```python
@dataclass(frozen=True)
class VideoAssembledPayload:
    slug: str
    final_video_path: str
    filesize_mb: float
    duration: float
    includes_subtitles: bool

@dataclass(frozen=True)
class YoutubePublishedPayload:
    slug: str
    youtube_url: str
    video_id: str
    status: str
    published_at: str
```

---

# 6. System & Orchestration Payloads

```python
@dataclass(frozen=True)
class PipelineLifecyclePayload:
    run_id: str
    slug: str
    status: str  # "STARTED", "COMPLETED", "FATAL_ERROR"
    reason: str | None = None

@dataclass(frozen=True)
class PluginLifecyclePayload:
    plugin_name: str
    version: str
    action: str  # "REGISTERED", "UNREGISTERED"

@dataclass(frozen=True)
class ConfigReloadedPayload:
    changed_keys: list[str]
    reload_time: float
```

---

# 7. Validation & Serialization Contracts

To guarantee system stability, events must self-validate and serialize seamlessly via the `src/core/serialization.py` utility established in Phase 03.

### 7.1 Validation (`__post_init__`)
Because pure Python `@dataclass` objects do not validate types at runtime, plugins rely on the Event Bus to enforce constraints. If a plugin attempts to emit an event with an invalid payload, the infrastructure raises a `ValidationError`.

```python
def validate_event(event: IntegrationEvent[Any]) -> None:
    """Called by the EventBus prior to accepting the message."""
    if not event.metadata.correlation_id:
        raise ValueError("Missing correlation_id")
    if event.metadata.retry_count < 0:
        raise ValueError("Retry count cannot be negative")
```

*(Note: In Phase 04, these classes may be optionally wrapped with `pydantic.dataclasses.dataclass` to leverage automatic runtime coercion).*

### 7.2 Serialization (`asdict`)
Because all properties use strict primitives (or types handled by our custom JSON Encoder), generating a string for the Dead Letter Queue or network transmission is trivial:

```python
from src.core.serialization import serialize_json
import dataclasses

def to_json(event: IntegrationEvent[Any]) -> str:
    # Recursively converts nested dataclasses to primitive dicts
    event_dict = dataclasses.asdict(event)
    return serialize_json(event_dict)
```

### 7.3 Backward Compatibility Upcasting
To support rolling updates where `v1` plugins and `v2` plugins operate simultaneously, the system will support dynamic upcasting logic inside the `EventRegistry`.

```python
def upcast_scrape_complete(payload_v1: dict) -> ScrapeCompletePayload:
    """Upcasts a v1 dictionary into a strongly typed v2 schema."""
    # Handle missing fields gracefully if the schema evolves
    return ScrapeCompletePayload(
        slug=payload_v1["slug"],
        title=payload_v1["title"],
        difficulty=payload_v1.get("difficulty", "Unknown"), # Added in v2
        raw_content=payload_v1["raw_content"],
        source_url=payload_v1.get("source_url", "")
    )
```
