# Phase 10 / 10: Organization Events Architecture

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Event Schemas & Definitions](#2-event-schemas--definitions)
3. [Source Code: `src/core/organization/events.py`](#3-source-code-srccoreorganizationeventspy)
4. [Design Decisions](#4-design-decisions)

---

# 1. Executive Summary

This document finalizes Phase 10 by defining the strictly-typed **Organization Event Topology**. 

Rather than tightly coupling the `IndexPreparer` directly to the Phase 12 `VectorDatabasePlugin`, we utilize the system-wide `EventBus`. The Organization Engine effortlessly hums along, converting chaos into strict Taxonomies, Graph DAGs, and Flattened Chunks, and simply broadcasts its progress as typed Dataclass payloads. Downstream components (like the LLM embedding engine) simply subscribe to these topics and execute when ready.

---

# 2. Event Schemas & Definitions

### Ordering & Triggers
The Phase 10 lifecycle is completely event-driven, typically triggered by Phase 09's `ingestion.persisted` event:
`ingestion.persisted` -> `organization.validated` -> `organization.prereqs_computed` -> `organization.index_ready`.

### Retry Guarantees & Versioning
*   **Retry:** If an event like `organization.index_ready` is published but the Vector DB is offline, the Event Bus routes it to the Dead Letter Queue (DLQ). The DLQ will execute exponential backoff replays indefinitely until the Vector DB accepts the payload.
*   **Versioning:** All payload schemas are defined via immutable `@dataclass` structures. If a schema evolves, a new Major Event Topic (e.g., `v2.organization.index_ready`) will be broadcasted, preventing crashes in legacy Phase 11 subscribers.

### Subscriptions
| Event Topic | Publisher | Subscribers |
| :--- | :--- | :--- |
| `organization.taxonomy_updated` | TaxonomyManager | UI Dashboard (Dropdown sync) |
| `organization.concept_linked` | ConceptGraph | Path Generator (Cache invalidation) |
| `organization.path_generated` | PathGenerator | ScriptGen Engine (Initiate Script) |
| `organization.prereqs_computed` | Analyzer | Metrics, UI (Show missing prereqs) |
| `organization.validated` | Validator | Metrics, Admin Alerts (If invalid) |
| `organization.index_ready` | IndexPreparer | Vector DB (Execute physical Embeddings) |

---

# 3. Source Code: `src/core/organization/events.py`

```python
"""
Organization Event Schemas.

Defines strongly-typed Events published during the Knowledge Organization 
and Curriculum Generation lifecycle.
"""

from dataclasses import dataclass

from src.core.events import Event

# Base namespace for all Organization events (V1)
NAMESPACE = "organization"

# ---------------------------------------------------------
# Taxonomy & Graph Mutation Events
# ---------------------------------------------------------
@dataclass
class TaxonomyUpdatedPayload:
    domain: str
    category_id: str
    action: str  # "CREATE", "UPDATE", "DELETE"
    version: int

class TaxonomyUpdated(Event):
    """
    Published when a Taxonomy domain is mutated.
    Subscribers: UI Dashboard (Refresh dropdowns), ConceptGraph (Validation Check)
    """
    def __init__(self, payload: TaxonomyUpdatedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.taxonomy_updated",
            payload={"domain": payload.domain, "id": payload.category_id, "action": payload.action},
            correlation_id=correlation_id
        )

@dataclass
class ConceptLinkedPayload:
    source_id: str
    target_id: str
    edge_type: str

class ConceptLinked(Event):
    """
    Published when a new mathematical edge is drawn in the DAG.
    Subscribers: LearningPathGenerator (Invalidate Cache), IndexPreparer (Re-index historical graphs)
    """
    def __init__(self, payload: ConceptLinkedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.concept_linked",
            payload={"source": payload.source_id, "target": payload.target_id, "type": payload.edge_type},
            correlation_id=correlation_id
        )

# ---------------------------------------------------------
# Curriculum & Prerequisite Analytics
# ---------------------------------------------------------
@dataclass
class LearningPathGeneratedPayload:
    path_id: str
    difficulty: str
    node_count: int

class LearningPathGenerated(Event):
    """
    Published when a new topological syllabus is synthesized.
    Subscribers: ScriptGeneration (Trigger Script writing), UI (Render SVG Path)
    """
    def __init__(self, payload: LearningPathGeneratedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.path_generated",
            payload={"id": payload.path_id, "diff": payload.difficulty, "nodes": payload.node_count},
            correlation_id=correlation_id
        )

@dataclass
class PrerequisitesComputedPayload:
    document_id: str
    is_ready: bool
    missing_count: int

class PrerequisitesComputed(Event):
    """
    Published after mathematically analyzing a document's dependencies.
    Subscribers: VectorDatabasePlugin (Inject into metadata payload)
    """
    def __init__(self, payload: PrerequisitesComputedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.prereqs_computed",
            payload={"doc": payload.document_id, "ready": payload.is_ready, "missing": payload.missing_count},
            correlation_id=correlation_id
        )

# ---------------------------------------------------------
# Diagnostics & Terminal Resolution
# ---------------------------------------------------------
@dataclass
class KnowledgeValidatedPayload:
    is_valid: bool
    violation_count: int

class KnowledgeValidated(Event):
    """
    Published after a full system diagnostic.
    Subscribers: Metrics, DLQ (if invalid, halts processing), PagerDuty (Webhooks)
    """
    def __init__(self, payload: KnowledgeValidatedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.validated",
            payload={"valid": payload.is_valid, "violations": payload.violation_count},
            correlation_id=correlation_id
        )

@dataclass
class IndexPreparedPayload:
    document_id: str
    chunk_count: int
    version: str

class IndexPrepared(Event):
    """
    The Final Phase 10 Terminal Event.
    Signals that a document is mathematically flattened, taxonomy-verified, and chunked.
    Subscribers: VectorDatabasePlugin (Triggers the physical LLM text embedding API call)
    """
    def __init__(self, payload: IndexPreparedPayload, correlation_id: str) -> None:
        super().__init__(
            topic=f"{NAMESPACE}.index_ready",
            payload={"doc": payload.document_id, "chunks": payload.chunk_count, "version": payload.version},
            correlation_id=correlation_id
        )
```

---

# 4. Design Decisions

1. **Strict Dataclass Safety:** By forcing developers to instantiate `IndexPreparedPayload(document_id="two-sum", chunk_count=5, version="1.0.0")`, we entirely eliminate `KeyError` runtime crashes. The static type checker explicitly enforces the schema before the Python code is even executed.
2. **Namespace Wildcard Routing:** Because all events strictly start with `organization.*`, the master `WorkflowEngine` (built in Phase 07) can easily subscribe to the entire subsystem using wildcard topics if it needs to monitor global progression velocity.
3. **The Index Terminal Handshake:** The `IndexPrepared` event perfectly encapsulates the conclusion of Phase 10. The payload does *not* contain the massive chunks of text (which would bloat the Event Store). It only contains the `document_id`. The downstream Vector Engine simply subscribes to this event, reads the ID, and natively queries the `MemoryService` or `StorageManager` to fetch the actual heavy chunks, keeping the Event Bus blazing fast.
