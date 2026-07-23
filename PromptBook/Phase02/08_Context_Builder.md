# Phase02/08_Context_Builder.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Core Responsibilities](#2-core-responsibilities)
3. [Deduplication & Concept Merging](#3-deduplication--concept-merging)
4. [Logical Ordering & Educational Flow](#4-logical-ordering--educational-flow)
5. [Citation Preservation](#5-citation-preservation)
6. [Handling Conflicting Information](#6-handling-conflicting-information)
7. [Token Limit Enforcement](#7-token-limit-enforcement)
8. [Example Output](#8-example-output)

---

# 1. Executive Summary

This document specifies the design for the **Context Builder**, the final stage of the RAG Engine (Module 3). After the reranker has selected the top chunks, the Context Builder is responsible for synthesizing these isolated vector chunks into a single, cohesive, token-efficient payload (`RAGContext`). This payload is specifically formatted to guide the Script Generator (Module 4) without confusing it with redundancies or logical jumps.

---

# 2. Core Responsibilities

The Context Builder operates strictly as a data formatter and synthesizer. It does *not* generate new knowledge; it optimizes existing knowledge for LLM consumption.

- **Combine:** Aggregate multiple `Node` objects into one continuous string or structured JSON array.
- **Deduplicate:** Identify and remove overlapping sentences or identical code blocks.
- **Order:** Sort the information pedagogically (Theory -> Code -> Complexity), overriding the reranker's raw similarity score order.
- **Constrain:** Enforce strict token limits to prevent LLM context window overflow or attention degradation.

---

# 3. Deduplication & Concept Merging

Retrieved chunks often contain redundant definitions (e.g., two different chunks defining "Sliding Window").

### 3.1 Parent-Child Recombination
If the Context Builder detects that two child chunks (e.g., chunks 3 and 4) come from the exact same Markdown file and are contiguous, it mechanically merges them back into a single text block, removing the artificial chunk boundary.

### 3.2 Semantic Concept Merging (Future)
If two chunks from different sources cover the exact same concept with high semantic overlap (e.g., a Wikipedia chunk and a GFG chunk both explaining standard BFS), the Context Builder uses a lightweight heuristic (or a fast LLM pass) to keep the chunk with the highest reranker score and discard the other, rather than concatenating them.

---

# 4. Logical Ordering & Educational Flow

LLMs suffer from "Lost in the Middle" syndrome. The most important information must be placed at the beginning and the end of the context prompt. Furthermore, educational content must flow logically.

The Context Builder ignores the reranker score for final sorting and instead sorts chunks by their `content_type` and `header_path` metadata.

**The Canonical Educational Flow:**
1. **Definitions & Theory:** Broad concepts (e.g., "What is dynamic programming?").
2. **Visual Analogies:** Real-world comparisons.
3. **Pseudo-code / Logic:** The step-by-step algorithmic progression.
4. **Implementation / C++ Syntax:** Language-specific code blocks and STL usage.
5. **Complexity Analysis:** Mathematical proofs for Time/Space limits.
6. **Edge Cases & Pitfalls:** Common failure modes (placed at the very end so the LLM remembers to warn the viewer).

---

# 5. Citation Preservation

To ensure the Script Generator does not hallucinate facts, the Context Builder explicitly injects the source citation directly into the text block sent to the LLM.

**Format:**
```text
[Source: data/knowledge_base/patterns/two_pointers.md | Confidence: High]
The two-pointer technique involves...
```
*Why?* The Script Generator prompt explicitly instructs the LLM: *"Base your explanations strictly on the provided sources. If a source says O(N), do not say O(N log N)."*

---

# 6. Handling Conflicting Information

Occasionally, two sources may conflict (e.g., one source claims `std::sort` is exactly O(N log N), another claims it is O(N^2) worst case depending on the standard implementation).

- **Rule:** The Knowledge Base must act as a Single Source of Truth. The Context Builder must **never** pass unresolved conflicts to the Script Generator to avoid confusing the viewer.
- **Action:** If two retrieved chunks share identical topic tags but contain conflicting claims, the Context Builder drops the lower-scoring chunk entirely. The Knowledge Base Linter (Module 10) is ultimately responsible for ensuring contradictory theoretical claims are blocked before they ever enter ChromaDB.

---

# 7. Token Limit Enforcement

The final assembled context must never exceed **4,000 tokens** (approx. 16,000 characters). 

1. **Greedy Addition:** The Context Builder adds chunks to the payload in order of their Reranker Score.
2. **Hard Cutoff:** Once the `tiktoken` count hits 3,800 tokens, the Builder prepares to stop.
3. **Smart Truncation (Node Boundary):** If adding the next highly relevant chunk pushes the limit to 4,200, the Builder **drops the entire chunk**. It never slices a chunk in half, as doing so might sever a C++ function mid-block and severely corrupt the LLM's understanding of the code.

---

# 8. Example Output

Below is an example of the final synthesized string payload generated by the Context Builder and placed inside the `RAGContext.retrieved_chunks` array for the LLM.

```text
=== RAG KNOWLEDGE CONTEXT ===

[Source: patterns/sliding_window.md | Section: Theory]
A sliding window is an extension of the two-pointer approach where the two pointers define a "window" of elements. The window expands by moving the right pointer and contracts by moving the left pointer.

[Source: patterns/sliding_window.md | Section: Visual Analogy]
Imagine a physical rectangular frame sliding over an array of numbers. As the frame moves right, a new number enters the frame, and the oldest number exits.

[Source: cpp_docs/unordered_map.md | Section: Syntax & Complexity]
In C++, `std::unordered_map` provides average O(1) time complexity for insertions and lookups. However, in the worst case (heavy hash collisions), it degrades to O(N).
```

This perfectly ordered, strictly bounded, citation-backed context guarantees the Script Generator has exactly what it needs to write an authoritative, educational video script.
