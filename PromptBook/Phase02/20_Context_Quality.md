# Phase02/20_Context_Quality.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Evaluation Metrics & Heuristics](#2-evaluation-metrics--heuristics)
3. [Scoring Architecture](#3-scoring-architecture)
4. [Automatic Repair & Filtering](#4-automatic-repair--filtering)
5. [Fallback Mechanisms](#5-fallback-mechanisms)

---

# 1. Executive Summary

Even with advanced reranking and logical context building, vector retrieval can occasionally pull together a payload that is semantically relevant but pedagogically disastrous (e.g., redundant definitions, contradictory math proofs, or missing core dependencies). 

The **Context Quality Assurance (QA) System** operates as the final tollgate before the context is handed off to the Educational Reasoning Engine (or Script Generator). It analyzes the assembled `RAGContext`, computes strict quality scores, and attempts automatic repair. If the context is unsalvageable, it halts the pipeline, preventing the LLM from generating an expensive, hallucinatory script.

---

# 2. Evaluation Metrics & Heuristics

The QA system evaluates the payload across 9 distinct dimensions. Some metrics are deterministic (Python heuristics), while others require a fast, lightweight LLM judge (e.g., `gemini-1.5-flash`).

### 2.1 Deterministic Metrics (Heuristics)
- **Token Efficiency:** Calculates the ratio of unique algorithmic keywords to total tokens. If the ratio is very low, the context is bloated with filler text.
- **Source Credibility:** Evaluates the `source` metadata. A payload consisting entirely of `user_notes` without any authoritative `cppreference` or `curated_patterns` chunks triggers a warning.
- **Difficulty Alignment:** Checks if the difficulty of the retrieved chunks matches the `ScrapedProblem`. (e.g., A "Beginner" array chunk being used to explain a "Hard" DP array problem results in a penalty).
- **Educational Flow:** Verifies that the Context Builder correctly ordered the chunks (Theory -> Analogy -> Code -> Complexity). If Code appears before Theory, the flow is broken.

### 2.2 Semantic Metrics (LLM / Cross-Encoder)
- **Redundancy:** Uses sentence-transformers to check if any two chunks in the payload have a similarity > 0.95. If so, they are saying the exact same thing.
- **Contradictions:** A fast LLM pass scans the chunks for conflicting factual claims (e.g., Chunk A says Space is O(N), Chunk B says Space is O(1)).
- **Coverage & Completeness:** Does the context address the *entire* LeetCode problem, or did it only retrieve chunks about the helper function?
- **Missing Concepts (Graph Check):** The QA system cross-references the Knowledge Graph. If the graph states `Dijkstra REQUIRES PriorityQueue`, but no Priority Queue chunk is in the context, a concept is missing.

---

# 3. Scoring Architecture

Every metric is graded on a scale of `0.0` to `1.0`. These scores are aggregated into a final **Context Health Index (CHI)**.

| Metric | Weight | Grade (Example) |
|---|---|---|
| Contradictions | 0.25 (Critical) | 1.0 (No conflicts) |
| Missing Concepts | 0.20 (High) | 0.5 (Missing 1 concept) |
| Redundancy | 0.15 (Med) | 0.8 (Minor overlap) |
| Token Efficiency | 0.10 (Low) | 0.7 (Slightly bloated) |
| **Total CHI** | **1.00** | **0.82 / 1.00** |

**Thresholds:**
- **`CHI > 0.80`:** PASS. Proceed to Reasoning Engine.
- **`CHI 0.60 - 0.79`:** REPAIR. Trigger Automatic Repair.
- **`CHI < 0.60`:** FAIL. Trigger Fallback.

---

# 4. Automatic Repair & Filtering

If the context falls into the REPAIR threshold, the QA system does not immediately fail the pipeline. It attempts to surgically fix the `RAGContext` object.

### 4.1 Redundancy Filtering
If the redundancy metric flags Chunk #3 and Chunk #5 as >95% similar, the QA system drops the chunk with the lower original Reranker score, instantly freeing up tokens.

### 4.2 Contradiction Pruning
Because the Knowledge Base Linter (Module 10) should have prevented conflicts from entering ChromaDB, any contradiction found here is a severe anomaly. The QA system applies a **Trust Priority** filter:
- It keeps the chunk from the more authoritative source (e.g., `curated_algorithms` > `wikipedia_scrape`).
- It drops the conflicting, lower-trust chunk entirely.

### 4.3 Missing Concept Injection
If a prerequisite concept is missing (e.g., the graph requires `Heap` but it's not there), the QA system makes an emergency, targeted micro-query to ChromaDB: `SELECT top 1 WHERE topic="Heap" AND content_type="Theory"`. It forcibly prepends this chunk to the context.

*Note: After a repair is made, the CHI score is recalculated. If it clears 0.80, the pipeline proceeds.*

---

# 5. Fallback Mechanisms

If a context scores below 0.60 (or fails to repair above 0.80), the system executes a hard fallback.

1. **The "Cold Reboot" Query:** 
   The Orchestrator is instructed to discard the complex rewritten queries and try one final time using just the raw Problem Title as a dense vector search, bypassing all hybrid/graph logic.
2. **Context-Free Degradation:**
   If the reboot fails, the pipeline strips the RAG context entirely. It passes the LeetCode problem to the Reasoning Engine with a strict system flag: `[WARNING: NO KB CONTEXT AVAILABLE. RELY ON BASE WEIGHTS. KEEP EXPLANATION HIGH-LEVEL TO AVOID HALLUCINATION]`.
3. **Quarantine:**
   The failed LeetCode problem slug and the rejected context payload are dumped to `data/logs/quarantine/`. The pipeline moves to the next LeetCode problem in the queue. A developer can review the quarantine log later to figure out why the Knowledge Base failed to support that specific problem.
