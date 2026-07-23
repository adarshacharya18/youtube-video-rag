# Phase02/11_Metadata_Design.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Metadata Schema Definition](#2-metadata-schema-definition)
3. [Schema Categories Explained](#3-schema-categories-explained)
4. [Validation Strategy](#4-validation-strategy)
5. [Filtering & Retrieval Logic](#5-filtering--retrieval-logic)

---

# 1. Executive Summary

This document strictly defines the metadata schema attached to every chunk inside the ChromaDB vector store. Because vector similarity search is blunt, robust metadata is the primary mechanism the pipeline uses to surgically filter, sort, and rerank educational context. This schema guarantees that the Script Generator LLM receives the correct language, the appropriate difficulty context, and the optimal pedagogical level.

---

# 2. Metadata Schema Definition

Every Markdown file in the Knowledge Base MUST contain a YAML Frontmatter block conforming to the following structure. During ingestion, LlamaIndex automatically propagates this document-level metadata down to every child chunk.

```yaml
---
algorithm: "Dijkstra"
difficulty: "hard"
topic: "graph_theory"
pattern: "shortest_path"
language: "cpp"
complexity:
  time: "O(V + E log V)"
  space: "O(V)"
source: "author_notes"
tags: ["greedy", "priority_queue", "weighted_graph"]
importance: 0.95
educational_level: "advanced"
version: "1.0.0"
relationships: ["bfs", "bellman_ford", "a_star"]
visual_assets: ["/assets/graphs/dijkstra_step1.png"]
---
```

---

# 3. Schema Categories Explained

### 3.1 Core Categorization
- **Algorithm:** The explicit name of the algorithm (e.g., `Dijkstra`, `Knapsack`). Used for direct exact-match keyword boosting.
- **Topic:** The broader computer science domain (e.g., `graph_theory`, `dynamic_programming`).
- **Pattern:** The specific LeetCode/DSA pattern used to solve the problem (e.g., `sliding_window`, `two_pointers`).
- **Tags:** An array of auxiliary concepts (e.g., `["hash_table", "prefix_sum"]`) mimicking LeetCode's tagging system.
- **Visual Assets:** An array of absolute paths pointing to local static image files (e.g., `["/assets/graphs/dijkstra_step1.png"]`) used to ground the LLM's visual layout.

### 3.2 Technical Constraints
- **Difficulty:** (`easy`, `medium`, `hard`). Ensures the LLM doesn't over-explain a trivial concept on a Hard problem, or under-explain a complex concept on an Easy problem.
- **Language:** (`cpp`, `python`, `agnostic`). Crucial for filtering. If the pipeline is generating a C++ video, `python` chunks must be strictly excluded.
- **Complexity:** The canonical Time and Space Big-O limits. Used to ground the LLM and prevent math hallucinations.

### 3.3 Provenance & Scoring
- **Source:** (`author_notes`, `wikipedia`, `cppreference`, `leetcode_editorial`). Determines the intrinsic trustworthiness of the chunk.
- **Importance:** A float `[0.0 - 1.0]`. Used by the Reranker to break ties between two semantically identical chunks. A foundational rule (e.g., "Always check for null pointers") gets a `1.0`.
- **Educational Level:** (`beginner`, `intermediate`, `advanced`). Allows dynamic prompt targeting based on the target YouTube audience demographic.
- **Version:** Tracks iterations of an explanation. If an animation style for `sliding_window` is revamped, the version bumps to `1.1.0`.

### 3.4 Relational Constraints
- **Relationships:** An array of explicit links to other algorithms (e.g., `["bfs", "a_star"]`). If a viewer needs to understand BFS to understand Dijkstra, this field triggers the retriever to fetch a small `bfs` chunk as prerequisite context.

---

# 4. Validation Strategy

Malformed metadata breaks SQL/ChromaDB filtering. To prevent this, metadata is strictly validated before ingestion.

### 4.1 The Linter Pipeline
A pre-commit hook and an ingestion check execute a Python Pydantic validation script:
1. **Schema Check:** Extracts the YAML frontmatter and parses it through a `KnowledgeMetadata` Pydantic model.
2. **Enum Enforcement:** Ensures `difficulty` is strictly one of `["easy", "medium", "hard"]`. Ensures `language` is in `["cpp", "python", "java", "agnostic"]`.
3. **Type Checking:** Prevents arrays from being passed as strings (e.g., `tags: "greedy"` instead of `tags: ["greedy"]`).
4. **Rejection:** If validation fails, the ingestion engine throws a `CriticalError`, halting the ingestion of that specific file and printing a clear terminal error for the developer.

---

# 5. Filtering & Retrieval Logic

ChromaDB uses SQLite under the hood to perform exact-match filtering on these metadata fields *before* running the HNSW vector search. This drastically reduces the search space and improves latency and accuracy.

### 5.1 Hard Exclusions (WHERE clause)
When querying for a Medium Sliding Window problem in C++:
```python
filters={
    "$and": [
        {"language": {"$in": ["cpp", "agnostic"]}},
        {"pattern": {"$eq": "sliding_window"}}
    ]
}
```
*Effect:* Instantly drops all Python-specific code chunks and all Graph/Tree chunks, even if the user query happened to contain the word "tree".

### 5.2 Soft Boosting (Reranker)
Fields like `importance`, `educational_level`, and `difficulty` are not used for hard exclusions. Instead, they are passed to the Cross-Encoder Reranker layer.
- **Example:** The retriever grabs 10 chunks about Sliding Windows. The Reranker evaluates them and adds `+0.1` to the final score for any chunk where `chunk.metadata.importance > 0.9`.
- **Difficulty Alignment:** If the current video is targeting an Easy problem, the Reranker penalizes chunks marked `educational_level: "advanced"` by `-0.15`, preventing the script from becoming overly academic.
