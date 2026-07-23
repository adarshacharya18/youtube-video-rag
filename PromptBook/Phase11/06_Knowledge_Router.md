# Phase 11 / 06: Knowledge Router

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/rag/router.py`](#2-source-code-srccoreragrouterpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

When the downstream Script Generation AI says "I need information about Dijkstra," it should **not** search the entire Vector Database. If it searches the global DB, it might accidentally retrieve the Python solution to *LeetCode 743: Network Delay Time* rather than the theoretical explanation of the Algorithm itself, confusing the video script.

The **Knowledge Router** acts as an intelligent traffic controller. By intercepting downstream queries and analyzing their `Intent` (e.g., *Theory* vs *Code*), it dynamically selects specific isolated ChromaDB Namespaces (Collections) to query. It also compiles deterministic Metadata Filters (e.g., `WHERE educational_level = 'Beginner'`) to physically constrain the Vector Engine's mathematical search space.

---

# 2. Source Code: `src/core/rag/router.py`

```python
"""
Knowledge Router.

Analyzes incoming downstream retrieval queries (from the Script Generator) 
and dynamically routes them to the correct semantic namespaces (Collections) 
in the Vector Database, along with precise metadata filters.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RouteDecision:
    """Strictly typed telemetry for the physical search boundaries."""
    target_namespaces: List[str]
    metadata_filters: Dict[str, str]
    confidence_score: float
    fallback_namespaces: List[str] = field(default_factory=list)


class KnowledgeRouter:
    """Intelligently routes queries to isolated Knowledge Bases."""
    
    def __init__(self) -> None:
        # We explicitly define our available logical collections (Phase 10 domains)
        self._available_namespaces = {
            "algorithms", 
            "data_structures", 
            "patterns", 
            "problems"
        }
        
    def route_query(
        self, 
        query: str, 
        intent: str, 
        topic: Optional[str] = None,
        educational_level: Optional[str] = None,
        language: Optional[str] = None
    ) -> RouteDecision:
        """
        Determines the optimal Vector DB namespaces and `WHERE` filters to execute 
        the search against, preventing irrelevant document contamination.
        """
        query_lower = query.lower()
        intent_lower = intent.lower()
        
        target_namespaces = []
        fallback_namespaces = []
        filters = {}
        confidence = 1.0
        
        # 1. Intent-Based Routing
        if "solution" in intent_lower or "code" in intent_lower or "leetcode" in query_lower:
            # The LLM wants physical code implementation
            target_namespaces.append("problems")
            fallback_namespaces.extend(["patterns", "algorithms"])
            confidence = 0.95
            
        elif "explain" in intent_lower or "theory" in intent_lower or "how" in query_lower:
            # The LLM wants theoretical Computer Science concepts
            if any(kw in query_lower for kw in ["tree", "graph", "list", "array", "map"]):
                target_namespaces.append("data_structures")
                fallback_namespaces.append("algorithms")
            else:
                target_namespaces.append("algorithms")
                fallback_namespaces.append("patterns")
            confidence = 0.85
            
        elif "pattern" in intent_lower or "recognize" in intent_lower:
            # The LLM is writing a video about identifying a problem type
            target_namespaces.append("patterns")
            fallback_namespaces.append("problems")
            confidence = 0.90
            
        else:
            # Generic fallback: Search everything if intent is extremely ambiguous
            target_namespaces = list(self._available_namespaces)
            confidence = 0.40
            
        # 2. Topic Filtering (Direct Vector Database 'WHERE' constraints)
        if topic:
            # If we know exactly what we are talking about, lock the DB query to that tag
            filters["tags"] = topic.lower()
            
        # 3. Educational Level Filtering
        if educational_level:
            # Prevent retrieving 'Hard' O(1) complex optimizations for Beginner scripts
            if educational_level.lower() == "beginner":
                filters["educational_level"] = "Beginner"
            elif educational_level.lower() == "advanced":
                filters["educational_level"] = "Advanced"
                
        # 4. Programming Language Filter
        if language and "problems" in target_namespaces:
            filters["language"] = language.lower()
            
        return RouteDecision(
            target_namespaces=target_namespaces,
            metadata_filters=filters,
            confidence_score=confidence,
            fallback_namespaces=fallback_namespaces
        )
```

---

# 3. Design Decisions

1. **Namespace Isolation:** Vector Similarity Search is mathematically flawed when dealing with vastly different types of documents. The semantic vectors for the *theory* of BFS are dangerously close to the semantic vectors of a LeetCode BFS *solution*. By enforcing `target_namespaces`, the Router forces ChromaDB to completely ignore LeetCode problems when generating a script about Theory, ensuring absolute conceptual purity in the video scripts.
2. **Deterministic DB Constraints (`metadata_filters`):** Rather than letting the LLM read 10 documents and figure out which ones are appropriate for Beginners, the Router injects `WHERE educational_level = 'Beginner'` directly into the physical database query. This ensures the downstream LLM *only* sees Beginner content, physically preventing it from accidentally writing overly-complex scripts that alienate the YouTube audience.
3. **Fallback Gracefulness (`fallback_namespaces`):** If the Router specifies `data_structures` but ChromaDB returns zero results (perhaps the topic hasn't been scraped yet), the downstream Retrieval Engine can seamlessly catch the empty array, read `fallback_namespaces`, and transparently query the `algorithms` namespace without crashing the video pipeline.
