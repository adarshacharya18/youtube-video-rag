"""
RAG (Retrieval-Augmented Generation) & Knowledge Organization Module.

Exports core RAG components:
- Chunkers: TextChunker, CodeChunker, Chunk
- Embedders: BaseEmbedder, MockEmbedder, OpenAIEmbedder, get_embedder
- VectorStore: ChromaVectorStore
"""

from src.core.rag.embedder import (
    BaseEmbedder,
    Chunk,
    CodeChunker,
    MockEmbedder,
    OpenAIEmbedder,
    TextChunker,
    get_embedder,
)
from src.core.rag.vector_store import ChromaVectorStore

__all__ = [
    "Chunk",
    "TextChunker",
    "CodeChunker",
    "BaseEmbedder",
    "MockEmbedder",
    "OpenAIEmbedder",
    "get_embedder",
    "ChromaVectorStore",
]
