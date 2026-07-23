# Phase 10 / 05: Prerequisite Analyzer

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/organization/prerequisite_analyzer.py`](#2-source-code-srccoreorganizationprerequisite_analyzerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

While the `ConceptGraph` models the absolute theoretical truth of Computer Science, the **Prerequisite Analyzer** applies that theoretical math to real-world objects. 

It acts as the strict bridging layer that evaluates a specific LeetCode `NormalizedDocument` (or a specific Viewer's learning profile) against the Graph. If a document is tagged with `"A* Search"`, the Analyzer instantly traverses the Graph, discovers that `Priority Queues` and `Heuristics` are required, builds a unified Topological Sort across all combined tags, and injects this structured `PrerequisiteMetadata` into the document before it reaches the Vector Store.

---

# 2. Source Code: `src/core/organization/prerequisite_analyzer.py`

```python
"""
Prerequisite Analyzer.

Analyzes physical documents and user profiles against the theoretical Concept Graph 
to deduce required knowledge, strict learning orders, and structural knowledge gaps.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import List, Set

from src.core.organization.concept_graph import ConceptGraph, EdgeType
from src.core.organization.taxonomy_manager import TaxonomyManager


@dataclass
class ConceptReadiness:
    """Delineates exactly what a Student (or the Script Generator) is missing."""
    is_ready: bool
    missing_prerequisites: List[str] = field(default_factory=list)
    recommended_learning_order: List[str] = field(default_factory=list)


@dataclass
class PrerequisiteMetadata:
    """Structured Metadata injected into Documents before Vector Embedding."""
    document_id: str
    direct_dependencies: List[str]
    all_historical_dependencies: List[str]
    learning_order: List[str]


class PrerequisiteAnalyzer:
    """Infers structural readiness and strict curriculum gaps."""
    
    def __init__(self, concept_graph: ConceptGraph, taxonomy: TaxonomyManager) -> None:
        self._graph = concept_graph
        self._tax = taxonomy
        self._logger = logging.getLogger(__name__)

    def analyze_document(self, document_id: str, tags: List[str]) -> PrerequisiteMetadata:
        """
        Analyzes a single LeetCode document (e.g., 'two-sum' with tags ['hash_table', 'array']).
        Resolves canonical IDs, fetches Deep dependencies, and compiles a Unified Topological Path.
        """
        canonical_tags: Set[str] = set()
        
        # 1. Resolve raw chaotic tags to strict Taxonomy Canonical IDs
        for tag in tags:
            # Check Algorithms Domain
            resolved = self._tax.resolve_alias("algorithms", tag)
            if resolved in self._graph._nodes:
                canonical_tags.add(resolved)
                continue
                
            # Check Data Structures Domain
            resolved = self._tax.resolve_alias("data_structures", tag)
            if resolved in self._graph._nodes:
                canonical_tags.add(resolved)

        direct_deps: Set[str] = set()
        historical_deps: Set[str] = set()
        
        # 2. Extract Subgraphs for every resolved Tag
        for tag in canonical_tags:
            direct_deps.update(self._graph.get_prerequisites(tag, deep=False))
            historical_deps.update(self._graph.get_prerequisites(tag, deep=True))
            
        # 3. Generate a Unified Topological Sort covering ALL required tags simultaneously
        unified_subgraph_nodes = historical_deps.union(canonical_tags)
        unified_order = self._generate_unified_path(list(unified_subgraph_nodes))
            
        return PrerequisiteMetadata(
            document_id=document_id,
            direct_dependencies=list(direct_deps),
            all_historical_dependencies=list(historical_deps),
            learning_order=unified_order
        )

    def evaluate_student_readiness(self, target_concept: str, mastered_concepts: List[str]) -> ConceptReadiness:
        """
        Calculates strict knowledge gaps between what a Viewer knows and what the Video requires.
        """
        # Resolve Target Concept
        canonical_target = self._tax.resolve_alias("algorithms", target_concept)
        if canonical_target not in self._graph._nodes:
            canonical_target = self._tax.resolve_alias("data_structures", target_concept)
            
        if canonical_target not in self._graph._nodes:
            raise ValueError(f"Target concept '{target_concept}' does not exist in the Concept Graph.")
            
        # Resolve Mastered Concepts
        mastered_set = set(mastered_concepts)
        
        # Fetch theoretically required knowledge
        required_set = set(self._graph.get_prerequisites(canonical_target, deep=True))
        
        # Determine the Mathematical Gap
        missing = required_set - mastered_set
        is_ready = len(missing) == 0
        
        # Build the exact Path to bridge the gap
        learning_order = self._generate_unified_path(list(missing) + [canonical_target]) if missing else []
        
        return ConceptReadiness(
            is_ready=is_ready,
            missing_prerequisites=list(missing),
            recommended_learning_order=learning_order
        )

    def _generate_unified_path(self, nodes: List[str]) -> List[str]:
        """
        Runs Kahn's Algorithm across an arbitrary subset of scattered Graph Nodes.
        Perfectly stitches disjointed concepts into a single linear progression.
        """
        subgraph_nodes = set(nodes)
        if not subgraph_nodes:
            return []
            
        # 1. Build localized In-Degree map
        in_degree = {node: 0 for node in subgraph_nodes}
        for node in subgraph_nodes:
            for edge in self._graph._out_edges.get(node, []):
                if edge.edge_type == EdgeType.REQUIRES and edge.target_id in subgraph_nodes:
                    in_degree[edge.target_id] += 1
                    
        # 2. Queue foundation nodes (0 local prerequisites)
        queue = deque([n for n in subgraph_nodes if in_degree[n] == 0])
        path: List[str] = []
        
        # 3. Kahn's Topological Sort
        while queue:
            current = queue.popleft()
            path.append(current)
            for edge in self._graph._out_edges.get(current, []):
                if edge.edge_type == EdgeType.REQUIRES and edge.target_id in subgraph_nodes:
                    in_degree[edge.target_id] -= 1
                    if in_degree[edge.target_id] == 0:
                        queue.append(edge.target_id)
                        
        return path
```

---

# 3. Design Decisions

1. **Unified Graph Compilation (`analyze_document`):** If a LeetCode problem requires *both* `Dijkstra` and `Dynamic Programming`, simply generating two separate learning paths would be chaotic for an LLM to read. The Analyzer intelligently unions the historical dependencies of *both* domains together, and runs Kahn's Topological Sort over the entire unified matrix, guaranteeing a flawless, singular linear track that intertwines both topics safely.
2. **Student Gap Analysis (`evaluate_student_readiness`):** Instead of forcing an LLM to hallucinate "what should the student review?", this function mathematically performs `required_set - mastered_set`. If a student knows `Hash Maps` but wants to learn `Dijkstra`, it extracts exactly what's missing (`Graph Theory`, `Priority Queues`) and builds a specific, customized bridge path to get them there. This will be critical for generating personalized "Quick Recap" segments in the YouTube videos.
3. **Graceful Subgraph Extraction:** `_generate_unified_path` allows us to run Kahn's algorithm not just on the whole graph, but on arbitrary, disconnected subsets of nodes, making it incredibly flexible for ad-hoc metadata enrichment.
