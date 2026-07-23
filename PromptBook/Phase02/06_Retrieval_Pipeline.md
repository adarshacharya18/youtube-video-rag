# Phase02/06_Retrieval_Pipeline.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Input Context & Retrieval Goals](#2-input-context--retrieval-goals)
3. [Query Rewriting & Expansion](#3-query-rewriting--expansion)
4. [Metadata Filtering](#4-metadata-filtering)
5. [Vector Retrieval](#5-vector-retrieval)
6. [Top-K & Similarity Thresholds](#6-top-k--similarity-thresholds)
7. [Reranking & Compression](#7-reranking--compression)
8. [Deduplication & Context Ordering](#8-deduplication--context-ordering)
9. [Output Formatting](#9-output-formatting)

---

# 1. Executive Summary

This document specifies the exact sequence of operations occurring during the runtime phase of the RAG engine. When the Orchestrator requests context for a specific LeetCode problem, the Retrieval Pipeline executes a sophisticated multi-stage process: Query Rewriting, Vector Retrieval, Reranking, and Context Formatting. This ensures the Script Generator receives highly relevant, noise-free educational material.

---

# 2. Input Context & Retrieval Goals

### 2.1 The Input
The RAG Engine does not receive a simple user string. It receives a structured payload:
- **Problem:** Full text description, constraints, and canonical slug.
- **Difficulty:** Easy / Medium / Hard.
- **Tags:** e.g., `["Array", "Sliding Window"]`
- **Solution:** The accepted C++ code block.
- **Requested Section:** (Optional) The specific script section being generated (e.g., `COMPLEXITY_ANALYSIS`), used to dynamically tune the retrieval focus.

### 2.2 The Target
The pipeline must extract the following from the local ChromaDB:
- **Algorithms & Patterns:** Formal definitions (e.g., "What is a Sliding Window?").
- **Complexities:** Mathematical proofs for Time/Space limits.
- **Examples & Analogies:** Real-world comparisons (e.g., "A sliding window is like a caterpillar moving across a leaf").
- **Visual Ideas:** Directives for Manim animations.
- **Educational Insights:** Common pitfalls, edge cases, and "gotchas" specific to the tags.

---

# 3. Query Rewriting & Expansion

A single dense vector embedding of the raw LeetCode problem is ineffective for retrieving broad educational concepts. We employ an **LLM-based Query Rewriter**.

1. **Analysis:** The Rewriter LLM examines the problem, tags, and solution.
2. **Expansion:** It generates 3 to 4 independent, highly targeted search queries.
   - *Query 1 (Theory):* "Explain the sliding window algorithm pattern and its core principles."
   - *Query 2 (Complexity):* "Time and space complexity analysis of sliding window with hash map."
   - *Query 3 (Visuals):* "How to visually animate two pointers expanding and contracting a window."
3. **Execution:** Each of these rewritten queries is executed in parallel against the database.
4. **Fallback Strategy:** If the Gemini API fails or times out during the rewriting phase, the system catches the error and falls back to a deterministic query: concatenating the raw problem title, difficulty, and primary tags into a single search string.

---

# 4. Metadata Filtering

Before similarity math occurs, the search space is aggressively pruned using ChromaDB's `where` filters.

- **Pre-Filtering:** If the problem is tagged `["Graph", "BFS"]`, a filter `{"category": {"$in": ["graph_theory", "general"]}}` is applied. 
- **Language Enforcement:** The filter `{"language": "cpp"}` ensures that Python or Java-specific syntax chunks are discarded entirely, preventing the Script Generator from hallucinating standard library methods.

---

# 5. Vector Retrieval

Relying solely on dense semantic vectors can sometimes cause "Keyword Misses" if not bounded correctly. We solve this by leveraging strict Metadata Filtering alongside the Dense Vector Retrieval, entirely within ChromaDB, omitting the complexity and desynchronization risks of maintaining a separate BM25 sparse index.

1. **Dense Vector Retrieval:**
   - Embeds the rewritten queries using Gemini `text-embedding-004`.
   - Executes a Cosine Similarity search on the HNSW index in ChromaDB.
2. **Metadata Simulation of Keyword Search:**
   - Instead of a secondary keyword database, critical keywords (like algorithm names and language syntaxes) are enforced via the `where` filters (Section 4), forcing the dense search to only consider exactly matching keyword buckets.

---

# 6. Top-K & Similarity Thresholds

To balance context richness with token limits, the retrieval parameters are strictly defined:

- **Initial Fetch (Top K):** 
  - Vector Search retrieves the top `K=15` chunks per query.
- **Similarity Threshold:** 
  - Vector chunks with a Cosine Similarity score below `0.75` are immediately discarded. This prevents the inclusion of "best effort but irrelevant" chunks when the knowledge base legitimately lacks information on a niche topic.

---

# 7. Reranking & Compression

The Vector Retrieval phase produces a noisy, overlapping list of potential chunks. 

### 7.1 Cross-Encoder Reranking
To resolve CPU latency bottlenecks, we limit the Cross-Encoder to only the top **10** chunks from the initial vector retrieval. These chunks are passed through a lightweight, locally executed, ONNX-quantized `int8` Cross-Encoder (e.g., `bge-reranker-base-quantized`). The Cross-Encoder compares the original LeetCode problem text directly against the chunk text, assigning a highly accurate final relevance score (0.0 to 1.0) in under 500ms.

### 7.2 Context Compression
We strictly enforce a **4,000 token limit** for the final RAG payload to prevent overwhelming the Script Generator LLM. If the top reranked chunks exceed 4,000 tokens, the lowest-scoring chunks are truncated.

---

# 8. Deduplication & Context Ordering

### 8.1 Deduplication (Parent-Child Resolution)
- If chunks overlap (e.g., Chunk 2 and Chunk 3 from the same article were both retrieved), they are automatically merged into a single contiguous block to save tokens.
- If more than 3 Child chunks from the same Parent document are in the top results, they are discarded and replaced by the single Parent chunk to provide broader context.

### 8.2 Context Ordering
LLMs suffer from the "Lost in the Middle" phenomenon (they pay more attention to the very beginning and very end of their prompt). 
- **Chronological Sorting:** We re-order the final selected chunks not by their similarity score, but by their original document order. Theory chunks are placed first, Code chunks in the middle, and Complexity proofs at the end. This provides a natural, textbook-like reading flow for the LLM.

---

# 9. Output Formatting

The final list of `Node` objects is packaged into the `RAGContext` dataclass as defined in the Data Models.

```python
# The payload injected into the Script Generator prompt
{
  "slug": "longest-substring-without-repeating-characters",
  "query_used": "Sliding Window HashMap time complexity visual analogy",
  "total_chunks_searched": 12540,
  "retrieval_time_ms": 412.5,
  "retrieved_at": "2026-07-22T12:00:00Z",
  "retrieved_chunks": [
    {
      "content": "A sliding window is an abstract concept...",
      "source_file": "patterns/sliding_window.md",
      "relevance_score": 0.94,
      "chunk_index": 1
    },
    ...
  ]
}
```
This final structured context guarantees the LLM has all the domain-specific ammunition required to write a technically flawless, highly educational video script.
