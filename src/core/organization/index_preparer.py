"""
Index Preparation Engine.

Prepares raw markdown and classified metadata into highly structured chunks,
optimized perfectly for Semantic Vector Embedding without actually hitting the LLM API.
"""

import hashlib
from dataclasses import dataclass
from typing import Dict, List

from src.core.organization.metadata_classifier import ClassifiedMetadata
from src.core.organization.prerequisite_analyzer import PrerequisiteMetadata


@dataclass
class DocumentChunk:
    """A strictly bounded segment of text optimized for LLM Embeddings."""
    chunk_id: str
    text_content: str
    token_estimate: int
    metadata: Dict[str, str]


@dataclass
class PreparedIndex:
    """The final DTO ready to be dispatched to the Vector Database."""
    document_id: str
    document_version: str
    chunks: List[DocumentChunk]
    global_metadata: Dict[str, str]
    relationships: Dict[str, List[str]]


class IndexPreparer:
    """Chunks documents and flattens metadata for Vector Database ingestion."""
    
    def __init__(self, max_tokens_per_chunk: int = 500) -> None:
        self._max_tokens = max_tokens_per_chunk

    def prepare(
        self,
        document_id: str,
        markdown_text: str,
        classified_meta: ClassifiedMetadata,
        prerequisite_meta: PrerequisiteMetadata,
        document_version: str = "1.0.0"
    ) -> PreparedIndex:
        """
        Takes raw components and strictly formats them for the Vector DB.
        """
        # 1. Flatten Metadata for Vector DB (Vector DBs reject nested JSON)
        global_meta = self._flatten_metadata(classified_meta, prerequisite_meta)
        
        # 2. Extract Mathematical Relationships
        relationships = {
            "requires": prerequisite_meta.direct_dependencies,
            "historical": prerequisite_meta.all_historical_dependencies
        }
        
        # 3. Calculate Semantic Chunking Boundaries
        chunks = self._chunk_document(document_id, markdown_text, global_meta)
        
        return PreparedIndex(
            document_id=document_id,
            document_version=document_version,
            chunks=chunks,
            global_metadata=global_meta,
            relationships=relationships
        )

    def _flatten_metadata(
        self, classified: ClassifiedMetadata, prereqs: PrerequisiteMetadata
    ) -> Dict[str, str]:
        """
        Flattens complex nested DTOs into purely scalar strings (CSV).
        This allows the Vector DB to execute hyper-fast WHERE clauses.
        """
        return {
            "difficulty": classified.difficulty,
            "algorithm_family": classified.algorithm_family,
            "pattern": classified.pattern,
            "educational_level": classified.educational_level,
            "visualization_complexity": classified.visualization_complexity,
            "expected_runtime": classified.expected_runtime,
            "memory_complexity": classified.memory_complexity,
            "tags": ",".join(classified.validated_tags),
            "direct_dependencies": ",".join(prereqs.direct_dependencies),
            "learning_order": ",".join(prereqs.learning_order)
        }

    def _chunk_document(self, document_id: str, text: str, global_meta: Dict[str, str]) -> List[DocumentChunk]:
        """
        Splits markdown by semantic paragraph boundaries.
        Uses a heuristic token estimator (1 token ~= 4 chars) to aggressively 
        maintain zero-dependency architecture, avoiding heavy `tiktoken` imports.
        """
        chunks = []
        paragraphs = text.split("\n\n")
        
        current_chunk_text = ""
        current_tokens = 0
        chunk_index = 0
        
        for p in paragraphs:
            # Heuristic token estimate (Extremely fast, zero-dependency)
            p_tokens = len(p) // 4
            
            # If appending this paragraph exceeds the boundary, seal the chunk
            if current_tokens + p_tokens > self._max_tokens and current_chunk_text:
                chunks.append(
                    self._build_chunk(document_id, chunk_index, current_chunk_text, current_tokens, global_meta)
                )
                chunk_index += 1
                current_chunk_text = p
                current_tokens = p_tokens
            else:
                current_chunk_text += "\n\n" + p if current_chunk_text else p
                current_tokens += p_tokens
                
        # Append the final dangling chunk
        if current_chunk_text:
            chunks.append(
                self._build_chunk(document_id, chunk_index, current_chunk_text, current_tokens, global_meta)
            )
            
        return chunks

    def _build_chunk(
        self, doc_id: str, index: int, text: str, tokens: int, meta: Dict[str, str]
    ) -> DocumentChunk:
        """
        Constructs a deterministic chunk ID with a SHA-256 hash checksum.
        Allows idempotent Vector DB Upserts (ignoring chunks that haven't changed).
        """
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]
        chunk_id = f"{doc_id}_chunk_{index}_{text_hash}"
        
        # We explicitly clone the global metadata into EVERY chunk so the 
        # Vector DB can filter on `difficulty == 'Hard'` regardless of which chunk hits.
        chunk_meta = meta.copy()
        chunk_meta["chunk_index"] = str(index)
        
        return DocumentChunk(
            chunk_id=chunk_id,
            text_content=text.strip(),
            token_estimate=tokens,
            metadata=chunk_meta
        )
