"""
Comprehensive Test Suite for Knowledge Organization Platform.

Tests Taxonomy rules, Kahn's Topological Sort (Concept Graph),
Curriculum synthesis, and DAG validation integrity.
"""

import pytest

from src.core.organization.concept_graph import ConceptGraph, ConceptNode, ConceptType
from src.core.organization.index_preparer import IndexPreparer
from src.core.organization.knowledge_validator import KnowledgeValidator
from src.core.organization.learning_path_generator import LearningPathGenerator, PathDifficulty
from src.core.organization.metadata_classifier import ClassifiedMetadata
from src.core.organization.prerequisite_analyzer import PrerequisiteAnalyzer, PrerequisiteMetadata
from src.core.organization.taxonomy_manager import TaxonomyManager
from src.core.storage_manager import StorageManager

# ---------------------------------------------------------
# Fixtures & Environment Setup
# ---------------------------------------------------------
@pytest.fixture
def storage():
    """Spin up an isolated in-memory DB for blisteringly fast I/O."""
    return StorageManager("sqlite:///:memory:")

@pytest.fixture
async def taxonomy(storage):
    """Mocks the core FAANG terminology dictionary."""
    tax = TaxonomyManager(storage)
    await tax.initialize()
    
    tax.add_category("algorithms", "binary_search", ["bs", "binarysearch"])
    tax.add_category("algorithms", "dijkstra", ["shortest_path", "dijkstras"])
    tax.add_category("data_structures", "array", ["list", "vector"])
    tax.add_category("data_structures", "graph", ["graphs", "network"])
    
    return tax

@pytest.fixture
def graph():
    """Builds a mathematical DAG mapping FAANG concepts."""
    g = ConceptGraph()
    # 1. Initialize Vertices
    g.add_node("array", ConceptType.DATA_STRUCTURE, difficulty=1)
    g.add_node("graph", ConceptType.DATA_STRUCTURE, difficulty=2)
    g.add_node("binary_search", ConceptType.ALGORITHM, difficulty=1)
    g.add_node("dijkstra", ConceptType.ALGORITHM, difficulty=3) # Level 3 (Hard)
    
    # 2. Initialize Directed Vectors (REQUIRES)
    g.add_prerequisite("binary_search", "array")
    g.add_prerequisite("dijkstra", "graph")
    g.add_prerequisite("dijkstra", "array")
    
    return g

# ---------------------------------------------------------
# Taxonomy & Dictionary Integrity
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_taxonomy_alias_resolution(taxonomy):
    # Valid Canonical lookups
    assert taxonomy.resolve_alias("algorithms", "bs") == "binary_search"
    assert taxonomy.resolve_alias("data_structures", "vector") == "array"
    
    # Missing aliases should gracefully fallback to the raw input (for manual review)
    assert taxonomy.resolve_alias("algorithms", "unknown_algo") == "unknown_algo"

@pytest.mark.asyncio
async def test_taxonomy_validation(taxonomy):
    assert taxonomy.validate("algorithms", "binary_search") is True
    # An Array is explicitly NOT an algorithm
    assert taxonomy.validate("algorithms", "array") is False 

# ---------------------------------------------------------
# Concept Graph (DAG Mathematics)
# ---------------------------------------------------------
def test_graph_add_nodes_and_edges(graph):
    """Proves O(V+E) instantiation limits."""
    assert len(graph._nodes) == 4
    deps = graph.get_prerequisites("dijkstra", deep=False)
    assert "graph" in deps
    assert "array" in deps

def test_graph_cycle_detection(graph):
    """CRITICAL: Proves the DAG physically rejects impossible circular dependencies."""
    from src.core.organization.concept_graph import CycleDetectedError
    
    # Dijkstra already requires Array. 
    # If a Jr. Dev tries to make Array require Dijkstra, the system MUST crash.
    with pytest.raises(CycleDetectedError):
        graph.add_prerequisite("array", "dijkstra")

