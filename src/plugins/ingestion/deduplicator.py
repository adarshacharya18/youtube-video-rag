"""
Knowledge Deduplication Engine.

Mathematically prevents the Pipeline from re-ingesting duplicate problems or outdated schemas.
Supports SHA-256 Hashing, Slug Matching, and Conflict Merge Strategies.
"""

import hashlib
import json
import logging
from enum import Enum
from typing import Any, Dict, Tuple

from src.core.memory_service import MemoryService
from src.core.metadata_store import MetadataStore
from src.plugins.ingestion.normalizer import NormalizedDocument


class DeduplicationAction(Enum):
    """The authoritative instruction returned to the Orchestrator."""
    INSERT = "INSERT"     # Completely new document
    UPDATE = "UPDATE"     # Document exists but content/metadata mathematically drifted
    SKIP = "SKIP"         # Exact duplicate, halt the ingestion pipeline
    CONFLICT = "CONFLICT" # Unresolvable version clash (Requires human intervention)


class DeduplicationEngine:
    """
    Evaluates incoming NormalizedDocuments against the Persistence Layer.
    """
    
    def __init__(self, memory_service: MemoryService) -> None:
        self._memory = memory_service
        self._logger = logging.getLogger(__name__)

    def _generate_content_hash(self, doc: NormalizedDocument) -> str:
        """
        Generates a deterministic SHA-256 hash of the pure Markdown text.
        Ignores metadata, focusing entirely on the pedagogical content.
        """
        raw_bytes = doc.markdown.encode('utf-8')
        return hashlib.sha256(raw_bytes).hexdigest()

    async def evaluate(self, doc: NormalizedDocument) -> Tuple[DeduplicationAction, NormalizedDocument]:
        """
        Evaluates the incoming document against existing knowledge stores.
        Returns the required DB Action and the finalized Document (post-merge).
        """
        # Direct lookup via Slug Matching using the high-speed MetadataStore
        # We safely bypass the Memory facade here because Deduplication is an Infrastructure concern
        store: MetadataStore = self._memory._storage.get_store(self._memory._metadata_name) # type: ignore
        existing_data, _ = await store.read("knowledge", doc.id)
        
        new_hash = self._generate_content_hash(doc)
        
        # 1. New Document (Insert Path)
        if not existing_data:
            # Inject system telemetry into metadata for future comparisons
            new_meta = dict(doc.metadata)
            new_meta["_content_hash"] = new_hash
            new_meta["_version"] = 1
            
            final_doc = NormalizedDocument(
                id=doc.id,
                title=doc.title,
                markdown=doc.markdown,
                metadata=new_meta,
                tags=doc.tags
            )
            return DeduplicationAction.INSERT, final_doc

        # 2. Existing Document found. Extract stored telemetry.
        old_hash = existing_data.get("_content_hash", "")
        old_version = existing_data.get("_version", 1)
        
        # 3. Exact Content Duplicate Check (Hash Match)
        if old_hash == new_hash:
            # The Markdown matches exactly. But did LeetCode change the difficulty?
            if self._has_metadata_drift(doc.metadata, existing_data):
                self._logger.info(f"Metadata Drift detected on {doc.id}. Merging updates.")
                merged_doc = self._merge_documents(doc, existing_data, new_hash, old_version + 1)
                return DeduplicationAction.UPDATE, merged_doc
            
            self._logger.debug(f"Document '{doc.id}' is an exact hash duplicate. Bailing out.")
            return DeduplicationAction.SKIP, doc

        # 4. Content Drift Check (Hash Mismatch)
        # e.g., LeetCode added new test cases or reworded the problem description
        self._logger.info(f"Markdown Content Drift detected on {doc.id}. Executing UP-Migration.")
        merged_doc = self._merge_documents(doc, existing_data, new_hash, old_version + 1)
        return DeduplicationAction.UPDATE, merged_doc

    def _has_metadata_drift(self, new_meta: Dict[str, Any], old_meta: Dict[str, Any]) -> bool:
        """
        Compares critical semantic metadata to detect upstream changes 
        even if the raw Markdown text hasn't changed.
        """
        # Check core scalar fields
        if new_meta.get("difficulty") != old_meta.get("difficulty"):
            return True
            
        # Check the deterministic Enriched JSON blob
        new_enriched = new_meta.get("enriched", {})
        old_enriched = old_meta.get("enriched", {})
        
        # O(N) Deep Dictionary Equality Check
        if json.dumps(new_enriched, sort_keys=True) != json.dumps(old_enriched, sort_keys=True):
            return True
            
        return False

    def _merge_documents(
        self, 
        new_doc: NormalizedDocument, 
        old_meta: Dict[str, Any], 
        new_hash: str, 
        new_version: int
    ) -> NormalizedDocument:
        """
        Merge Strategy: 'Latest Upstream Wins' for content, but strictly preserves 
        custom tags and override configurations added manually by human admins.
        """
        merged_meta = dict(new_doc.metadata)
        
        # Safely persist human-added custom tags across automated updates
        custom_tags = old_meta.get("_custom_tags", [])
        if custom_tags:
            merged_meta["_custom_tags"] = custom_tags
            
        merged_meta["_content_hash"] = new_hash
        merged_meta["_version"] = new_version
        
        # Merge all automated tags with human tags flawlessly
        final_tags = list(set(new_doc.tags + custom_tags))
        
        return NormalizedDocument(
            id=new_doc.id,
            title=new_doc.title,
            markdown=new_doc.markdown,
            metadata=merged_meta,
            tags=final_tags
        )
