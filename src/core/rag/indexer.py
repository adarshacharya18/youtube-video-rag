"""
RAG Indexing Engine.

Handles high-throughput batch and incremental ingestion of PreparedIndexes into the 
Vector Database plugin. Ensures idempotency, rollbacks, and progress tracking.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.core.organization.index_preparer import PreparedIndex
from src.plugins.plugin_manager import PluginManager


@dataclass
class IndexingResult:
    """Strictly typed telemetry payload for a single document's ingestion."""
    document_id: str
    chunks_indexed: int
    is_success: bool
    error_message: Optional[str] = None
    version_indexed: str = "1.0.0"


class IndexingEngine:
    """Manages the physical batch upsert of chunks into a Vector DB."""
    
    def __init__(self, plugin_manager: PluginManager, batch_size: int = 100) -> None:
        self._plugins = plugin_manager
        # Optimal batch size for OpenAI `text-embedding-3-small` is usually ~100-500
        self._batch_size = batch_size
        self._logger = logging.getLogger(__name__)
        # Hard cap on concurrent external API calls to prevent DDOSing OpenAI
        self._semaphore = asyncio.Semaphore(10)

    async def index_document(self, prepared_index: PreparedIndex, namespace: str) -> IndexingResult:
        """
        Incrementally indexes a single document.
        Executes physical API embeddings and DB upserts in bounded batches.
        """
        doc_id = prepared_index.document_id
        self._logger.info(f"Starting incremental index for '{doc_id}' into '{namespace}'...")
        
        # 1. Validation
        if not prepared_index.chunks:
            return IndexingResult(doc_id, 0, False, "Validation Error: No chunks provided.")
            
        vector_db = self._plugins.get_vector_db()
        embedder = self._plugins.get_embedder()
        
        if not vector_db or not embedder:
            return IndexingResult(doc_id, 0, False, "System Error: Required plugins (Vector/Embed) not loaded.")

        chunks = prepared_index.chunks
        total_indexed = 0
        
        try:
            # 2. Semaphore Lock for API Concurrency limits
            async with self._semaphore:
                
                # 3. Batch Processing Loop
                for i in range(0, len(chunks), self._batch_size):
                    batch = chunks[i : i + self._batch_size]
                    
                    # Extract raw text for LLM API
                    texts = [chunk.text_content for chunk in batch]
                    
                    # Generate Embeddings (Heavy Network Call)
                    vectors = await embedder.embed_batch(texts)
                    
                    # Prepare Vector DB Upsert Payload: Tuple(ID, Vector[], MetadataDict)
                    payloads = []
                    for idx, chunk in enumerate(batch):
                        meta = chunk.metadata.copy()
                        meta["document_id"] = doc_id
                        meta["version"] = prepared_index.document_version
                        payloads.append((chunk.chunk_id, vectors[idx], meta))
                        
                    # 4. Upsert to Vector Database
                    await vector_db.upsert(
                        namespace=namespace,
                        vectors=payloads
                    )
                    total_indexed += len(batch)
                    
            self._logger.info(f"Successfully indexed {total_indexed} chunks for '{doc_id}'.")
            return IndexingResult(
                document_id=doc_id,
                chunks_indexed=total_indexed,
                is_success=True,
                version_indexed=prepared_index.document_version
            )
            
        except Exception as e:
            self._logger.error(f"Indexing critically failed for '{doc_id}': {e}")
            # 5. Atomic Rollback on Failure
            await self._rollback_document(doc_id, namespace)
            return IndexingResult(doc_id, total_indexed, False, str(e))

    async def index_full_batch(self, documents: List[PreparedIndex], namespace: str) -> Dict[str, IndexingResult]:
        """
        Executes a massive full re-indexing of multiple documents concurrently.
        Automatically distributes load while respecting the internal Semaphore limits.
        """
        self._logger.info(f"Initiating Massive Batch Indexing of {len(documents)} documents...")
        results: Dict[str, IndexingResult] = {}
        
        # Fire off all document indexers concurrently. The `Semaphore` inside 
        # `index_document` will gracefully queue them up to prevent API ratelimits.
        tasks = [self.index_document(doc, namespace) for doc in documents]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for doc, response in zip(documents, responses):
            if isinstance(response, Exception):
                self._logger.error(f"Task crash for {doc.document_id}: {response}")
                results[doc.document_id] = IndexingResult(doc.document_id, 0, False, str(response))
            else:
                results[doc.document_id] = response
                
        return results

    async def _rollback_document(self, document_id: str, namespace: str) -> None:
        """
        Atomic rollback. If a batch fails halfway, delete all chunks belonging to this 
        specific document ID to prevent corrupted, partial semantic retrieval state.
        """
        self._logger.warning(f"Initiating Atomic Rollback for Document '{document_id}'...")
        try:
            vector_db = self._plugins.get_vector_db()
            if vector_db:
                # Delete by explicit metadata filter matching
                await vector_db.delete(
                    namespace=namespace,
                    filter={"document_id": document_id}
                )
            self._logger.info(f"Rollback successful for '{document_id}'.")
        except Exception as e:
            # If the rollback fails, the Vector DB has partial corrupted data
            self._logger.critical(f"FATAL: Rollback failed for '{document_id}': {e}. Manual DB intervention required.")
