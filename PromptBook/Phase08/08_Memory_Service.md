# Phase 08 / 08: Memory Service Implementation

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/memory_service.py`](#2-source-code-srccorememory_servicepy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Memory Service**. 

In strict adherence to the Single Responsibility Principle, Subagents and Orchestrators should *never* write SQL queries or interact directly with Database Repositories. The `MemoryService` acts as the definitive Business Logic facade. It abstracts away the `StateStore`, `MetadataStore`, and `EventStore`, synthesizing their raw data into usable Contexts (e.g., Session Memory, Execution History, Knowledge References) for the upstream AI pipelines.

This perfectly separates the physical Storage Concerns (SQLite I/O, Unit of Works) from the Retrieval Logic (Contextual aggregation and heuristic filtering).

---

# 2. Source Code: `src/core/memory_service.py`

```python
"""
Memory Service.

High-level business logic layer that aggregates disparate persistence stores 
(State, Metadata, Event, Vector) into a unified Memory context for AI Agents and Pipelines.
Separates storage concerns from retrieval heuristics.
"""

import logging
from typing import Any, Optional

from src.core.event_store import EventStore
from src.core.metadata_store import MetadataStore
from src.core.state_store import StateStore
from src.core.storage_manager import StorageManager


class MemoryService:
    """
    Unified Façade for Agentic and Pipeline Memory contexts.
    """

    def __init__(
        self, 
        storage_manager: StorageManager,
        state_store_name: str = "core_state",
        metadata_store_name: str = "metadata",
        event_store_name: str = "event_bus"
    ) -> None:
        self._storage = storage_manager
        self._state_name = state_store_name
        self._metadata_name = metadata_store_name
        self._event_name = event_store_name
        self._logger = logging.getLogger(__name__)

    # ---------------------------------------------------------
    # Pipeline & Session Memory (StateStore)
    # ---------------------------------------------------------
    async def get_session_memory(self, session_id: str) -> dict[str, Any]:
        """Retrieves active user or agent Session state variables."""
        store: StateStore = self._storage.get_store(self._state_name) # type: ignore
        data, _ = await store.read("session", session_id)
        return data or {}

    async def update_session_memory(self, session_id: str, updates: dict[str, Any]) -> None:
        """
        Merges new data into Session memory safely using Optimistic Locking.
        """
        store: StateStore = self._storage.get_store(self._state_name) # type: ignore
        
        # Enforce UoW lock to prevent concurrent plugins from overwriting the memory
        async with self._storage.transaction(self._state_name):
            current, version = await store.read("session", session_id)
            current = current or {}
            current.update(updates)
            await store.write("session", session_id, current, expected_version=version)

    async def get_pipeline_memory(self, pipeline_id: str) -> dict[str, Any]:
        """Retrieves pipeline-scoped execution variables for downstream plugins."""
        store: StateStore = self._storage.get_store(self._state_name) # type: ignore
        data, _ = await store.read("pipeline", pipeline_id)
        return data or {}

    # ---------------------------------------------------------
    # Knowledge References (MetadataStore)
    # ---------------------------------------------------------
    async def get_knowledge_references(self) -> list[dict[str, Any]]:
        """
        Retrieves static domain knowledge (e.g., LeetCode patterns, System Prompts).
        """
        store: MetadataStore = self._storage.get_store(self._metadata_name) # type: ignore
        all_knowledge = await store.query_by_category("knowledge")
        return list(all_knowledge.values())
        
    async def store_knowledge_reference(
        self, 
        entity_id: str, 
        data: dict[str, Any], 
        tags: Optional[list[str]] = None
    ) -> None:
        """Persists a new piece of static domain knowledge into the registry."""
        store: MetadataStore = self._storage.get_store(self._metadata_name) # type: ignore
        async with self._storage.transaction(self._metadata_name):
            await store.save_metadata("knowledge", entity_id, data, tags)

    # ---------------------------------------------------------
    # Execution History (EventStore)
    # ---------------------------------------------------------
    async def get_execution_history(self, correlation_id: str) -> list[dict[str, Any]]:
        """
        Reconstructs the precise chronological timeline of a subagent or pipeline.
        Transforms raw technical Events into readable Agentic History.
        """
        store: EventStore = self._storage.get_store(self._event_name) # type: ignore
        
        # Uses the high-speed SQLite `idx_event_correlation` index
        events = await store.query_events(correlation_id=correlation_id)
        
        history: list[dict[str, Any]] = []
        for e in events:
            history.append({
                "timestamp": e.timestamp,
                "topic": e.topic,
                "payload": e.payload
            })
        return history

    # ---------------------------------------------------------
    # Future Conversational & Long-Term Memory (VectorStore Stub)
    # ---------------------------------------------------------
    async def search_long_term_memory(self, query_text: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        [STUB] Future Semantic RAG Search.
        Will interface with a VectorStore (ChromaDB) to retrieve Agentic episodic memories.
        """
        self._logger.warning("Long-Term Memory is stubbed pending VectorStore implementation in Phase 10.")
        return []
```

---

# 3. Design Decisions

1. **Façade Pattern (Separation of Concerns):** A Subagent trying to figure out what happened in its previous iteration shouldn't have to write a SQL `SELECT` statement joining three tables. It just calls `get_execution_history(correlation_id)`. The Memory Service seamlessly routes this to the underlying `EventStore`, utilizing the SQLite Indexes we built in previous files.
2. **Safe Session Updates:** The `update_session_memory()` function elegantly combines the StorageManager's `transaction` UoW with the StateStore's Optimistic Locking (`expected_version`). This means if two Plugins run in parallel via `asyncio.gather()` and both try to update the Session Memory simultaneously, one will safely succeed and the other will Roll Back, mathematically eliminating silent data-loss anomalies.
3. **Future-Proof RAG Stub:** The `search_long_term_memory()` method acts as the defined entrypoint for the upcoming Phase 10 Semantic Retrieval Engine. When we integrate Vector Embeddings, the Business Logic interface will not change, ensuring backward compatibility across the entire Orchestration layer.
