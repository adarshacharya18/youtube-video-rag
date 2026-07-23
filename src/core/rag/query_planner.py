"""
RAG Query Planner.

Acts as the intelligent pre-processor for the Retrieval Engine.
Takes a raw user prompt, detects intent, rewrites/expands queries, 
and builds a comprehensive Execution Plan for the Retriever.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class RetrievalStrategy(Enum):
    """Execution modes for the Retrieval Engine."""
    EXACT_MATCH = "exact"
    SEMANTIC_BROAD = "semantic_broad"
    HYBRID_DEEP = "hybrid_deep"
    CODE_ONLY = "code_only"


@dataclass
class QueryPlan:
    """The strict execution blueprint passed to the Retrieval Engine."""
    original_query: str
    expanded_queries: List[str]
    detected_intent: str
    routing_hints: List[str]
    suggested_strategy: RetrievalStrategy
    extracted_topics: List[str] = field(default_factory=list)
    
    # If True, the Reranker will boot up the heavy MS-MARCO Cross-Encoder
    require_cross_encoder: bool = False


class QueryPlanner:
    """Intelligently analyzes prompts to generate optimal Retrieval plans."""
    
    def __init__(self) -> None:
        # Heuristic keywords for deterministic Intent extraction
        self._theory_keywords = {"explain", "how", "what", "theory", "concept", "define"}
        self._code_keywords = {"code", "implement", "python", "script", "solution", "leetcode"}
        self._perf_keywords = {"optimal", "complexity", "big o", "time", "space", "memory"}

    def plan(self, raw_query: str) -> QueryPlan:
        """
        Analyzes the query and compiles a strict Execution Plan.
        """
        q_lower = raw_query.lower()
        
        # 1. Intent Detection
        intent = self._detect_intent(q_lower)
        
        # 2. Strategy Selection
        strategy = self._select_strategy(intent, q_lower)
        
        # 3. Query Expansion / Rewriting
        expanded = self._expand_query(raw_query, intent, strategy)
        
        # 4. Routing Hints (Provides guardrails for the Knowledge Router)
        hints = self._generate_routing_hints(intent)
        
        # 5. Entity Extraction
        topics = self._extract_topics(q_lower)
        
        # If the user asks for highly complex optimal solutions, force the heavy Cross-Encoder
        require_cross = strategy == RetrievalStrategy.HYBRID_DEEP
        
        return QueryPlan(
            original_query=raw_query,
            expanded_queries=expanded,
            detected_intent=intent,
            routing_hints=hints,
            suggested_strategy=strategy,
            extracted_topics=topics,
            require_cross_encoder=require_cross
        )

    def _detect_intent(self, q_lower: str) -> str:
        """Determines the semantic goal of the query."""
        if any(kw in q_lower for kw in self._code_keywords):
            return "implementation"
        if any(kw in q_lower for kw in self._perf_keywords):
            return "optimization"
        return "explanation"

    def _select_strategy(self, intent: str, q_lower: str) -> RetrievalStrategy:
        """Determines how much compute power to spend on retrieval."""
        if intent == "implementation":
            if "optimal" in q_lower:
                return RetrievalStrategy.HYBRID_DEEP
            return RetrievalStrategy.CODE_ONLY
            
        if intent == "optimization":
            return RetrievalStrategy.HYBRID_DEEP
            
        return RetrievalStrategy.SEMANTIC_BROAD

    def _expand_query(self, original: str, intent: str, strategy: RetrievalStrategy) -> List[str]:
        """
        Generates Cosine-optimized variants of the query to cast a wider net.
        """
        expanded = []
        if intent == "implementation":
            expanded.append(f"{original} python optimal solution implementation")
        elif intent == "explanation":
            expanded.append(f"{original} technical academic theory explanation")
            
        if strategy == RetrievalStrategy.HYBRID_DEEP:
            expanded.append(f"{original} time and space complexity Big O analysis")
            
        return expanded

    def _generate_routing_hints(self, intent: str) -> List[str]:
        """Provides fallback namespaces for the Router."""
        if intent == "implementation":
            return ["problems", "patterns"]
        return ["algorithms", "data_structures"]

    def _extract_topics(self, q_lower: str) -> List[str]:
        """
        Naive heuristic entity extraction.
        In production, this would tie directly into Phase 10's TaxonomyManager aliases.
        """
        found = []
        famous_algos = ["dijkstra", "bfs", "dfs", "binary search", "two pointers", "sliding window"]
        for algo in famous_algos:
            if algo in q_lower:
                found.append(algo.replace(" ", "_"))
        return found
