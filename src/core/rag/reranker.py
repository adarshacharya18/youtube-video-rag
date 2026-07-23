"""
RAG Semantic Reranking Service.

Re-evaluates and re-scores the Top-K chunks returned by the Vector Store
using Cross-Encoders and deterministic pedagogical heuristics (Difficulty matching).
"""

import logging
from typing import List, Optional

from src.core.rag.retriever import RetrievedContext


class RerankingService:
    """Applies secondary heuristics and Cross-Encoders to refine RAG retrieval."""
    
    def __init__(self, use_cross_encoder: bool = False) -> None:
        self._logger = logging.getLogger(__name__)
        # Cross encoders are mathematically heavy and slow. We toggle them off by default for speed.
        self._use_cross_encoder = use_cross_encoder
        
        # Difficulty penalty weights. If the viewer is a beginner, and a chunk is "Hard", 
        # we penalize the chunk's score severely to bury it at the bottom of the array.
        self._difficulty_weights = {
            "Beginner": 1,
            "Intermediate": 2,
            "Advanced": 3
        }

    async def rerank(
        self, 
        query: str, 
        chunks: List[RetrievedContext], 
        target_difficulty: Optional[str] = None
    ) -> List[RetrievedContext]:
        """
        Executes a multi-pass reranking algorithm over the retrieved chunks.
        """
        if not chunks:
            return []
            
        self._logger.debug(f"Initiating reranking pipeline for {len(chunks)} chunks.")
        
        reranked_chunks = []
        for chunk in chunks:
            # Clone the chunk to avoid mutating the original Retrieval Engine pointers
            new_chunk = RetrievedContext(
                chunk_id=chunk.chunk_id,
                score=chunk.score,
                metadata=chunk.metadata.copy()
            )
            
            # 1. Apply Pedagogical Heuristics (Difficulty Penalty)
            new_chunk.score = self._apply_difficulty_penalty(new_chunk, target_difficulty)
            
            # 2. Apply Educational Relevance (Boost theory vs code based on metadata)
            new_chunk.score = self._apply_educational_boost(query, new_chunk)
            
            reranked_chunks.append(new_chunk)
            
        # 3. Cross-Encoder Re-scoring (Heavy LLM Execution - Optional)
        if self._use_cross_encoder:
            reranked_chunks = await self._apply_cross_encoder(query, reranked_chunks)
            
        # 4. Final Sort (Descending order, highest mathematically relevant first)
        sorted_chunks = sorted(reranked_chunks, key=lambda x: x.score, reverse=True)
        return sorted_chunks

    def _apply_difficulty_penalty(self, chunk: RetrievedContext, target_difficulty: Optional[str]) -> float:
        """
        If a target difficulty is provided (e.g., "Beginner"), penalize chunks 
        that are mathematically too advanced, even if their cosine similarity is high.
        """
        if not target_difficulty:
            return chunk.score
            
        chunk_diff_str = chunk.metadata.get("educational_level", "Beginner")
        
        target_val = self._difficulty_weights.get(target_difficulty.capitalize(), 1)
        chunk_val = self._difficulty_weights.get(chunk_diff_str.capitalize(), 1)
        
        diff = abs(target_val - chunk_val)
        
        # If perfect match (e.g., Beginner -> Beginner), no penalty
        if diff == 0:
            return chunk.score
            
        # If it's one level off (e.g., Beginner -> Intermediate), slight penalty (-10%)
        if diff == 1:
            return chunk.score * 0.90
            
        # If it's two levels off (e.g., Beginner -> Advanced), massive penalty (-40%)
        # This virtually guarantees an Advanced O(1) space optimization chunk will never
        # be fed to the Script Generator for a Beginner's video.
        if diff == 2:
            return chunk.score * 0.60
            
        return chunk.score

    def _apply_educational_boost(self, query: str, chunk: RetrievedContext) -> float:
        """
        Boosts 'Concept' and 'Theory' chunks if the query asks for explanations.
        Boosts 'Code' chunks if the query asks for implementations.
        """
        q_lower = query.lower()
        is_code_chunk = str(chunk.metadata.get("is_code", "false")).lower() == "true"
        
        # If they want code, and the chunk is a physical code block, mathematically boost it (+5%)
        if ("code" in q_lower or "implement" in q_lower) and is_code_chunk:
            return min(1.0, chunk.score * 1.05)
            
        # If they want theory, and the chunk is prose (NOT code), mathematically boost it (+5%)
        if ("explain" in q_lower or "theory" in q_lower) and not is_code_chunk:
            return min(1.0, chunk.score * 1.05)
            
        return chunk.score

    async def _apply_cross_encoder(self, query: str, chunks: List[RetrievedContext]) -> List[RetrievedContext]:
        """
        Simulates a Cross-Encoder model (e.g., MS-MARCO).
        Unlike Bi-Encoders (which embed query and chunk separately for speed), 
        Cross-Encoders process them simultaneously for massive accuracy gains, at a severe compute cost.
        """
        self._logger.info("Executing heavy Cross-Encoder re-scoring (O(N) latency).")
        # In a real physical environment, this calls a HuggingFace cross-encoder pipeline.
        # For Phase 11 architectural validation, we stub the integration point.
        for chunk in chunks:
            chunk.score = min(1.0, chunk.score * 1.02)
        return chunks
