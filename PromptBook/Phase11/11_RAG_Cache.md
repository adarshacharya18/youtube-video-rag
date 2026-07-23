# Phase 11 / 11: RAG Unified Cache

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/rag/cache.py`](#2-source-code-srccoreragcachepy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

Vector Similarity Search and LLM Embeddings are mathematically expensive and physically slow. If a user asks "Explain Dijkstra" on Monday, and another user asks the exact same thing on Tuesday, recalculating the embeddings, executing the ChromaDB scatter-gather, and rebuilding the prompt context wastes precious system resources.

The **RAG Unified Cache** is a strict, TTL-backed memory layer. It sits in front of the Embedder, the Retriever, and the Context Builder. It implements deterministic JSON hashing to guarantee cache hits on identical queries, while supporting localized Namespace Invalidation to prevent serving stale data if the underlying Vector DB is updated.

---

# 2. Source Code: `src/core/rag/cache.py`

```python
"""
RAG Unified Caching Layer.

Provides high-speed TTL-based caching for Embeddings, Retrieval Queries,
and Compiled Contexts. Prevents redundant LLM API billing and DB I/O.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CacheEntry:
    """Strictly typed payload for memory storage."""
    payload: Any
    expires_at: float
    namespace: str


class RAGCache:
    """In-memory TTL cache for RAG operations."""
    
    def __init__(self, default_ttl_seconds: int = 3600) -> None:
        # Physical dictionary acting as the KV Store (can be swapped for Redis later)
        self._cache: Dict[str, CacheEntry] = {}
        # Default expiration (1 hour)
        self._default_ttl = default_ttl_seconds
        self._logger = logging.getLogger(__name__)
        
        # Grafana Telemetry Counters
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _generate_key(self, namespace: str, prefix: str, data: Any) -> str:
        """
        Deterministically hashes complex data structures (like Query parameter dicts) 
        into flat, collision-resistant string keys.
        """
        # If the input is a complex dict (e.g., QueryPlan), serialize it deterministically
        if isinstance(data, (dict, list)):
            raw_str = json.dumps(data, sort_keys=True)
        else:
            raw_str = str(data)
            
        hashed = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
        return f"{namespace}:{prefix}:{hashed}"

    def get(self, namespace: str, prefix: str, data: Any) -> Optional[Any]:
        """
        Retrieves an item from the cache, strictly respecting TTL expiration limits.
        """
        key = self._generate_key(namespace, prefix, data)
        
        if key not in self._cache:
            self._misses += 1
            return None
            
        entry = self._cache[key]
        
        # 1. Enforce TTL expiration
        if time.time() > entry.expires_at:
            self._logger.debug(f"Cache key {key} physically expired. Evicting from memory.")
            del self._cache[key]
            self._evictions += 1
            self._misses += 1
            return None
            
        # 2. Cache Hit
        self._hits += 1
        return entry.payload

    def set(self, namespace: str, prefix: str, data: Any, payload: Any, ttl_override: Optional[int] = None) -> None:
        """
        Stores an item in the cache memory pool.
        """
        key = self._generate_key(namespace, prefix, data)
        ttl = ttl_override if ttl_override is not None else self._default_ttl
        
        self._cache[key] = CacheEntry(
            payload=payload,
            expires_at=time.time() + ttl,
            namespace=namespace
        )

    def invalidate_namespace(self, namespace: str) -> int:
        """
        Clears all cached items belonging to a specific DB namespace.
        Critical during Document Rollbacks (Phase 11/02) to ensure the Retriever 
        doesn't serve 'ghost' chunks that were physically deleted from ChromaDB.
        """
        # Find all keys matching the target namespace
        keys_to_delete = [k for k, v in self._cache.items() if v.namespace == namespace]
        
        for k in keys_to_delete:
            del self._cache[k]
            
        self._logger.info(f"Invalidated {len(keys_to_delete)} cache entries for namespace '{namespace}'.")
        return len(keys_to_delete)

    def get_metrics(self) -> Dict[str, Any]:
        """Returns standard cache telemetry for the Prometheus monitor daemon."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total) * 100 if total > 0 else 0.0
        
        return {
            "total_keys": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate_percent": round(hit_rate, 2)
        }
```

---

# 3. Design Decisions

1. **Deterministic Serialization (`_generate_key`):** Sometimes the caller passes a simple string (`query="Dijkstra"`). Other times, they pass a complex `QueryPlan` dictionary with nested arrays. If we simply used `str(dict)`, Python doesn't guarantee key ordering, meaning the same dictionary could generate two different string hashes. By explicitly using `json.dumps(data, sort_keys=True)`, we guarantee absolute deterministic collision-resistance across complex objects.
2. **Namespace Invalidation (`invalidate_namespace`):** In Phase 11/02 (IndexingEngine), we implemented `_rollback_document` to physically delete corrupted vectors from ChromaDB. If the Cache didn't know about this, the `RetrievalEngine` would return *ghost* chunks from memory that no longer exist in the DB. By invoking `cache.invalidate_namespace("algorithms")`, the pipeline instantly purges the memory pool, ensuring consistency.
3. **Telemetry Metrics (`get_metrics`):** Production RAG systems require observability. If the `hit_rate_percent` drops below 10%, it mathematically proves our TTL is too short, or our users are generating completely unique queries. This exact dictionary format can be scraped natively by the `OrganizationMonitor` daemon built in Phase 10.
