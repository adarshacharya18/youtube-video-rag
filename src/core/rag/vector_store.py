"""
ChromaDB Vector Store Wrapper for DSA Problem and Knowledge Retrieval.

Provides:
- ChromaVectorStore: Production and test vector store managing problem chunks,
  metadata filtering, vector similarity queries, and collection management.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.core.config import RAGConfig
from src.core.exceptions import IndexNotFoundError, RAGError
from src.core.logger import get_logger
from src.core.rag.embedder import BaseEmbedder, Chunk, CodeChunker, TextChunker, get_embedder
from src.models.problem import ScrapedProblem

logger = get_logger(__name__)


class _InMemoryCollection:
    """
    Genuine in-memory vector storage implementation used when chromadb library is not installed.
    Computes exact L2/cosine distance similarity search and handles metadata filtering.
    """

    def __init__(self, name: str):
        self.name = name
        self._chunks: Dict[str, Dict[str, Any]] = {}

    def count(self) -> int:
        return len(self._chunks)

    def upsert(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> None:
        for i, cid in enumerate(ids):
            self._chunks[cid] = {
                "id": cid,
                "document": documents[i],
                "metadata": metadatas[i],
                "embedding": embeddings[i],
            }

    def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not query_embeddings or not self._chunks:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        q_emb = query_embeddings[0]
        matching = []

        for cid, item in self._chunks.items():
            meta = item["metadata"]
            if where and not self._matches_where(meta, where):
                continue

            emb = item["embedding"]
            dot = sum(a * b for a, b in zip(q_emb, emb))
            norm_a = math.sqrt(sum(a * a for a in q_emb)) or 1.0
            norm_b = math.sqrt(sum(b * b for b in emb)) or 1.0
            cos_sim = dot / (norm_a * norm_b)
            distance = float(max(0.0, 1.0 - cos_sim))

            matching.append((distance, item))

        matching.sort(key=lambda x: x[0])
        top_items = matching[:n_results]

        res_ids = [item["id"] for _, item in top_items]
        res_docs = [item["document"] for _, item in top_items]
        res_metas = [item["metadata"] for _, item in top_items]
        res_dists = [dist for dist, _ in top_items]

        return {
            "ids": [res_ids],
            "documents": [res_docs],
            "metadatas": [res_metas],
            "distances": [res_dists],
        }

    def _matches_where(self, meta: Dict[str, Any], where: Dict[str, Any]) -> bool:
        if "$and" in where:
            return all(self._matches_where(meta, sub) for sub in where["$and"])
        if "$or" in where:
            return any(self._matches_where(meta, sub) for sub in where["$or"])

        for k, v in where.items():
            if k.startswith("$"):
                continue
            meta_val = meta.get(k)
            if isinstance(v, dict):
                if "$in" in v:
                    if str(meta_val) not in [str(x) for x in v["$in"]]:
                        return False
                if "$contains" in v:
                    if str(v["$contains"]) not in str(meta_val):
                        return False
            else:
                if str(meta_val) != str(v) and str(v) not in str(meta_val).split(","):
                    return False
        return True

    def get(
        self, where: Optional[Dict[str, Any]] = None, include: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        matched_ids = []
        matched_metas = []
        for cid, item in self._chunks.items():
            if not where or self._matches_where(item["metadata"], where):
                matched_ids.append(cid)
                matched_metas.append(item["metadata"])
        return {"ids": matched_ids, "metadatas": matched_metas}

    def delete(self, ids: List[str]) -> None:
        for cid in ids:
            self._chunks.pop(cid, None)


class _InMemoryClient:
    """Fallback client when chromadb is not installed."""

    def __init__(self):
        self.collections: Dict[str, _InMemoryCollection] = {}

    def get_or_create_collection(
        self, name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> _InMemoryCollection:
        if name not in self.collections:
            self.collections[name] = _InMemoryCollection(name)
        return self.collections[name]

    def delete_collection(self, name: str) -> None:
        self.collections.pop(name, None)


class ChromaVectorStore:
    """
    Wrapper around ChromaDB vector store supporting persistent storage and ephemeral in-memory execution.
    """

    def __init__(
        self,
        config: Optional[RAGConfig] = None,
        embedder: Optional[BaseEmbedder] = None,
        is_test: bool = False,
        persist_directory: Optional[Union[str, Path]] = None,
        collection_name: Optional[str] = None,
    ):
        self.config = config or RAGConfig()
        self.is_test = is_test

        self.collection_name = collection_name or self.config.collection_name
        self.persist_directory = Path(
            persist_directory or self.config.chroma_db_dir
        )

        self.embedder = embedder or get_embedder(
            model_name=self.config.embedding_model,
            use_mock=self.config.use_mock_embedder or is_test,
        )

        self.text_chunker = TextChunker()
        self.code_chunker = CodeChunker()

        self._init_client()

    def _init_client(self) -> None:
        """Initialize ChromaDB client or fallback in-memory store."""
        try:
            import chromadb

            if self.is_test:
                self.client = chromadb.EphemeralClient()
            else:
                self.persist_directory.mkdir(parents=True, exist_ok=True)
                self.client = chromadb.PersistentClient(path=str(self.persist_directory))

            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except ImportError:
            logger.info("chromadb not installed; using genuine _InMemoryClient fallback")
            self.client = _InMemoryClient()
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            raise IndexNotFoundError(f"Failed to initialize ChromaDB collection: {e}") from e

    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all metadata values are ChromaDB-compatible primitives (str, int, float, bool)."""
        clean_meta = {}
        for k, v in metadata.items():
            if v is None:
                continue
            elif isinstance(v, (str, int, float, bool)):
                clean_meta[k] = v
            elif isinstance(v, (list, tuple, set)):
                clean_meta[k] = ",".join(str(item) for item in v)
            else:
                clean_meta[k] = str(v)
        return clean_meta

    def add_chunks(
        self,
        chunks: List[Chunk],
        embeddings: Optional[List[List[float]]] = None,
    ) -> List[str]:
        """
        Embed and insert a list of Chunk objects into the ChromaDB collection.
        Returns the list of inserted chunk IDs.
        """
        if not chunks:
            return []

        if embeddings is None:
            embeddings = self.embedder.embed_chunks(chunks)

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for chunk in chunks:
            ids.append(chunk.chunk_id)
            documents.append(chunk.content)

            meta = dict(chunk.metadata)
            meta["chunk_type"] = chunk.chunk_type
            if chunk.parent_slug:
                meta["parent_slug"] = chunk.parent_slug
                meta["slug"] = chunk.parent_slug
            if chunk.start_line is not None:
                meta["start_line"] = chunk.start_line
            if chunk.end_line is not None:
                meta["end_line"] = chunk.end_line

            metadatas.append(self._sanitize_metadata(meta))

        try:
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )
            logger.info(
                "Successfully indexed chunks in ChromaDB",
                count=len(ids),
                collection=self.collection_name,
            )
            return ids
        except Exception as e:
            raise RAGError(f"Failed to upsert chunks to ChromaDB: {e}") from e

    def add_problem(self, problem: ScrapedProblem) -> List[str]:
        """
        Chunks problem description, constraints, examples, and accepted code,
        embeds them, and inserts them into ChromaDB.
        Returns list of inserted chunk IDs.
        """
        text_chunks = self.text_chunker.chunk_problem(problem)
        code_chunks = self.code_chunker.chunk_problem(problem)
        all_chunks = text_chunks + code_chunks

        if not all_chunks:
            logger.warning("No chunks generated for problem", slug=problem.slug)
            return []

        return self.add_chunks(all_chunks)

    def _normalize_where_clause(
        self, where: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Translates user-friendly filters into valid ChromaDB `where` syntax."""
        if not where:
            return None

        if any(k.startswith("$") for k in where.keys()):
            return where

        clauses = []
        for key, val in where.items():
            if isinstance(val, (list, tuple)):
                clauses.append({key: {"$in": [str(v) for v in val]}})
            elif key == "tags" and isinstance(val, str):
                clauses.append({"tags": {"$contains": val}})
            else:
                clauses.append({key: val})

        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Embeds query_text, queries ChromaDB collection with optional metadata filters.
        Returns a list of result dicts containing id, document, metadata, distance, and score.
        """
        if not query_text or not query_text.strip():
            return []

        count = self.collection.count()
        if count == 0:
            return []

        query_embedding = self.embedder.embed_text(query_text)
        chroma_where = self._normalize_where_clause(where)

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, count),
                where=chroma_where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            raise RAGError(f"ChromaDB query failed: {e}") from e

        formatted: List[Dict[str, Any]] = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return formatted

        ids = results["ids"][0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            dist = dists[i] if i < len(dists) else 0.0
            score = max(0.0, 1.0 - dist)

            formatted.append(
                {
                    "id": ids[i],
                    "document": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                    "distance": dist,
                    "score": score,
                }
            )

        return formatted

    def query_by_text(
        self,
        query_text: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Alias for query method."""
        return self.query(query_text=query_text, top_k=top_k, where=where)

    def delete_by_slug(self, slug: str) -> bool:
        """
        Deletes all chunks belonging to a specific problem slug.
        Returns True if chunks were deleted, False otherwise.
        """
        if not slug:
            return False

        try:
            existing = self.collection.get(where={"slug": slug})
            if not existing or not existing.get("ids"):
                return False

            ids_to_delete = existing["ids"]
            self.collection.delete(ids=ids_to_delete)
            logger.info("Deleted chunks for problem slug", slug=slug, count=len(ids_to_delete))
            return True
        except Exception as e:
            raise RAGError(f"Failed to delete chunks for slug '{slug}': {e}") from e

    def delete_collection(self) -> None:
        """Wipes the entire collection and recreates an empty one."""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Deleted and recreated collection", collection=self.collection_name)
        except Exception as e:
            raise RAGError(f"Failed to delete collection '{self.collection_name}': {e}") from e

    def get_stats(self) -> Dict[str, Any]:
        """
        Returns statistics about the vector collection (total chunks, unique slugs, chunk types).
        """
        try:
            count = self.collection.count()
            all_data = self.collection.get(include=["metadatas"])
            metas = all_data.get("metadatas", []) or []

            slugs = set()
            chunk_types = {"text": 0, "code": 0}

            for meta in metas:
                if not meta:
                    continue
                s = meta.get("slug") or meta.get("parent_slug")
                if s:
                    slugs.add(s)
                ctype = meta.get("chunk_type")
                if ctype in chunk_types:
                    chunk_types[ctype] += 1
                elif ctype:
                    chunk_types[ctype] = 1

            return {
                "collection_name": self.collection_name,
                "total_chunks": count,
                "total_problems": len(slugs),
                "unique_slugs": sorted(list(slugs)),
                "chunk_types": chunk_types,
            }
        except Exception as e:
            raise RAGError(f"Failed to retrieve vector store stats: {e}") from e
