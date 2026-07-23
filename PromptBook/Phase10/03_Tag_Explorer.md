# Phase 10 / 03: Tag Explorer

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/organization/tag_explorer.py`](#2-source-code-srccoreorganizationtag_explorerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

While the `TaxonomyManager` enforces strict, dictionary-style classification, the **Tag Explorer** brings that taxonomy to life. It builds an internal Knowledge Graph (a mathematical Directed Graph) of every single tag in the system.

By actively tracking *usage statistics* and calculating *co-occurrences*, the Explorer can autonomously deduce that `Dynamic Programming` is highly related to `Recursion` and `Memoization` because those three tags appear together frequently. It exposes robust APIs for searching, domain-filtering, and intelligent tagging recommendations, crucial for generating rich YouTube SEO tags and semantic links.

---

# 2. Source Code: `src/core/organization/tag_explorer.py`

```python
"""
Tag Explorer Engine.

Analyzes hierarchical tags, manages relationships, and provides search, filtering, 
and heuristic recommendations for the Knowledge Graph.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from src.core.organization.taxonomy_manager import TaxonomyManager


@dataclass
class TagNode:
    """A single node within the mathematical Tag Graph."""
    id: str
    domain: str
    parent_id: Optional[str] = None
    children: Set[str] = field(default_factory=set)
    related: Set[str] = field(default_factory=set)
    usage_count: int = 0


class TagExplorer:
    """
    Knowledge Graph adapter for hierarchical tag analysis.
    """
    
    def __init__(self, taxonomy_manager: TaxonomyManager) -> None:
        self._tax = taxonomy_manager
        self._graph: Dict[str, TagNode] = {}
        self._logger = logging.getLogger(__name__)

    def add_tag(self, tag_id: str, domain: str, parent_id: Optional[str] = None) -> None:
        """Injects a hierarchical tag into the directed graph."""
        if tag_id not in self._graph:
            self._graph[tag_id] = TagNode(id=tag_id, domain=domain, parent_id=parent_id)
            
        if parent_id and parent_id in self._graph:
            self._graph[parent_id].children.add(tag_id)

    def record_usage(self, tags: List[str]) -> None:
        """
        Increments statistics and automatically links co-occurring tags.
        e.g., If [DP, Recursion] are passed, an undirected edge is drawn between them.
        """
        valid_tags = [t for t in tags if t in self._graph]
        
        for t in valid_tags:
            self._graph[t].usage_count += 1
            # Link semantic co-occurrences (O(N^2) for small N)
            for other in valid_tags:
                if t != other:
                    self._graph[t].related.add(other)

    def search(self, query: str) -> List[str]:
        """
        Sub-string matching on Canonical IDs, Display Names, and Aliases.
        e.g., search("memo") -> returns ["dynamic_programming"]
        """
        query_lower = query.lower().strip()
        results: Set[str] = set()
        
        for tag_id, node in self._graph.items():
            # Check the raw ID
            if query_lower in tag_id.lower():
                results.add(tag_id)
                continue
                
            # Cross-reference with the strict Taxonomy Dictionary
            cat = self._tax._cache.get(node.domain, {}).get(tag_id)
            if cat:
                if query_lower in cat.name.lower():
                    results.add(tag_id)
                elif any(query_lower in alias.lower() for alias in cat.aliases):
                    results.add(tag_id)
                    
        return list(results)

    def filter_by_domain(self, domain: str) -> List[str]:
        """Returns all tags in a given domain (e.g., all 'algorithms')."""
        return [t.id for t in self._graph.values() if t.domain == domain]

    def recommend(self, current_tags: List[str], limit: int = 5) -> List[str]:
        """
        Intelligent Recommendation Engine.
        Analyzes the co-occurrence edges of the input tags to recommend related concepts.
        """
        recommendations: Dict[str, int] = {}
        
        for tag in current_tags:
            node = self._graph.get(tag)
            if node:
                # Add weight to related tags based on global usage popularity
                for rel in node.related:
                    if rel not in current_tags:
                        recommendations[rel] = recommendations.get(rel, 0) + self._graph[rel].usage_count
                        
        # Sort aggressively by usage score (Descending)
        sorted_recs = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)
        return [k for k, v in sorted_recs[:limit]]

    def get_statistics(self) -> Dict[str, Any]:
        """Returns aggregate usage data for global analytics and UI rendering."""
        domains: Dict[str, int] = {}
        
        for node in self._graph.values():
            domains[node.domain] = domains.get(node.domain, 0) + node.usage_count
            
        return {
            "total_tags": len(self._graph),
            "usage_by_domain": domains
        }
```

---

# 3. Design Decisions

1. **Undirected Co-Occurrence Edges (`record_usage`):** An LLM doesn't natively know that "Depth-First Search" and "Trees" go hand in hand. However, by running `record_usage(["dfs", "tree"])` every time a LeetCode problem is ingested, the Tag Explorer organically draws mathematical edges between them. Later, when the `ScriptGeneration` Node asks for recommendations, it effortlessly returns highly accurate semantic links without wasting any LLM API calls.
2. **Deep Taxonomy Cross-Referencing (`search`):** A generic database `LIKE %query%` search on tags would fail if the user searches for `"memo"` but the database tag is strictly `"dynamic_programming"`. Because the `TagExplorer` holds a reference to the `TaxonomyManager`, the `search` function natively scans the hidden `aliases` array (e.g., `["dp", "memoization"]`), guaranteeing perfect recall.
3. **Popularity-Weighted Recommendations (`recommend`):** If a user provides `["recursion"]`, the engine might see 50 related tags. Rather than returning random elements, the engine weights the recommendations by global `usage_count`, ensuring the most structurally important concepts are pushed to the top of the curriculum.
