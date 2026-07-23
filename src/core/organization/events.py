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
