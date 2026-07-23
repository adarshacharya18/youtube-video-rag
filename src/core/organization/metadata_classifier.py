"""
Metadata Classification Engine.

Applies strict taxonomic validation to unstructured metadata. Classifies 
expected time/space complexities, visualization effort, and educational depth.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from src.core.organization.taxonomy_manager import TaxonomyManager


@dataclass
class ClassifiedMetadata:
    """Strictly typed classification payload injected into the DB."""
    difficulty: str
    algorithm_family: str
    pattern: str
    educational_level: str
    visualization_complexity: str  # LOW, MEDIUM, HIGH
    expected_runtime: str          # e.g. O(N)
    memory_complexity: str         # e.g. O(1)
    validated_tags: List[str] = field(default_factory=list)


class MetadataClassifier:
    """Rigorous classifier that validates and enhances heuristic metadata."""
    
    def __init__(self, taxonomy: TaxonomyManager) -> None:
        self._tax = taxonomy
        self._logger = logging.getLogger(__name__)

    def classify(self, raw_metadata: Dict[str, str], raw_tags: List[str]) -> ClassifiedMetadata:
        """
        Translates noisy, unstructured data into strict canonical fields.
        """
        # 1. Resolve & Validate Tags across all Domains
        valid_tags = set()
        for t in raw_tags:
            # Aggressively check multiple domains to find a mathematical match
            for domain in ["algorithms", "data_structures", "patterns"]:
                resolved = self._tax.resolve_alias(domain, t)
                if self._tax.validate(domain, resolved):
                    valid_tags.add(resolved)
                    break # Found a canonical match
                    
        # 2. Heuristically Classify Core Domains based on validated tags
        algo_family = "Unknown"
        pattern = "None"
        for t in valid_tags:
            if self._tax.validate("algorithms", t):
                algo_family = t
            if self._tax.validate("patterns", t):
                pattern = t

        # 3. Assess Educational Difficulty
        raw_diff = raw_metadata.get("difficulty", "Medium").lower()
        if raw_diff in ["easy", "beginner"]:
            difficulty = "Easy"
            edu_level = "Beginner"
        elif raw_diff in ["hard", "expert", "advanced"]:
            difficulty = "Hard"
            edu_level = "Advanced"
        else:
            difficulty = "Medium"
            edu_level = "Intermediate"

        # 4. Predict Big-O Complexities
        time_c, space_c = self._predict_complexities(algo_family, pattern, list(valid_tags))
        
        # 5. Assess Visualization Complexity (Crucial for Video Rendering Engine)
        vis_complexity = self._assess_visualization(list(valid_tags))
        
        return ClassifiedMetadata(
            difficulty=difficulty,
            algorithm_family=algo_family,
            pattern=pattern,
            educational_level=edu_level,
            visualization_complexity=vis_complexity,
            expected_runtime=time_c,
            memory_complexity=space_c,
            validated_tags=list(valid_tags)
        )

    def _predict_complexities(self, algo: str, pattern: str, tags: List[str]) -> Tuple[str, str]:
        """
        Deterministic Rules engine mapping topics to Big-O notations.
        Provides the Script Generation LLM with a hardcoded baseline it cannot hallucinate away from.
        """
        time_complexity = "O(N)"
        space_complexity = "O(N)"
        
        # Common Absolute Overrides
        if algo == "binary_search":
            time_complexity = "O(log N)"
            space_complexity = "O(1)"
        elif pattern in ("two_pointers", "sliding_window"):
            time_complexity = "O(N)"
            space_complexity = "O(1)"
        elif pattern == "dynamic_programming" or "matrix" in tags:
            time_complexity = "O(N * M)"
            space_complexity = "O(N * M)"
        elif "tree" in tags or "graph" in tags:
            time_complexity = "O(V + E)"
            space_complexity = "O(V + E)"
        elif algo in ("merge_sort", "quick_sort"):
            time_complexity = "O(N log N)"
            space_complexity = "O(N)"
            
        return time_complexity, space_complexity

    def _assess_visualization(self, tags: List[str]) -> str:
        """
        Determines how much computational animation horsepower Manim will require.
        """
        # Complex node-link diagrams require heavy SVG compilation
        high_vis = {"graph", "tree", "dynamic_programming", "recursion", "trie"}
        
        # Grids and linked lists require moderate tracking
        med_vis = {"linked_list", "matrix", "heap"}
        
        for t in tags:
            if t in high_vis:
                return "HIGH"
                
        for t in tags:
            if t in med_vis:
                return "MEDIUM"
                
        # 1D Arrays, Strings, and Math are computationally cheap to render
        return "LOW" 
