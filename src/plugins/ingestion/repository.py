"""
Knowledge Repository.

Dedicated persistence adapter for the Ingestion Pipeline. 
Coordinates saving Raw HTML/JSON to the ArtifactStore (blob storage),
and saving semantic Markdown/Metadata to the MetadataStore (structured storage).
"""

import logging
import time
from typing import Any, Dict

from src.core.artifact_store import ArtifactStore
from src.core.exceptions import PipelineError
from src.core.metadata_store import MetadataStore
from src.core.storage_manager import StorageManager
from src.plugins.ingestion.connector_base import RawContent
from src.plugins.ingestion.normalizer import NormalizedDocument


class RepositoryError(PipelineError):
    """Raised when either Blob Storage or SQLite insertions fail."""
    pass


class KnowledgeRepository:
    """
    Handles atomic persistence of Ingestion data, spanning both Blob storage and SQLite.
    """
    def __init__(self, storage_manager: StorageManager) -> None:
        self._storage = storage_manager
        self._logger = logging.getLogger(__name__)

    async def persist_knowledge(
        self, 
        raw: RawContent, 
        doc: NormalizedDocument, 
        action: str
    ) -> None:
        """
        Atomically saves the raw blob and the structured metadata.
        """
        try:
            # We look up the raw stores directly from the core StorageManager Registry
            artifact_store: ArtifactStore = self._storage.get_store("artifacts") # type: ignore
        except Exception:
            self._logger.warning("ArtifactStore not found. Raw source archiving will be skipped.")
            artifact_store = None # type: ignore
            
        try:
            meta_store: MetadataStore = self._storage.get_store("metadata") # type: ignore
        except Exception as e:
            raise RepositoryError(f"FATAL: MetadataStore is missing from StorageManager: {e}") from e
            
        # 1. Save Raw Source to Blob Storage (Audit Trail / Re-Parsing Buffer)
        raw_artifact_path = None
        if artifact_store:
            # Sanitize the URI so the OS doesn't crash on invalid filename characters
            safe_name = raw.uri.replace("https://", "").replace("/", "_").replace(":", "_") + f"_{int(time.time())}.raw"
            
            # Ensure we write exact physical bytes to the OS Drive
            raw_bytes = raw.content_body.encode('utf-8') if isinstance(raw.content_body, str) else raw.content_body
            raw_artifact_path = await artifact_store.write_artifact("raw_ingestion", safe_name, raw_bytes)
            
        # 2. Extract telemetry injected by the Deduplication Engine
        version = doc.metadata.get("_version", 1)
        checksum = doc.metadata.get("_content_hash", "UNKNOWN")
        
        # 3. Package Strict Audit Information
        audit_info = {
            "source_uri": raw.uri,
            "content_type": raw.content_type,
            "raw_artifact_path": raw_artifact_path,
            "version": version,
            "checksum": checksum,
            "ingested_at": time.time(),
            "action": action
        }
        
        final_metadata = dict(doc.metadata)
        
        # 4. Maintain a rolling version history log inside the metadata block
        history: list[dict[str, Any]] = final_metadata.get("_version_history", [])
        history.append(audit_info)
        
        final_metadata["_audit"] = audit_info
        final_metadata["_version_history"] = history
        
        # Assemble the SQLite Payload
        payload = {
            "title": doc.title,
            "markdown": doc.markdown,
            "metadata": final_metadata
        }
        
        # 5. Save Structured Data to Metadata Store via strict Unit-of-Work
        try:
            async with self._storage.transaction("metadata"):
                await meta_store.save_metadata(
                    category="knowledge",
                    entity_id=doc.id,
                    data=payload,
                    tags=doc.tags
                )
        except Exception as e:
            # Note: The raw blob on disk is technically orphaned here if SQLite fails.
            # In Phase 08, the ArtifactStore's `cleanup_expired` TTL GC handles these gracefully.
            raise RepositoryError(f"Failed to persist Knowledge to SQLite: {e}") from e
            
        self._logger.debug(f"Dual-Persisted Knowledge for '{doc.id}' (Version {version})")
