"""
ChromaDB Vector Store Plugin.

Provides a robust, local, persistent vector database backend utilizing Chroma.
Supports strict metadata filtering, cosine similarity search, and collection-based namespacing.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings


class ChromaVectorStore:
    """Production Plugin wrapper for ChromaDB."""
    
    def __init__(self, persist_directory: str = "./chroma_db") -> None:
        self._persist_dir = persist_directory
        self._logger = logging.getLogger(__name__)
        
        # Initialize the Physical Persistent Client
        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=Settings(
                anonymized_telemetry=False, # Security/Privacy compliance
                is_persistent=True
            )
        )

    def _get_or_create_collection(self, namespace: str):
        """
        Maps logical business namespaces (e.g., 'algorithms') to physical Chroma Collections.
        Forces strict Cosine Similarity to perfectly match Gemini Embeddings.
        """
        # ChromaDB requires valid collection names (alphanumeric and underscores only)
        safe_name = namespace.replace("-", "_").lower()
        return self._client.get_or_create_collection(
            name=safe_name,
            # Gemini models are specifically trained for Cosine Distance
            metadata={"hnsw:space": "cosine"} 
        )

    async def upsert(self, namespace: str, vectors: List[Tuple[str, List[float], Dict[str, Any]]]) -> bool:
        """
        Idempotent insert/update of massive mathematical embeddings.
        Tuple format: (chunk_id, vector_floats, metadata_dict)
        """
        if not vectors:
            return True
            
        collection = self._get_or_create_collection(namespace)
        
        # Deconstruct tuples into Chroma's required flat-array structures
        ids = [v[0] for v in vectors]
        embeddings = [v[1] for v in vectors]
        metadatas = [v[2] for v in vectors]
        
        try:
            # Chroma DB handles batch upserts natively in C++ via SQLite/Parquet
            # Note: In a production async app, this synchronous library call is wrapped in a ThreadPool
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas
            )
            self._logger.info(f"Successfully Upserted {len(vectors)} vectors to Collection '{namespace}'.")
            return True
            
        except Exception as e:
            self._logger.error(f"FATAL: Failed to upsert batch to ChromaDB: {e}")
            raise e

    async def delete(self, namespace: str, filter: Dict[str, Any]) -> bool:
        """
        Deletes vectors based on metadata filter (e.g., {'document_id': 'two-sum'}).
        Critical for the IndexingEngine's Atomic Rollback logic.
        """
        collection = self._get_or_create_collection(namespace)
        try:
            # Chroma strictly uses 'where' for metadata attribute filtering
            collection.delete(where=filter)
            self._logger.warning(f"Deleted vectors from '{namespace}' matching filter: {filter}.")
            return True
        except Exception as e:
            self._logger.error(f"Failed to execute semantic delete: {e}")
            raise e

    async def similarity_search(
        self, 
        namespace: str, 
        query_vector: List[float], 
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes a lightning-fast HNSW (Hierarchical Navigable Small World) search.
        Returns a strictly structured list of results.
        """
        collection = self._get_or_create_collection(namespace)
        
        try:
            # Execute physical C++ search
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=filter,
                include=["metadatas", "distances"]
            )
            
            # Format Chroma's multi-dimensional return structure into a clean Python List[Dict]
            formatted_results = []
            if results['ids'] and len(results['ids']) > 0:
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        "id": results['ids'][0][i],
                        # Cosine Distance = 1.0 - Cosine Similarity
                        "score": 1.0 - results['distances'][0][i], 
                        "metadata": results['metadatas'][0][i]
                    })
                    
            return formatted_results
            
        except Exception as e:
            self._logger.error(f"Vector Similarity search failed: {e}")
            return []

    def snapshot(self) -> str:
        """
        Returns the physical directory path to allow cron backups.
        Because Chroma PersistentClient syncs to disk instantly, a snapshot 
        is simply archiving the _persist_dir.
        """
        self._logger.info(f"ChromaDB State is synced to physical disk at {self._persist_dir}.")
        return self._persist_dir
