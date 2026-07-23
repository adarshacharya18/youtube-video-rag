# Phase 11 / 03: Advanced Chunking Engine

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/rag/chunker.py`](#2-source-code-srccoreragchunkerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

While Phase 10 introduced a rudimentary paragraph splitter, a production-grade RAG pipeline requires far more sophistication to prevent context loss. If a binary search implementation (Python code block) is blindly split in half because it hit a token boundary, the LLM will fail to understand the algorithm during retrieval.

The **Advanced Chunking Engine** acts as a semantic parser. It utilizes Regex to proactively isolate Markdown Code Blocks, ensuring they are chunked logically by lines rather than prose paragraphs. Furthermore, it implements **Adaptive Overlap** (sliding windows) and **Parent-Child tracking**, allowing the downstream system to retrieve a small child chunk, but pass the entire parent document to the LLM for maximum context.

---

# 2. Source Code: `src/core/rag/chunker.py`

```python
"""
Advanced RAG Chunking Engine.

Implements recursive, semantic, and code-aware chunking strategies with 
adaptive overlaps and parent-child relationship tracking.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Chunk:
    """Strictly typed payload for a semantically isolated text segment."""
    chunk_id: str
    text_content: str
    token_estimate: int
    metadata: Dict[str, str]
    parent_id: Optional[str] = None
    is_code_block: bool = False


class ChunkingEngine:
    """Parses markdown deterministically, isolating code from prose with overlap retention."""
    
    def __init__(self, max_tokens: int = 500, overlap_tokens: int = 50) -> None:
        self._max_tokens = max_tokens
        self._overlap = overlap_tokens
        self._chars_per_token = 4

    def chunk_document(self, document_id: str, markdown_text: str, global_metadata: Dict[str, str]) -> List[Chunk]:
        """
        Executes a multi-pass hierarchical chunking strategy.
        First extracts code blocks, then recursively splits markdown prose.
        """
        chunks: List[Chunk] = []
        
        # 1. Parent Document Tracking (Used later for "Small-to-Big" RAG Retrieval)
        parent_id = f"{document_id}_parent"
        
        # 2. Extract and protect code blocks using Regex
        # Matches ```python ... ``` securely across newlines
        code_block_pattern = re.compile(r'```(?P<lang>\w*)\n(?P<code>.*?)\n```', re.DOTALL)
        
        last_end = 0
        chunk_index = 0
        
        for match in code_block_pattern.finditer(markdown_text):
            # A. Process the prose BEFORE the code block
            prose = markdown_text[last_end:match.start()].strip()
            if prose:
                prose_chunks = self._chunk_prose(
                    document_id, prose, global_metadata, parent_id, chunk_index
                )
                chunks.extend(prose_chunks)
                chunk_index += len(prose_chunks)
                
            # B. Process the Code Block
            code_text = match.group('code').strip()
            lang = match.group('lang')
            
            # Inject code-specific metadata for Vector Filtering
            meta = global_metadata.copy()
            meta["is_code"] = "true"
            meta["language"] = lang
            
            tokens = len(code_text) // self._chars_per_token
            
            # If the code block is massive (e.g., a massive 800-line solution),
            # split it by lines. Otherwise, keep the entire function intact.
            if tokens > self._max_tokens:
                code_chunks = self._chunk_code(
                    document_id, code_text, meta, parent_id, chunk_index
                )
                chunks.extend(code_chunks)
                chunk_index += len(code_chunks)
            else:
                chunks.append(
                    self._build_chunk(document_id, chunk_index, code_text, tokens, meta, parent_id, True)
                )
                chunk_index += 1
                
            last_end = match.end()
            
        # C. Process any remaining dangling prose at the bottom of the document
        remaining_prose = markdown_text[last_end:].strip()
        if remaining_prose:
            prose_chunks = self._chunk_prose(
                document_id, remaining_prose, global_metadata, parent_id, chunk_index
            )
            chunks.extend(prose_chunks)

        return chunks

    def _chunk_prose(
        self, doc_id: str, text: str, meta: Dict[str, str], parent_id: str, start_idx: int
    ) -> List[Chunk]:
        """Recursively splits markdown by paragraphs, applying a sliding overlap window."""
        chunks = []
        paragraphs = text.split("\n\n")
        
        current_text = ""
        current_tokens = 0
        idx = start_idx
        
        for p in paragraphs:
            p_tokens = len(p) // self._chars_per_token
            
            if current_tokens + p_tokens > self._max_tokens and current_text:
                # 1. Seal the current chunk
                chunks.append(self._build_chunk(doc_id, idx, current_text, current_tokens, meta, parent_id))
                idx += 1
                
                # 2. Apply Adaptive Overlap
                # Grab the last N characters of current_text to prepend to the next chunk
                # This ensures the LLM doesn't lose context if a sentence is split midway.
                overlap_chars = self._overlap * self._chars_per_token
                current_text = current_text[-overlap_chars:] + "\n\n" + p if overlap_chars > 0 else p
                current_tokens = len(current_text) // self._chars_per_token
            else:
                current_text += "\n\n" + p if current_text else p
                current_tokens += p_tokens
                
        # Append final dangling chunk
        if current_text:
            chunks.append(self._build_chunk(doc_id, idx, current_text, current_tokens, meta, parent_id))
            
        return chunks

    def _chunk_code(
        self, doc_id: str, code: str, meta: Dict[str, str], parent_id: str, start_idx: int
    ) -> List[Chunk]:
        """Splits massive code blocks safely by newlines rather than paragraphs."""
        chunks = []
        lines = code.split("\n")
        
        current_text = ""
        current_tokens = 0
        idx = start_idx
        
        for line in lines:
            l_tokens = len(line) // self._chars_per_token
            
            if current_tokens + l_tokens > self._max_tokens and current_text:
                chunks.append(self._build_chunk(doc_id, idx, current_text, current_tokens, meta, parent_id, True))
                idx += 1
                
                # 2. Code Overlap (Keep the last 5 lines for scope context)
                overlap_lines = "\n".join(current_text.split("\n")[-5:])
                current_text = overlap_lines + "\n" + line
                current_tokens = len(current_text) // self._chars_per_token
            else:
                current_text += "\n" + line if current_text else line
                current_tokens += l_tokens
                
        if current_text:
            chunks.append(self._build_chunk(doc_id, idx, current_text, current_tokens, meta, parent_id, True))
            
        return chunks

    def _build_chunk(
        self, doc_id: str, index: int, text: str, tokens: int, meta: Dict[str, str], parent_id: str, is_code: bool = False
    ) -> Chunk:
        """Constructs a deterministic SHA-256 chunk for idempotent DB Upserts."""
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]
        chunk_id = f"{doc_id}_chunk_{index}_{text_hash}"
        
        chunk_meta = meta.copy()
        chunk_meta["chunk_index"] = str(index)
        chunk_meta["parent_id"] = parent_id
        
        return Chunk(
            chunk_id=chunk_id,
            text_content=text.strip(),
            token_estimate=tokens,
            metadata=chunk_meta,
            parent_id=parent_id,
            is_code_block=is_code
        )
```

---

# 3. Design Decisions

1. **Code-Aware Partitioning (`chunk_document`):** Standard chunkers (like Langchain's RecursiveCharacterTextSplitter) blindly slice text when it hits the limit. If it slices a Python `class` exactly down the middle of a `def __init__` function, semantic meaning is destroyed. This Engine uses strict Regex to isolate ` ```python ` blocks *before* chunking, ensuring code functions remain fully intact as solitary Vector chunks.
2. **Adaptive Overlap (`_chunk_prose`):** When reading English prose, if a chunk ends mid-explanation, the next chunk starts with zero context. By setting an `overlap_tokens=50` parameter, the engine physically copies the last 50 tokens of Chunk A and prepends them to Chunk B. The LLM generative engine now has a sliding window of historical context, drastically reducing RAG hallucinations.
3. **Parent-Child Retrieval Targeting (`parent_id`):** This is a cutting-edge advanced RAG technique. When a query is executed, we want to perform the mathematical Vector Similarity Search on *small* chunks (to maximize cosine similarity accuracy). However, when we pass the result to the LLM, we want to pass the *large parent document* so the LLM has full context. By tagging every chunk with `parent_id`, the Retriever can fetch the best child chunk, and dynamically join it to its siblings before script generation begins.
