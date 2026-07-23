# Phase02/14_RAG_Evaluation.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Quantitative Retrieval Metrics](#2-quantitative-retrieval-metrics)
3. [Qualitative Generation Metrics](#3-qualitative-generation-metrics)
4. [Domain-Specific Metrics (Educational)](#4-domain-specific-metrics-educational)
5. [Testing Methodology & Benchmark Datasets](#5-testing-methodology--benchmark-datasets)
6. [Continuous Evaluation (CI/CD)](#6-continuous-evaluation-cicd)

---

# 1. Executive Summary

This document defines the **RAG Evaluation Framework**, ensuring that the Retrieval-Augmented Generation subsystem operates deterministically and accurately. Because the pipeline generates educational content, hallucinations (e.g., falsely stating an algorithm is $O(N)$ instead of $O(N \log N)$) are catastrophic. This framework uses an "LLM-as-a-Judge" methodology alongside deterministic heuristics to continuously measure system health across retrieval accuracy, generation faithfulness, and token efficiency.

---

# 2. Quantitative Retrieval Metrics

These metrics evaluate the performance of the ChromaDB, the BM25/Vector search, and the Cross-Encoder Reranker, independently of the final Script Generator.

* **Recall (Top-K):** Measures whether the absolute *required* theoretical chunk (e.g., the exact definition of a Trie) is present anywhere within the retrieved top 10 chunks.
  * *Target:* > 95%
* **Precision:** Measures how many of the retrieved top 10 chunks were actually relevant to the LeetCode problem.
  * *Target:* > 80% (It's acceptable to retrieve slightly tangential context as long as it fits in the token window).
* **Coverage:** Measures the breadth of the Knowledge Base. If a user inputs a niche LeetCode problem (e.g., "Dancing Links"), does the database have *any* relevant chunks that clear the 0.75 Cosine threshold?
  * *Target:* > 90% across the top 500 LeetCode problems.
* **Latency:** The end-to-end time from receiving the `ScrapedProblem` to returning the formatted `RAGContext` dataclass.
  * *Target:* < 800ms (P95).

---

# 3. Qualitative Generation Metrics

These metrics evaluate how effectively the Script Generator LLM uses the retrieved context. They are scored using an "LLM-as-a-Judge" (e.g., prompting `gemini-1.5-pro` to blindly grade the output).

* **Faithfulness:** Does the generated video script rely *only* on the provided `RAGContext`? Or did the LLM hallucinate external information from its base weights?
* **Groundedness:** When the script makes a factual claim (e.g., "The space complexity is bounded by the recursion stack"), can that exact claim be traced back to a specific sentence in the retrieved Markdown chunks?
* **Hallucination Rate:** The percentage of generated scripts that contain mathematically or algorithmically false statements. 
  * *Target:* 0.0% (Strictly enforced via CI pipelines).

---

# 4. Domain-Specific Metrics (Educational)

Because this is a YouTube automation pipeline, standard RAG metrics are insufficient. We must measure *pedagogical* quality.

* **Educational Quality (1-5 Score):** An LLM judge evaluates the script for clarity, engaging pacing, use of analogies, and whether a beginner could understand the concept.
* **Context Utilization:** If the Context Builder provided 3,500 tokens of context, what percentage of those tokens actually influenced the final script? If 2,000 tokens are consistently ignored, the Reranker is wasting API tokens.
* **Token Efficiency:** The ratio of *Meaningful Insights* to *Input Tokens*. 
  * *Goal:* Maximize the script's educational density while minimizing the $ input cost to Gemini. We want highly targeted 1,000-token contexts, not sloppy 8,000-token dumps.

---

# 5. Testing Methodology & Benchmark Datasets

You cannot evaluate RAG without a golden dataset. We maintain a static benchmark suite locally.

### 5.1 The Benchmark Dataset (`data/eval/rag_bench.json`)
A curated JSON array of 50 canonical LeetCode problems representing diverse algorithms (Graphs, DP, Trees, Bit Manipulation).
Each entry contains:
- `slug`: e.g., `longest-palindromic-substring`
- `expected_chunks`: Array of Markdown filenames that *must* be retrieved (e.g., `dp_state_expansion.md`).
- `forbidden_chunks`: Array of chunks that indicate a failure if retrieved (e.g., `greedy_intervals.md`).
- `expected_complexity`: The mathematical Big-O string the LLM must generate.

### 5.2 The "LLM-as-a-Judge" Evaluator
We use `Ragas` or `TruLens` (or a custom wrapper) to run the evaluations offline. The evaluator LLM is given the `RAGContext`, the generated `VideoScript`, and a strict grading rubric, returning JSON scores for Faithfulness and Educational Quality.

---

# 6. Continuous Evaluation (CI/CD)

RAG evaluation is not a one-time test; it is deeply integrated into the development lifecycle.

### 6.1 PR Gating (The "Vibe Check")
Before a developer merges a change to the Prompt Assembly logic, the Reranker weights, or the Knowledge Base Markdown files:
1. A GitHub Action triggers `pytest tests/eval/`.
2. The pipeline runs a subset of 10 benchmark problems (to save API costs).
3. If **Recall** drops below 90% or the **Hallucination Rate** rises above 0%, the PR is blocked.

### 6.2 Nightly Full-Suite Run
Every night at 3:00 AM, the system runs the entire 50-problem benchmark suite. It outputs a `rag_eval_report_YYYYMMDD.json` file.

### 6.3 Regression Monitoring
The pipeline visualizes these daily JSON reports on a local dashboard (or terminal script). If the *Token Efficiency* degrades slowly over 3 weeks (indicating the database is getting bloated and pulling in too much garbage context), the developer is alerted to manually prune the Knowledge Base.
