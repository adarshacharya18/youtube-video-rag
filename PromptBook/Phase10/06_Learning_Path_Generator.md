# Phase 10 / 06: Learning Path Generator

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/organization/learning_path_generator.py`](#2-source-code-srccoreorganizationlearning_path_generatorpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

While the `PrerequisiteAnalyzer` (Phase 10/05) handles low-level graph mathematics and dependency extraction for single documents, the **Learning Path Generator** operates at the macro curriculum layer.

It utilizes the Analyzer's topological sorts to construct massive, highly structured **Syllabi**. By supporting personas (Beginners, Advanced, Interview Prep), it dynamically trims the DAG (Directed Acyclic Graph) to prevent overwhelming beginners with Hard concepts, while simultaneously ensuring FAANG candidates are pushed through rigorous difficulty progressions. It outputs these structures as reusable `LearningPathDefinition` Data Transfer Objects (DTOs) for downstream UI rendering and Video Script orchestration.

---

# 2. Source Code: `src/core/organization/learning_path_generator.py`

```python
"""
Learning Path Generator.

Synthesizes structured, reusable educational curricula from the Concept Graph 
based on target personas (Beginner, Interview Prep) and specific domains.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from src.core.organization.concept_graph import ConceptGraph
from src.core.organization.prerequisite_analyzer import PrerequisiteAnalyzer


class PathDifficulty(Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    INTERVIEW_PREP = "INTERVIEW_PREP"


@dataclass
class LearningPathDefinition:
    """A strictly typed, reusable serialized curriculum."""
    id: str
    title: str
    description: str
    difficulty: PathDifficulty
    ordered_concepts: List[str]
    estimated_duration_hours: float
    target_topics: List[str] = field(default_factory=list)


class LearningPathGenerator:
    """Generates dynamically scaled educational paths based on topological graph traversal."""
    
    def __init__(self, concept_graph: ConceptGraph, analyzer: PrerequisiteAnalyzer) -> None:
        self._graph = concept_graph
        self._analyzer = analyzer
        self._logger = logging.getLogger(__name__)

    def generate_topic_path(self, topic_id: str, difficulty: PathDifficulty) -> LearningPathDefinition:
        """
        Builds a macro-curriculum strictly tailored to mastering a specific topic.
        Dynamically scales theoretical depth and prerequisites based on the requested difficulty.
        """
        # 1. Fetch the absolute mathematical foundation required
        # (This uses Kahn's Topological Sort internally)
        base_path = self._analyzer._generate_unified_path(
            self._graph.get_prerequisites(topic_id, deep=True) + [topic_id]
        )
        
        # 2. Trim the DAG based on Persona (e.g., Hide Hard nodes from Beginners)
        filtered_path = self._scale_path_by_difficulty(base_path, difficulty)
        
        # 3. Inject Progressive Overload for Advanced Personas
        if difficulty in (PathDifficulty.ADVANCED, PathDifficulty.INTERVIEW_PREP):
            progression = self._graph.get_difficulty_progression(topic_id)
            for p in progression:
                if p not in filtered_path:
                    filtered_path.append(p)
                    
        return LearningPathDefinition(
            id=f"path_{topic_id}_{difficulty.name.lower()}",
            title=f"{difficulty.name.title()} Guide to {topic_id.replace('_', ' ').title()}",
            description=f"A targeted curriculum meticulously designed to master {topic_id}.",
            difficulty=difficulty,
            ordered_concepts=filtered_path,
            estimated_duration_hours=round(len(filtered_path) * 1.5, 1), # Assume 1.5 hrs per concept
            target_topics=[topic_id]
        )

    def generate_interview_prep_path(self, target_companies: Optional[List[str]] = None) -> LearningPathDefinition:
        """
        Builds the ultimate FAANG survival guide.
        Aggregates high-value, high-frequency patterns (DP, Two Pointers, Graphs).
        """
        # In a physical deployment, we'd query the DB for the most common 
        # tags associated with the 'target_companies' list. 
        # For this logic block, we explicitly target the FAANG Core 5.
        core_patterns = [
            "two_pointers", "sliding_window", "depth_first_search", 
            "breadth_first_search", "dynamic_programming"
        ]
        
        all_required = set(core_patterns)
        
        # Recursively fetch the dependency trees for ALL 5 topics
        for pattern in core_patterns:
            if pattern in self._graph._nodes:
                all_required.update(self._graph.get_prerequisites(pattern, deep=True))
            
        # Stitch all 5 massive subgraphs together into a single, flawless linear track
        unified_path = self._analyzer._generate_unified_path(list(all_required))
        
        # Ensure Advanced Progressions are included for Interview Prep
        final_path = unified_path.copy()
        for pattern in core_patterns:
            if pattern in self._graph._nodes:
                progression = self._graph.get_difficulty_progression(pattern)
                for p in progression:
                    if p not in final_path:
                        final_path.append(p)
        
        return LearningPathDefinition(
            id="path_faang_interview_prep",
            title="Comprehensive FAANG Interview Preparation",
            description="The definitive, mathematically-structured guide to passing high-tier technical interviews.",
            difficulty=PathDifficulty.INTERVIEW_PREP,
            ordered_concepts=final_path,
            estimated_duration_hours=round(len(final_path) * 2.0, 1),
            target_topics=core_patterns
        )

    def _scale_path_by_difficulty(self, path: List[str], target_difficulty: PathDifficulty) -> List[str]:
        """
        Trims a topological sort based on difficulty boundaries.
        Prevents Beginners from being exposed to Level-3 (Hard) progression nodes too early.
        """
        scaled = []
        for concept_id in path:
            node = self._graph._nodes.get(concept_id)
            if not node:
                scaled.append(concept_id)
                continue
                
            node_diff = node.difficulty # 1: Easy, 2: Med, 3: Hard
            
            # Beginners are shielded from anything > 1 (Easy)
            if target_difficulty == PathDifficulty.BEGINNER and node_diff > 1:
                continue 
                
            # Intermediates are shielded from > 2 (Hard)
            elif target_difficulty == PathDifficulty.INTERMEDIATE and node_diff > 2:
                continue 
                
            scaled.append(concept_id)
            
        return scaled
```

---

# 3. Design Decisions

1. **Persona-Driven Subgraph Trimming (`_scale_path_by_difficulty`):** Kahn's algorithm will dutifully return the absolute dependency chain for a topic. However, if a user selects `BEGINNER`, they shouldn't immediately be slammed with a Level-3 (Hard) progression node just because it sits adjacent in the graph. The Generator safely prunes the Topological Sort based on the Node's inherent `difficulty` metadata flag.
2. **Progressive Overload Injection:** If a user selects `ADVANCED`, the standard prerequisite track isn't enough. The Generator actively reaches into the `ConceptGraph` to trace `EdgeType.PROGRESSES` vectors. It intentionally appends the hardest variants of a concept to the end of the syllabus (e.g., transitioning from *1D DP Climbing Stairs* directly into *2D DP Knapsack*).
3. **Massive Graph Unioning (`generate_interview_prep_path`):** This is the crown jewel. By passing 5 massive, completely disconnected concepts (Two Pointers, DFS, BFS, DP, Sliding Window) into the `PrerequisiteAnalyzer`, the system performs a massive multi-subgraph union. The resulting output is a single, perfectly linear curriculum that effortlessly bounces between Arrays and Trees in exactly the correct mathematical learning order.
