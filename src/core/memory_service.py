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