def test_graph_deep_prerequisite_traversal(graph):
    """Proves the recursive back-propagation tracks the entire knowledge lineage."""
    graph.add_node("A", ConceptType.ALGORITHM, 1)
    graph.add_node("B", ConceptType.ALGORITHM, 1)
    graph.add_node("C", ConceptType.ALGORITHM, 1)
    
    graph.add_prerequisite("C", "B")
    graph.add_prerequisite("B", "A")
    
    # Shallow = B only
    shallow = graph.get_prerequisites("C", deep=False)
    assert "B" in shallow
    assert "A" not in shallow
    
    # Deep = B and A
    deep = graph.get_prerequisites("C", deep=True)
    assert "B" in deep
    assert "A" in deep

# ---------------------------------------------------------
# Topological Sorting & Curriculum Generator
# ---------------------------------------------------------
def test_analyzer_kahn_topological_sort(graph, taxonomy):
    """Proves that Kahn's algorithm flawlessly sequences a syllabus."""
    analyzer = PrerequisiteAnalyzer(graph, taxonomy)
    
    # User selects 4 random topics in total chaos
    path = analyzer._generate_unified_path(["dijkstra", "binary_search", "array", "graph"])
    
    # Mathematical Assertions:
    # Array (InDegree=0) MUST be taught before Binary Search (Requires Array)
    assert path.index("array") < path.index("binary_search")
    # Graph (InDegree=0) MUST be taught before Dijkstra (Requires Graph)
    assert path.index("graph") < path.index("dijkstra")
    # Array MUST be taught before Dijkstra (Requires Array)
    assert path.index("array") < path.index("dijkstra")

def test_learning_path_difficulty_scaling(graph, taxonomy):
    """Proves that Beginners are completely shielded from Hard (Level-3) nodes."""
    analyzer = PrerequisiteAnalyzer(graph, taxonomy)
    generator = LearningPathGenerator(graph, analyzer)
    
    # Generate a BEGINNER path specifically for Dijkstra
    path = generator.generate_topic_path("dijkstra", PathDifficulty.BEGINNER)
    
    # Array is difficulty 1 (Included for beginners)
    assert "array" in path.ordered_concepts
    
    # Dijkstra is difficulty 3 (Hard). It MUST be explicitly excluded 
    # to prevent beginner cognitive overload.
    assert "dijkstra" not in path.ordered_concepts

# ---------------------------------------------------------
# System Diagnostics & Vector Preparation
# ---------------------------------------------------------
def test_validator_detects_memory_corruption(graph, taxonomy):
    """Proves the Daemon detects manually corrupted database states."""
    from src.core.organization.concept_graph import Edge, EdgeType
    
    # Manually inject a ghost edge, bypassing Python safety wrappers
    graph._out_edges["array"].append(Edge("array", "ghost_node_123", EdgeType.REQUIRES))
    
    validator = KnowledgeValidator(graph, taxonomy)
    report = validator.run_full_diagnostic()
    
    # The system MUST halt the pipeline
    assert report.is_valid is False
    assert len(report.broken_references) == 1
    assert "ghost_node_123" in report.broken_references[0]

def test_index_chunking_boundaries():
    """Proves Markdown paragraphs are split identically for the Vector Store."""
    preparer = IndexPreparer(max_tokens_per_chunk=10) # Limit: ~40 chars
    
    text = "A" * 30 + "\n\n" + "B" * 30
    
    # Mocks
    c_meta = ClassifiedMetadata("E", "A", "P", "B", "L", "O(1)", "O(1)", [])
    p_meta = PrerequisiteMetadata("1", [], [], [])
    
    prepared = preparer.prepare("doc1", text, c_meta, p_meta)
    
    # Assertions: 60 total chars / 4 chars per token = 15 total tokens.
    # 15 tokens > 10 token limit, therefore it MUST perfectly split exactly at the \n\n.
    assert len(prepared.chunks) == 2
    assert "A" * 30 in prepared.chunks[0].text_content
    assert "B" * 30 in prepared.chunks[1].text_content
    
    # Prove Deterministic Hashing (For Idempotent Pinecone Upserts)
    assert "doc1_chunk_0" in prepared.chunks[0].chunk_id
    assert "doc1_chunk_1" in prepared.chunks[1].chunk_id
