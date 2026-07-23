# Phase 11 / 07: Semantic Retrieval Engine

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/rag/retriever.py`](#2-source-code-srccoreragretrieverpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

If the **Knowledge Router** is the Traffic Controller, the **Retrieval Engine** is the racecar.

It is responsible for taking a downstream request (e.g., "Explain how Dijkstra works"), expanding it syntactically, executing massive parallel sweeps across multiple Vector Database Namespaces concurrently, and then aggressively deduplicating and compressing the results to prevent the downstream Script Generation LLM from running out of Token Context limits.

---

# 2. Source Code: `src/core/rag/retriever.py`

```python
"""
RAG Semantic Retrieval Engine.

Executes high-speed parallel retrieval across Vector Databases.
Handles Query Rewriting, Deduplication, and Context Compression.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from src.core.rag.embedder import GeminiEmbedder
from src.core.rag.router import KnowledgeRouter, RouteDecision
from src.plugins.vector_store_chroma import ChromaVectorStore


@dataclass
class RetrievedContext:
    """Strictly typed telemetry for the final retrieval payload."""
    chunk_id: str
    score: float
    metadata: Dict[str, Any]


class RetrievalEngine:
    """Executes distributed semantic search and applies ranking strategies."""
    
    def __init__(
        self, 
        embedder: GeminiEmbedder, 
        vector_store: ChromaVectorStore,
        router: KnowledgeRouter
    ) -> None:
        self._embedder = embedder
        self._store = vector_store
        self._router = router
        self._logger = logging.getLogger(__name__)

    async def retrieve(
        self, 
        query: str, 
        intent: str, 
        top_k: int = 5,
        topic: str = None
    ) -> List[RetrievedContext]:
        """
        The Main Retrieval Pipeline: 
        Query Rewrite -> Rout -> Embed -> Parallel Search -> Merge -> Deduplicate
        """
        self._logger.info(f"Executing Retrieval Pipeline for query: '{query[:30]}...'")
        
        # 1. Query Rewriting (Expands query context to catch more vectors)
        expanded_queries = self._rewrite_query(query)
        
        # 2. Knowledge Routing (Where to search & what to filter)
        route: RouteDecision = self._router.route_query(
            query=query, 
            intent=intent, 
            topic=topic
        )
        
        namespaces_to_search = route.target_namespaces
        if not namespaces_to_search:
            self._logger.warning("Primary route failed. Falling back to secondary namespaces.")
            namespaces_to_search = route.fallback_namespaces
            
        if not namespaces_to_search:
            self._logger.warning("Router yielded no valid namespaces. Aborting retrieval.")
            return []
            
        # 3. Embed the queries (Leveraging the Embedder Cache natively)
        # Combine the original query + all syntactic variants
        all_queries = [query] + expanded_queries
        query_vectors = await self._embedder.embed_batch(all_queries)
        
        # 4. Parallel Retrieval (Massive Scatter-Gather)
        raw_results = await self._parallel_search(
            namespaces=namespaces_to_search,
            query_vectors=query_vectors,
            top_k=top_k,
            filters=route.metadata_filters
        )
        
        # 5. Merge, Deduplicate, and Compress
        final_results = self._merge_and_deduplicate(raw_results, top_k)
        
        self._logger.info(f"Retrieval complete. Yielded {len(final_results)} highly relevant chunks.")
        return final_results

    def _rewrite_query(self, query: str) -> List[str]:
        """
        Expands the user query to catch semantic variants.
        In a physical production LLM deployment, this would prompt a cheap model (e.g. GPT-4o-mini).
        For this pipeline phase, we use rapid heuristic string mutation.
        """
        expanded = []
        q_lower = query.lower()
        
        # Heuristic Semantic Expansion
        if "how" in q_lower or "explain" in q_lower:
            expanded.append(query + " technical explanation and academic theory")
        if "code" in q_lower or "implement" in q_lower:
            expanded.append(query + " python optimal algorithm implementation")
        if "optimal" in q_lower or "complexity" in q_lower:
            expanded.append(query + " time and space big O notation complexity limits")
            
        return expanded

    async def _parallel_search(
        self, 
        namespaces: List[str], 
        query_vectors: List[List[float]], 
        top_k: int,
        filters: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Scatters the query vectors across multiple Vector DB Namespaces concurrently.
        """
        tasks = []
        
        # If we have 2 Namespaces and 3 Query Variants, this spawns 6 parallel searches instantly.
        for ns in namespaces:
            for vector in query_vectors:
                tasks.append(self._store.similarity_search(
                    namespace=ns,
                    query_vector=vector,
                    top_k=top_k,
                    filter=filters if filters else None
                ))
                
        # Gather all physical DB queries simultaneously without blocking
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten the list of lists
        flattened = []
        for res in results:
            if not isinstance(res, Exception):
                flattened.extend(res)
            else:
                self._logger.error(f"A parallel search task failed mid-flight: {res}")
                
        return flattened

    def _merge_and_deduplicate(self, raw_results: List[Dict[str, Any]], top_k: int) -> List[RetrievedContext]:
        """
        Merges results from multiple scattered queries/namespaces.
        Resolves duplicate chunk IDs by taking the absolute highest semantic score.
        """
        merged_map: Dict[str, RetrievedContext] = {}
        
        for item in raw_results:
            chunk_id = item["id"]
            score = item["score"]
            
            # If we've seen this exact physical chunk before, keep the highest similarity score
            if chunk_id in merged_map:
                if score > merged_map[chunk_id].score:
                    merged_map[chunk_id].score = score
            else:
                merged_map[chunk_id] = RetrievedContext(
                    chunk_id=chunk_id,
                    score=score,
                    metadata=item.get("metadata", {})
                )
                
        # Sort by mathematical Cosine Similarity descending (Highest relevance first)
        sorted_results = sorted(merged_map.values(), key=lambda x: x.score, reverse=True)
        
        # Compression Strategy: Hard Truncate to top_k to avoid blowing out Downstream LLM Context Windows
        return sorted_results[:top_k]
```

---

# 3. Design Decisions

1. **Syntactic Query Rewriting (`_rewrite_query`):** Standard Vector Search often suffers from the "Vocabulary Mismatch Problem." If a downstream script generator asks for "How to do Dijkstra in Python," but the Vector Store chunk says "Optimal Shortest Path Implementation," Cosine Similarity might miss it. By proactively generating semantic variants (e.g., appending "optimal algorithm implementation"), we cast a wider mathematical net without burning expensive LLM API tokens.
2. **Scatter-Gather Parallelism (`_parallel_search`):** If the Router decides we must search both the `algorithms` namespace and the `data_structures` namespace using 3 different query variants, executing that sequentially would take `6 * 100ms = 600ms`. By utilizing `asyncio.gather`, we execute all 6 physical ChromaDB queries concurrently, dropping the total latency to `~120ms`.
3. **Idempotent Merge & Deduplication (`_merge_and_deduplicate`):** Because we executed 6 parallel searches, there is a very high probability that `chunk_A` was returned by two different queries with two different scores. If we simply appended the results, we would send duplicate context to the Script Generator (wasting context window). The `merged_map` perfectly deduplicates the physical `chunk_id` while natively preserving the highest mathematically returned `score`.
