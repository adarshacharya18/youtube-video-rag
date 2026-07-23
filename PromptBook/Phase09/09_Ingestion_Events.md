# Phase 09 / 09: Ingestion Events Architecture

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Event Schemas & Definitions](#2-event-schemas--definitions)
3. [Source Code: `src/plugins/ingestion/events.py`](#3-source-code-srcpluginsingestioneventspy)
4. [Design Decisions](#4-design-decisions)

---

# 1. Executive Summary

This document defines the highly decoupled **Ingestion Event Topology**. 

Rather than tightly coupling the `IngestionPipeline` directly to the `ScriptGeneration` module or the `MetricsRegistry` via direct Python imports, we utilize the `EventBus` (built in Phase 06). By defining strongly typed Event Classes, the Ingestion Engine simply "announces" its state changes to the world. Any interested system (like the Workflow Engine scheduler or a Grafana telemetry daemon) can effortlessly subscribe to these announcements without modifying the Ingestion codebase.

---

# 2. Event Schemas & Definitions

### Ordering & Retry Guarantees
*   **Ordering:** Events are published sequentially as the 6-Step Ingestion FSM progresses (`discovered` -> `fetched` -> `normalized` -> `persisted` -> `completed`). The `correlation_id` guarantees that all 6 events can be grouped together in the `EventStore` later for timeline reconstruction.
*   **Retry:** If an event like `ingestion.failed` is published, the `EventBus` automatically traps it and routes the payload to the Dead Letter Queue (DLQ). The DLQ will execute an exponential backoff replay, resending the `fetch` command until the network recovers.
*   **Versioning:** All payload schemas are defined via `@dataclass`. If a schema evolves in Phase 12, a new major Event Topic (e.g., `v2.ingestion.completed`) will be broadcasted to ensure backward compatibility with older subscribers.

### Subscriptions
| Event Topic | Publisher | Subscribers |
| :--- | :--- | :--- |
| `ingestion.discovered` | Connector | Stream Orchestrator, Metrics |
| `ingestion.fetched` | Pipeline | Audit Logger, Artifact Archiver |
| `ingestion.normalized` | Pipeline | Internal Telemetry |
| `ingestion.enriched` | Pipeline | Analytics |
| `ingestion.duplicate` | Deduplicator | Rate Limiter, Telemetry |
| `ingestion.persisted` | Repository | Cache Manager (Warmup) |
| `ingestion.completed` | Pipeline | Workflow Engine (Trigger next step) |

---

# 3. Source Code: `src/plugins/ingestion/events.py`

```python
"""
Ingestion Event Schemas.

Defines the strongly-typed Event classes published during the Ingestion Pipeline.
Provides explicit Payloads, Versioning, and Subscriber routing definitions.
"""

from dataclasses import dataclass

from src.core.events import Event

# Base namespace for all ingestion events (V1)
NAMESPACE = "ingestion"

# ---------------------------------------------------------
# Phase 1: Discovery & Extraction
# ---------------------------------------------------------
@dataclass
class SourceDiscoveredPayload:
    uri: str
    source_name: str
    search_query: str

class SourceDiscovered(Event):
    """Published when a Connector discovers a new URI to process."""
    def __init__(self, payload: SourceDiscoveredPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.discovered",
            payload={"uri": payload.uri, "source": payload.source_name, "query": payload.search_query},
            correlation_id=correlation_id
        )

@dataclass
class ProblemFetchedPayload:
    uri: str
    content_type: str
    byte_size: int

class ProblemFetched(Event):
    """Published when RawContent is successfully downloaded."""
    def __init__(self, payload: ProblemFetchedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.fetched",
            payload={"uri": payload.uri, "type": payload.content_type, "size": payload.byte_size},
            correlation_id=correlation_id
        )

# ---------------------------------------------------------
# Phase 2: Processing & Transformation
# ---------------------------------------------------------
@dataclass
class NormalizationCompletedPayload:
    uri: str
    markdown_length: int

class NormalizationCompleted(Event):
    """Published after HTML/JSON is stripped into clean Markdown."""
    def __init__(self, payload: NormalizationCompletedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.normalized",
            payload={"uri": payload.uri, "length": payload.markdown_length},
            correlation_id=correlation_id
        )

@dataclass
class MetadataEnrichedPayload:
    uri: str
    primary_algorithm: str
    animation_hints: list[str]

class MetadataEnriched(Event):
    """Published after the Deterministic Rule Engine infers data structures."""
    def __init__(self, payload: MetadataEnrichedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.enriched",
            payload={"uri": payload.uri, "algo": payload.primary_algorithm, "hints": payload.animation_hints},
            correlation_id=correlation_id
        )

# ---------------------------------------------------------
# Phase 3: Resolution & Persistence
# ---------------------------------------------------------
@dataclass
class DuplicateDetectedPayload:
    uri: str
    checksum: str
    version: int

class DuplicateDetected(Event):
    """Published when the SHA-256 hash perfectly matches the SQLite record."""
    def __init__(self, payload: DuplicateDetectedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.duplicate",
            payload={"uri": payload.uri, "hash": payload.checksum, "version": payload.version},
            correlation_id=correlation_id
        )

@dataclass
class ProblemPersistedPayload:
    uri: str
    entity_id: str
    action: str  # e.g., "INSERT" or "UPDATE"
    artifact_path: str

class ProblemPersisted(Event):
    """Published when the KnowledgeRepository successfully commits the UoW."""
    def __init__(self, payload: ProblemPersistedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.persisted",
            payload={"uri": payload.uri, "id": payload.entity_id, "action": payload.action, "artifact": payload.artifact_path},
            correlation_id=correlation_id
        )

# ---------------------------------------------------------
# Phase 4: Termination
# ---------------------------------------------------------
@dataclass
class IngestionCompletedPayload:
    uri: str
    status: str
    duration_ms: float

class IngestionCompleted(Event):
    """
    The Final Terminal Event. 
    Signals the Workflow Engine to proceed to Script Generation.
    """
    def __init__(self, payload: IngestionCompletedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.completed",
            payload={"uri": payload.uri, "status": payload.status, "duration": payload.duration_ms},
            correlation_id=correlation_id
        )
```

---

# 4. Design Decisions

1. **Strong Payload Typing:** Rather than passing random Python dictionaries into the `EventBus` (which leads to `"KeyError"` crashes when developers inevitably typo a key), we strictly define the expected structure via `@dataclass` payload objects. If a developer forgets to pass the `byte_size` to `ProblemFetchedPayload`, the Python static type checker will catch it before the code even runs.
2. **Namespace Routing:** All events strictly follow the `{NAMESPACE}.{action}` pattern (e.g., `ingestion.completed`). This allows the `WorkflowEngine` (Phase 07) to use wildcard topic routing (e.g., subscribing to `ingestion.*` or filtering only `*.completed`).
3. **Correlation Stitching:** Every single event strictly requires a `correlation_id`. Because the system runs asynchronously, 50 different LeetCode problems might be processing at the exact same millisecond. If we want to trace the execution history of "Two Sum", we simply query the `EventStore` for that problem's UUID, instantly grouping its exact `fetched`, `normalized`, and `completed` events together into a perfect timeline.
