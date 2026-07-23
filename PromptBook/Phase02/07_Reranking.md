# Phase02/07_Reranking.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Bi-Encoder vs. Cross-Encoder Architecture](#2-bi-encoder-vs-cross-encoder-architecture)
3. [Metadata & Domain Reranking](#3-metadata--domain-reranking)
   - [Educational Relevance](#31-educational-relevance)
   - [Difficulty Matching](#32-difficulty-matching)
   - [Pattern & Code Matching](#33-pattern--code-matching)
4. [Ranking Score & Thresholds](#4-ranking-score--thresholds)
5. [Failure Handling](#5-failure-handling)
6. [Tradeoffs](#6-tradeoffs)

---

# 1. Executive Summary

This document specifies the Reranking Strategy for the Retrieval-Augmented Generation (RAG) subsystem. Following the initial Vector Retrieval (which casts a wide net using Cosine Similarity), the reranking layer acts as a highly precise filter. It reorganizes the initial top 10 candidate chunks into the absolute best chunks by performing deep semantic comparisons and applying heuristic metadata boosts tailored for Data Structures and Algorithms (DSA) education.

---

# 2. Bi-Encoder vs. Cross-Encoder Architecture

### 2.1 Bi-Encoder (The Initial Fetch)
The initial retrieval phase uses a **Bi-Encoder** (Gemini `text-embedding-004`). 
- **How it works:** The user query and the document chunks are embedded separately into vectors, and their mathematical distance (Cosine Similarity) is calculated. 
- **Pros/Cons:** Extremely fast (can search millions of vectors in milliseconds) but semantically shallow because the query and document never "see" each other during the embedding process.

### 2.2 Cross-Encoder (The Reranker)
To achieve pinpoint accuracy while maintaining sub-500ms execution times on the CPU, the Reranking phase utilizes a local ONNX-quantized `int8` **Cross-Encoder** (e.g., `BAAI/bge-reranker-base-quantized`).
- **How it works:** The original query and the retrieved chunk are concatenated (`[CLS] Query [SEP] Chunk [SEP]`) and passed simultaneously through the Transformer layers.
- **Pros/Cons:** Highly accurate because attention mechanisms evaluate the exact contextual relationship between the query and the chunk. It is computationally expensive, hence why it is strictly limited to the top 10 chunks returned by the Bi-Encoder.

---

# 3. Metadata & Domain Reranking

After the Cross-Encoder assigns a baseline semantic score, the system applies domain-specific heuristic boosts to fine-tune the final order.

### 3.1 Educational Relevance
Chunks explicitly tagged in ChromaDB with `content_type="explanation"` or `content_type="analogy"` receive a **+0.1 boost** if the Script Generator is currently writing the `PROBLEM_STATEMENT` or `VISUAL_WALKTHROUGH` sections. Theoretical proofs receive boosts during the `COMPLEXITY_ANALYSIS` generation.

### 3.2 Difficulty Matching
A "Hard" dynamic programming problem requires deeper theoretical context than an "Easy" two-pointer problem. 
- If `ScrapedProblem.difficulty == "HARD"`, chunks with metadata `difficulty_level="advanced"` (e.g., state-machine DP explanations) receive a **+0.15 boost**. 
- Conversely, basic introductory chunks are slightly penalized to save token space for advanced theory.

### 3.3 Pattern Matching
Using the `TagKnowledge.primary_pattern` (from Module 2), the reranker heavily favors chunks that explicitly teach that pattern. 
- If the pattern is `Sliding Window`, chunks containing the metadata `primary_topic="sliding_window"` get a massive **+0.25 boost**.

### 3.4 Code Matching
To prevent the LLM from hallucinating standard library syntax, code blocks are prioritized based on the problem's language. 
- Since the pipeline normalizes on C++, chunks with `language="cpp"` containing AST-parsed code blocks (e.g., `std::priority_queue` syntax) receive a **+0.2 boost** during the `CODE_WALKTHROUGH` generation phase.

---

# 4. Ranking Score & Thresholds

The final ranking score is a composite of the Cross-Encoder semantic score and the Metadata heuristic boosts:

`Final Score = CrossEncoderScore(Query, Chunk) + MetadataBoosts`

- **Output Range:** Theoretically 0.0 to 1.5+ (Cross-Encoder usually outputs 0.0 to 1.0).
- **Absolute Threshold:** Any chunk with a `Final Score < 0.4` is immediately discarded. This ensures that if the knowledge base genuinely lacks information on a niche algorithm (e.g., "Dancing Links"), the system won't force irrelevant noise into the LLM context.
- **Top-K Cutoff:** After filtering by the threshold, only the top 10 chunks (or max 4,000 tokens) are passed to the `RAGContext`.

---

# 5. Failure Handling

Reranking relies on a local compute-heavy model (Cross-Encoder). 

- **Model Load Failure:** If the Cross-Encoder model fails to load into memory (e.g., OOM on the CPU/NPU), the reranker catches the `MemoryError`.
- **Graceful Degradation:** The system falls back to using the raw Cosine Similarity scores from the initial Vector Retrieval phase. The heuristic Metadata Boosts (Section 3) are still applied to these base scores.
- **Logging:** A `WARNING` is logged, and the pipeline continues uninterrupted without raising a `CriticalError`.

---

# 6. Tradeoffs

| Decision | Pros | Cons |
|---|---|---|
| **Local Cross-Encoder** | Eliminates API costs and latency for reranking; highly accurate semantic matching. | Consumes local RAM; using ONNX `int8` quantization prevents severe CPU bottlenecks, but still adds ~100-300ms latency compared to pure Bi-Encoder. |
| **Heuristic Metadata Boosts** | Guarantees educational alignment; ensures Hard problems get Hard theory. | Requires rigid metadata tagging during the ingestion pipeline; hardcoded boost values (`+0.15`) require manual tuning. |
| **Strict 0.4 Threshold** | Prevents LLM confusion by strictly blocking irrelevant context. | Risks returning an empty `RAGContext` if the query is poorly phrased, forcing the Script Generator to rely purely on internal LLM weights. |
| **Dynamic Section Targeting** | Highly token-efficient (e.g., only sends math proofs during the complexity section). | Requires the Script Generator to request context dynamically *per section*, which complicates Orchestrator logic compared to one massive upfront prompt. |
