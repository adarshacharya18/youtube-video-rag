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
