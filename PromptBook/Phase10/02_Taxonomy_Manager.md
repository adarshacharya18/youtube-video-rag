# Phase 10 / 02: Taxonomy Manager

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/organization/taxonomy_manager.py`](#2-source-code-srccoreorganizationtaxonomy_managerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

The **Taxonomy Manager** enforces a rigorous, strictly-typed dictionary across the entire Knowledge Organization Platform. Without it, the system would rapidly degrade into tagging chaos (e.g., LeetCode returns `dynamic-programming`, Wikipedia returns `Dynamic Programming`, and a human types `DP`).

By explicitly defining Domains (`Algorithms`, `Data Structures`, `Companies`, `Difficulty`) and leveraging an Alias Resolution engine, the Taxonomy Manager intercepts raw, chaotic strings and forcefully maps them into Immutable Canonical IDs. It inherently integrates with the SQLite `MetadataStore` to persist the taxonomy schemas across application restarts.

---

# 2. Source Code: `src/core/organization/taxonomy_manager.py`

```python
"""
Taxonomy Manager.

Provides strict, version-controlled definitions for all platform knowledge domains.
Validates chaotic tags and maps aliases to their canonical definitions.
"""

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.core.metadata_store import MetadataStore
from src.core.storage_manager import StorageManager


@dataclass
class TaxonomyCategory:
    """Rigorous schema for a single taxonomy node."""
    id: str  # Canonical ID (e.g., "dynamic_programming")
    name: str # Display Name (e.g., "Dynamic Programming")
    description: str
    aliases: List[str] = field(default_factory=list) # e.g., ["dp", "memoization"]
    version: int = 1


class TaxonomyManager:
    """
    Manages CRUD, Validation, and Alias Mapping for all core Taxonomy Definitions.
    """
    def __init__(self, storage: StorageManager) -> None:
        self._storage = storage
        self._logger = logging.getLogger(__name__)
        
        # Pre-defined strict domains
        self._domains = [
            "algorithms", "data_structures", "patterns", 
            "difficulty", "topics", "companies", 
            "programming_languages", "categories"
        ]
        
        # In-Memory Cache for O(1) Lookups: { domain: { category_id: Category } }
        self._cache: Dict[str, Dict[str, TaxonomyCategory]] = {d: {} for d in self._domains}
        self._is_loaded = False

    async def initialize(self) -> None:
        """Bootstraps the taxonomy from SQLite into local RAM for ultra-fast validation."""
        if self._is_loaded:
            return
            
        store: MetadataStore = self._storage.get_store("metadata") # type: ignore
        for domain in self._domains:
            data, _ = await store.read("taxonomy", domain)
            if data:
                for cat_id, payload in data.items():
                    self._cache[domain][cat_id] = TaxonomyCategory(**payload)
                    
        self._is_loaded = True
        self._logger.info("Taxonomy Manager successfully booted and cached.")

    # ---------------------------------------------------------
    # Core CRUD Operations (With SQLite Persistence)
    # ---------------------------------------------------------
    async def create_category(
        self, 
        domain: str, 
        category_id: str, 
        name: str, 
        description: str, 
        aliases: Optional[List[str]] = None
    ) -> TaxonomyCategory:
        """Registers a new Canonical Category into a Domain."""
        if domain not in self._domains:
            raise ValueError(f"CRITICAL: Unknown domain '{domain}'. Must be one of {self._domains}")
        if category_id in self._cache[domain]:
            raise ValueError(f"Category '{category_id}' already physically exists in '{domain}'")
            
        cat = TaxonomyCategory(
            id=category_id, 
            name=name, 
            description=description, 
            aliases=aliases or []
        )
        self._cache[domain][category_id] = cat
        await self._persist_domain(domain)
        return cat

    async def get_category(self, domain: str, category_id: str) -> Optional[TaxonomyCategory]:
        """Retrieves a Category from the O(1) RAM cache."""
        return self._cache.get(domain, {}).get(category_id)
        
    async def update_category(self, domain: str, category_id: str, updates: Dict[str, Any]) -> TaxonomyCategory:
        """Safely mutates a Category and increments its internal Version."""
        cat = await self.get_category(domain, category_id)
        if not cat:
            raise ValueError(f"Category '{category_id}' not found in '{domain}'.")
            
        if "name" in updates: 
            cat.name = updates["name"]
        if "description" in updates: 
            cat.description = updates["description"]
        if "aliases" in updates: 
            cat.aliases = updates["aliases"]
            
        cat.version += 1
        await self._persist_domain(domain)
        return cat

    async def _persist_domain(self, domain: str) -> None:
        """Atomically locks and dumps the memory RAM map into the SQLite disk."""
        store: MetadataStore = self._storage.get_store("metadata") # type: ignore
        payload = {k: asdict(v) for k, v in self._cache[domain].items()}
        
        async with self._storage.transaction("metadata"):
            await store.save_metadata("taxonomy", domain, payload, tags=["system_taxonomy"])
            
    # ---------------------------------------------------------
    # Semantic Resolution & Validation
    # ---------------------------------------------------------
    def resolve_alias(self, domain: str, tag: str) -> str:
        """
        Translates a chaotic, unpredictable string (e.g., "dfs") into its 
        Strict Canonical ID (e.g., "depth_first_search").
        """
        tag_clean = tag.lower().strip()
        
        for cat_id, cat in self._cache.get(domain, {}).items():
            if cat.name.lower() == tag_clean or cat_id.lower() == tag_clean:
                return cat_id
            for alias in cat.aliases:
                if alias.lower() == tag_clean:
                    return cat_id
                    
        # If we cannot resolve it, return the raw tag and let the calling system decide
        return tag 

    def validate(self, domain: str, tag: str) -> bool:
        """Strict mathematical check: Does this tag belong in this domain?"""
        return tag in self._cache.get(domain, {})
```

---

# 3. Design Decisions

1. **Explicit Domain Sharding:** We do not allow random metadata keys. Everything is forcefully partitioned into strict Domains (`algorithms`, `patterns`, `companies`). This allows the SQLite engine to query *all* Algorithms without scanning through Company names, making UI dropdowns and filters instantaneous.
2. **Pre-Caching (`initialize`):** Because alias resolution might execute 500 times per second during a massive streaming ingestion, it would absolutely decimate the disk I/O if we queried SQLite every time. The `initialize` function loads all taxonomies into an `O(1)` Python Dictionary in RAM, effectively reducing resolution latency to zero.
3. **Canonical Translation Engine:** If the LLM generates the tag `"BFS"`, the engine's `resolve_alias` function aggressively corrects it to `breadth_first_search`. This prevents fragmented data islands where 10 problems are tagged `"BFS"` and 10 are tagged `"Breadth-First"`, ensuring perfect data hygiene.
