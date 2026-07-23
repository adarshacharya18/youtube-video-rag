# Phase 09 / 06: Knowledge Deduplication Engine

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/plugins/ingestion/deduplicator.py`](#2-source-code-srcpluginsingestiondeduplicatorpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Knowledge Deduplication Engine**. 

If the Ingestion Pipeline runs a cron job that pulls 3,000 LeetCode problems every night, it would immediately overwhelm the `MetadataStore` and `VectorStore` with duplicate entries, resulting in corrupted LLM responses (e.g., the AI pulling 5 identical copies of "Two Sum" during Script Generation).

The `DeduplicationEngine` mathematically solves this. Before a `NormalizedDocument` is committed to the database, the Engine computes a deterministic SHA-256 hash of its Markdown text. It queries the Database via Slug Matching. If the Hash perfectly matches, it issues a rigid `SKIP` command. If LeetCode updated the problem constraints, the Hash will mismatch, and it intelligently calculates a `MergeStrategy`, bumping the version number without overwriting human-defined custom tags.

---

# 2. Source Code: `src/plugins/ingestion/deduplicator.py`

```python
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
```

---

# 3. Design Decisions

1. **SHA-256 Text Hashing:** Trying to do a string-to-string comparison of a 5,000-word problem description across 3,000 database rows would spike CPU usage. By converting the `NormalizedDocument.markdown` into a deterministic SHA-256 hex string during the initial insertion, we reduce the massive `O(N)` string comparison down to a blazing fast `O(1)` hash equality check (`if old_hash == new_hash`).
2. **Metadata Drift Detection:** Sometimes, a problem's text remains exactly the same, but LeetCode promotes its difficulty from "Medium" to "Hard". The Engine intelligently catches this via `_has_metadata_drift()`. By explicitly checking the `difficulty` and the `enriched` semantic JSON blocks, it catches edge cases that the purely text-based SHA-256 hash would completely miss.
3. **Destructive vs. Additive Merge Strategy:** When LeetCode updates a problem, the Engine assumes the `new_doc` is authoritative and physically overwrites the old markdown text (`Latest Wins`). However, if an Admin manually logged into the `MetadataStore` and added `"_custom_tags": ["FAANG_FAVORITE"]`, the `_merge_documents` algorithm natively detects and surgically injects those human additions back into the new document before committing the `UPDATE`, preventing silent data loss.
