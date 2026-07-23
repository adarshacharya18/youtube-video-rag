"""
Metadata Enrichment Engine.

Rule-based heuristic engine that infers deep semantic metadata (Data Structures, 
Algorithms, Animation Hints) from Normalized Documents without burning expensive LLM tokens.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from src.plugins.ingestion.normalizer import NormalizedDocument


@dataclass
class EnrichedMetadata:
    """Strongly typed schema for the inferred heuristic data."""
    primary_algorithm: str = "Unknown"
    data_structures: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    difficulty: str = "Medium"
    prerequisites: List[str] = field(default_factory=list)
    related_concepts: List[str] = field(default_factory=list)
    educational_level: str = "Intermediate"
    animation_hints: List[str] = field(default_factory=list)
    learning_objectives: List[str] = field(default_factory=list)
    interview_topics: List[str] = field(default_factory=list)


class MetadataEnricher:
    """
    Deterministically enriches documents using keyword heuristics and tag mapping.
    """
    
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        
        # Taxonomy Dictionaries for O(1) Lookups (Zero-LLM Heuristics)
        self._ds_keywords = {
            "Array": ["array", "nums", "indices", "subarray"],
            "Hash Table": ["hash table", "hash map", "dictionary", "frequency map"],
            "Linked List": ["linked list", "node", "next pointer", "head", "tail"],
            "Tree": ["binary tree", "bst", "root", "leaf", "child node"],
            "Graph": ["graph", "edges", "vertices", "adjacency", "directed graph"],
            "Stack": ["stack", "lifo", "pop from top"],
            "Queue": ["queue", "fifo", "dequeue"],
            "Heap": ["heap", "priority queue", "kth largest"]
        }
        
        self._algo_keywords = {
            "Binary Search": ["binary search", "sorted array", "o(log n)", "mid ="],
            "Depth-First Search": ["depth-first", "dfs", "recursion", "backtracking"],
            "Breadth-First Search": ["breadth-first", "bfs", "level order"],
            "Dynamic Programming": ["dynamic programming", "dp", "memoization", "tabulation", "overlapping subproblems"],
            "Two Pointers": ["two pointers", "left and right", "start and end", "sliding window"],
            "Greedy": ["greedy", "optimal substructure"],
            "Sorting": ["sort", "o(n log n)", "merge sort", "quick sort"]
        }

    def enrich(self, doc: NormalizedDocument) -> NormalizedDocument:
        """
        Applies heuristic rules to expand the document's metadata.
        Returns a new frozen dataclass copy.
        """
        enriched = EnrichedMetadata()
        
        # 1. Inherit Explicit Metadata (Passed natively from LeetCode Connector)
        enriched.difficulty = doc.metadata.get("difficulty", "Medium")
        
        # 2. Build the Lowercase Text Corpus for O(1) Regex-less scanning
        text_corpus = (doc.title + " " + doc.markdown + " " + " ".join(doc.tags)).lower()
        
        # 3. Infer Data Structures
        ds_set: Set[str] = set()
        for ds, keywords in self._ds_keywords.items():
            if any(kw in text_corpus for kw in keywords):
                ds_set.add(ds)
        enriched.data_structures = list(ds_set)
        
        # 4. Infer Algorithms & Patterns
        algo_set: Set[str] = set()
        for algo, keywords in self._algo_keywords.items():
            if any(kw in text_corpus for kw in keywords):
                algo_set.add(algo)
        enriched.patterns = list(algo_set)
        
        if algo_set:
            # Heuristic: Pick the first matched pattern as the Primary for Scripting Focus
            enriched.primary_algorithm = enriched.patterns[0]
            
        # 5. Infer Educational Level from Difficulty
        if enriched.difficulty == "Easy":
            enriched.educational_level = "Beginner"
        elif enriched.difficulty == "Hard":
            enriched.educational_level = "Advanced"
            
        # 6. Generate Manim Animation Hints (Pre-computing for the Rendering Engine)
        hints: Set[str] = set()
        if "Tree" in enriched.data_structures:
            hints.add("RENDER_NODE_TREE")
            hints.add("HIGHLIGHT_RECURSION_STACK")
        if "Two Pointers" in enriched.patterns:
            hints.add("RENDER_ARRAY_WITH_L_R_ARROWS")
        if "Graph" in enriched.data_structures:
            hints.add("RENDER_DIRECTED_GRAPH")
        if "Hash Table" in enriched.data_structures:
            hints.add("RENDER_KEY_VALUE_BUCKETS")
        enriched.animation_hints = list(hints)
        
        # 7. Map to Interview Topics & Prerequisites
        enriched.interview_topics = list(set(enriched.data_structures + enriched.patterns))
        if "Dynamic Programming" in enriched.patterns:
            enriched.prerequisites.append("Recursion")
            enriched.prerequisites.append("Memoization")
            
        # 8. Generate Auto-Learning Objectives
        if enriched.primary_algorithm != "Unknown":
            enriched.learning_objectives.append(f"Master the {enriched.primary_algorithm} algorithm.")
        if enriched.data_structures:
            enriched.learning_objectives.append(f"Learn how to physically manipulate a {enriched.data_structures[0]}.")
            
        # 9. Pack results cleanly into the Immutable Document Metadata map
        new_metadata = dict(doc.metadata)
        new_metadata["enriched"] = {
            "primary_algorithm": enriched.primary_algorithm,
            "data_structures": enriched.data_structures,
            "patterns": enriched.patterns,
            "difficulty": enriched.difficulty,
            "prerequisites": enriched.prerequisites,
            "educational_level": enriched.educational_level,
            "animation_hints": enriched.animation_hints,
            "learning_objectives": enriched.learning_objectives,
            "interview_topics": enriched.interview_topics
        }
        
        # 10. Expand the Root Tags list for high-speed SQLite/ChromaDB indexing
        merged_tags = list(set(doc.tags + enriched.data_structures + enriched.patterns))
        
        return NormalizedDocument(
            id=doc.id,
            title=doc.title,
            markdown=doc.markdown,
            metadata=new_metadata,
            tags=merged_tags
        )
