# Phase 10 / 07: Metadata Classification

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/organization/metadata_classifier.py`](#2-source-code-srccoreorganizationmetadata_classifierpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

During Phase 09, the `MetadataEnricher` heuristically applied "best-guess" tags based on RegEx scanning. In Phase 10, the **Metadata Classifier** enforces absolute rigor. 

It acts as the final gatekeeper before data is embedded. It forces chaotic tags through the `TaxonomyManager` dictionary, permanently classifying a document into a strict `Algorithm Family` and `Pattern`. Most importantly, it executes a deterministic rules engine to output expected **Big-O Complexities** and **Visualization Complexity**, directly informing the downstream Video Rendering Engine how much animation horsepower will be required.

---

# 2. Source Code: `src/core/organization/metadata_classifier.py`

```python
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
```

---

# 3. Design Decisions

1. **Hallucination Prevention (`_predict_complexities`):** When generating a script for "Binary Search," an LLM might accidentally hallucinate the space complexity as `O(N)` depending on its context window length. By executing a deterministic Python rule-engine mapping `binary_search` strictly to `O(log N) / O(1)`, we provide the LLM with an absolute truth payload that overrides its internal weights.
2. **Video Render Optimization (`_assess_visualization`):** A video on `Arrays` takes about 20 minutes to compile in Manim. A video on recursive `Graphs` takes 2 hours to render due to complex SVG interpolation paths. By tagging a document with `HIGH` visualization complexity, the Phase 12 Workflow Engine can dynamically route Graph videos to a heavy GPU cloud-worker, while executing Array videos locally, saving massive cloud infrastructure costs.
3. **Cross-Domain Taxonomy Scanning:** Since LeetCode doesn't distinguish between an "Algorithm" (Binary Search) and a "Data Structure" (Hash Table) in its raw tags, the `classify` function recursively loops across all initialized `TaxonomyManager` domains until it finds a mathematical hit, cleanly splitting the tags into their correct logical buckets.
