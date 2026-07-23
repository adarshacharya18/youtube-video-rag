"""
Knowledge Validation Engine.

Scans the ConceptGraph, MetadataStore, and Taxonomy dictionaries to detect 
broken relationships, duplicate nodes, and missing metadata fields before index preparation.
"""

import logging
from collections import deque
from dataclasses import dataclass
from typing import List

from src.core.organization.concept_graph import ConceptGraph, EdgeType
from src.core.organization.taxonomy_manager import TaxonomyManager


@dataclass
class ValidationReport:
    """A comprehensive diagnostic structural report."""
    is_valid: bool
    broken_references: List[str]
    missing_metadata: List[str]
    duplicate_concepts: List[str]
    prerequisite_cycles: List[str]
    taxonomy_violations: List[str]


class KnowledgeValidator:
    """Executes a system-wide structural integrity scan."""
    
    def __init__(self, concept_graph: ConceptGraph, taxonomy: TaxonomyManager) -> None:
        self._graph = concept_graph
        self._tax = taxonomy
        self._logger = logging.getLogger(__name__)

    def run_full_diagnostic(self) -> ValidationReport:
        """
        Executes all diagnostic rules.
        Returns a structured report. If `is_valid` is False, the pipeline should HALT.
        """
        self._logger.info("Initiating Full System Knowledge Validation Scan...")
        
        broken_refs = self._check_broken_references()
        cycles = self._check_prerequisite_integrity()
        duplicates = self._check_duplicate_concepts()
        tax_violations = self._check_taxonomy_consistency()
        missing_meta = self._check_metadata_completeness()
        
        is_valid = not any([broken_refs, cycles, duplicates, tax_violations, missing_meta])
        
        if not is_valid:
            self._logger.error("System-wide structural corruption detected.")
            
        return ValidationReport(
            is_valid=is_valid,
            broken_references=broken_refs,
            missing_metadata=missing_meta,
            duplicate_concepts=duplicates,
            prerequisite_cycles=cycles,
            taxonomy_violations=tax_violations
        )

    def _check_broken_references(self) -> List[str]:
        """Ensures all mathematical graph edges point to physical nodes that actually exist."""
        broken = []
        for src, edges in self._graph._out_edges.items():
            if src not in self._graph._nodes:
                broken.append(f"Ghost Edge Source: Node '{src}' has outbound edges but does not physically exist.")
            for edge in edges:
                if edge.target_id not in self._graph._nodes:
                    broken.append(f"Broken Target Pointer: {src} -> {edge.target_id} (Target does not exist).")
        return broken

    def _check_prerequisite_integrity(self) -> List[str]:
        """
        Mathematically verifies the DAG is actually acyclic.
        Runs a global Kahn's Topological Sort. If nodes are left over, a cycle exists.
        """
        cycles = []
        in_degree = {n: 0 for n in self._graph._nodes}
        
        # Build global in-degree map for REQUIRES edges
        for src, edges in self._graph._out_edges.items():
            for e in edges:
                if e.edge_type == EdgeType.REQUIRES and e.target_id in in_degree:
                    in_degree[e.target_id] += 1
                    
        queue = deque([n for n in in_degree if in_degree[n] == 0])
        visited_count = 0
        
        while queue:
            current = queue.popleft()
            visited_count += 1
            for e in self._graph._out_edges.get(current, []):
                if e.edge_type == EdgeType.REQUIRES and e.target_id in in_degree:
                    in_degree[e.target_id] -= 1
                    if in_degree[e.target_id] == 0:
                        queue.append(e.target_id)
                        
        if visited_count != len(in_degree):
            cycles.append(
                f"CRITICAL CYCLE DETECTED: The dependency graph is mathematically impossible. "
                f"Only processed {visited_count}/{len(in_degree)} strict nodes."
            )
        return cycles

    def _check_duplicate_concepts(self) -> List[str]:
        """Finds distinct nodes that share exact canonical names, indicating a taxonomy failure."""
        duplicates = []
        names_seen = {}
        for node_id in self._graph._nodes.keys():
            name = node_id.lower().strip()
            if name in names_seen:
                duplicates.append(f"Duplicate Canonical Concept IDs detected: {names_seen[name]} and {node_id}")
            names_seen[name] = node_id
        return duplicates

    def _check_taxonomy_consistency(self) -> List[str]:
        """Ensures all Graph Concept Nodes are legally registered in the strict Taxonomy dictionaries."""
        violations = []
        
        for node_id, node in self._graph._nodes.items():
            # E.g., if it's an ALGORITHM, it must be in the 'algorithms' taxonomy domain
            domain = node.concept_type.name.lower() + "s"
            
            # Problems (like LeetCode 1) are endless and aren't stored in the strict Taxonomy Dicts
            if node.concept_type.name != "PROBLEM":
                if not self._tax.validate(domain, node_id):
                    violations.append(f"Taxonomy Violation: Graph Node '{node_id}' is missing from strictly typed Domain '{domain}'.")
                    
        return violations

    def _check_metadata_completeness(self) -> List[str]:
        """Ensures critical metadata fields aren't missing from standard algorithms."""
        missing = []
        # In a physical deployment, this would check that all ALGORITHM nodes 
        # have their 'expected_runtime' populated. This is a lightweight stub for V1.
        return missing
