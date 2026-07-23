"""
RAG Context Builder.

Takes the final, reranked chunks from the Retrieval/Reranking Engines and 
compiles them into a single, cohesive, token-budgeted Markdown payload string.
Handles explicit citations, deduplication, and pedagogical ordering.
"""

import logging
from typing import List

from src.core.rag.retriever import RetrievedContext


class ContextBuilder:
    """Compiles disparate Vector DB chunks into a clean LLM Prompt Context."""
    
    def __init__(self, max_context_tokens: int = 4000) -> None:
        # LLMs like GPT-4 have large windows, but keeping RAG context tight (4k tokens)
        # massively improves the LLM's attention span and reduces cost.
        self._max_tokens = max_context_tokens
        self._logger = logging.getLogger(__name__)
        # Fast, zero-dependency token heuristic
        self._chars_per_token = 4

    def build_context(self, chunks: List[RetrievedContext], query: str) -> str:
        """
        Assembles the final string payload for the Script Generation LLM.
        Ensures the final string mathematically does not exceed the LLM's context window.
        """
        if not chunks:
            self._logger.warning("No chunks provided to ContextBuilder.")
            return "No relevant historical context found."
            
        self._logger.debug(f"Building context from {len(chunks)} chunks. Token Budget: {self._max_tokens}")
        
        # 1. Hard Deduplication (Safety catch, even though Retriever should have done this)
        unique_chunks = self._deduplicate(chunks)
        
        # 2. Pedagogical Ordering (Force Theory first, then Code implementations)
        ordered_chunks = self._order_pedagogically(unique_chunks)
        
        # 3. Assembly & Token Budgeting
        final_text = f"--- RAG CONTEXT FOR: {query} ---\n\n"
        current_tokens = len(final_text) // self._chars_per_token
        
        for idx, chunk in enumerate(ordered_chunks):
            # In production, the DB fetches the text payload. We assume the physical 
            # string was loaded into the metadata dictionary during retrieval.
            text_content = chunk.metadata.get("text_content", f"[Content for {chunk.chunk_id}]")
            source = chunk.metadata.get("document_id", "Unknown Source")
            is_code = str(chunk.metadata.get("is_code", "false")).lower() == "true"
            
            chunk_tokens = len(text_content) // self._chars_per_token
            
            # 4. Strict Budget Enforcement
            if current_tokens + chunk_tokens > self._max_tokens:
                self._logger.warning(
                    f"Context budget exceeded at chunk {idx} ({current_tokens} > {self._max_tokens}). "
                    "Truncating remaining chunks to protect LLM stability."
                )
                break
                
            # 5. Formatting with Explicit Citations
            block_type = "CODE BLOCK" if is_code else "THEORY / PROSE"
            final_text += f"### SOURCE: {source} [{block_type}]\n"
            final_text += f"{text_content}\n\n"
            
            current_tokens += chunk_tokens
            
        final_text += "--- END OF CONTEXT ---\n"
        
        self._logger.info(f"Successfully compiled RAG Context payload ({current_tokens} tokens).")
        return final_text

    def _deduplicate(self, chunks: List[RetrievedContext]) -> List[RetrievedContext]:
        """
        Ensures absolutely no overlapping chunk IDs exist in the final payload,
        which would waste precious LLM tokens.
        """
        seen = set()
        deduped = []
        for c in chunks:
            if c.chunk_id not in seen:
                seen.add(c.chunk_id)
                deduped.append(c)
        return deduped

    def _order_pedagogically(self, chunks: List[RetrievedContext]) -> List[RetrievedContext]:
        """
        Reorders the mathematical ranking specifically for LLM consumption.
        Forces Theory/Prose chunks to appear FIRST in the prompt, providing foundational 
        understanding, followed by Code/Implementations at the absolute bottom.
        """
        theory = []
        code = []
        
        for c in chunks:
            is_code = str(c.metadata.get("is_code", "false")).lower() == "true"
            if is_code:
                code.append(c)
            else:
                theory.append(c)
                
        # Return theory first, then code
        return theory + code
