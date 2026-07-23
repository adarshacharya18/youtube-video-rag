# Phase02/10_Knowledge_Base.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Knowledge Categories](#2-knowledge-categories)
3. [Organization & Directory Structure](#3-organization--directory-structure)
4. [Metadata & Tagging Schema](#4-metadata--tagging-schema)
5. [Relationships & Cross-Linking](#5-relationships--cross-linking)
6. [Growth Strategy](#6-growth-strategy)
7. [Maintenance & Quality Control](#7-maintenance--quality-control)

---

# 1. Executive Summary

This document outlines the architecture, taxonomy, and lifecycle of the **Educational Knowledge Base (KB)**. The KB is the literal "brain" of the RAG system. It is a highly structured, Git-versioned repository of Markdown files that dictates *how* the pipeline teaches algorithms. It moves the system from generating generic, Wikipedia-style summaries to producing highly engaging, visually rich, and pedagogically sound YouTube scripts.

---

# 2. Knowledge Categories

The KB is segmented into explicit categories to satisfy the diverse retrieval needs of the pipeline:

### 2.1 Theoretical Foundations
- **Algorithms & Patterns:** Core definitions (e.g., "What is Dijkstra's?", "How does a Sliding Window work?").
- **Complexities:** Rigorous Big-O mathematical proofs for both Time and Space.

### 2.2 Pedagogical Enhancements
- **Analogies:** Real-world comparisons (e.g., "A Queue is like a line at a coffee shop").
- **Visualizations & Animations:** Directives for Manim (e.g., "Highlight the active pointer in RED, fade out processed nodes in GREY").
- **Visual Assets:** Absolute paths or references to static `.png` / `.svg` diagrams stored in a localized `assets/` directory, serving as direct topological references for the Script Generator when describing trees or graphs.

### 2.3 Practical Application
- **Examples:** Step-by-step trace walkthroughs of canonical problems.
- **Code Templates:** Bulletproof, idiomatic C++ boilerplates (e.g., standard Trie implementation) that the LLM must adhere to.

### 2.4 Interview Context
- **Edge Cases:** Off-by-one errors, integer overflow limits, empty array handling.
- **Common Mistakes:** "Gotchas" that trip up candidates in real interviews.
- **Interview Tips:** When to mention trade-offs, how to communicate stuck states.

---

# 3. Organization & Directory Structure

The KB exists as a physical directory structure on the local filesystem (`data/knowledge_base/`). This hierarchical layout aids the Semantic Chunker in assigning parent metadata automatically.

```text
data/knowledge_base/
├── patterns/
│   ├── sliding_window.md
│   ├── two_pointers.md
│   └── monotonic_stack.md
├── algorithms/
│   ├── graph/
│   │   ├── bfs.md
│   │   └── dijkstra.md
│   └── dynamic_programming/
│       ├── knapsack.md
│       └── state_machine.md
├── complexities/
│   ├── master_theorem.md
│   └── amortized_analysis.md
├── visual_analogies/
│   ├── pointers_and_arrays.md
│   └── recursive_call_stacks.md
└── code_templates/
    ├── cpp_stl_cheatsheet.md
    └── disjoint_set_union.md
```

Each Markdown file utilizes explicit H2 (`##`) and H3 (`###`) headers that map directly to the Knowledge Categories (Section 2) to ensure perfect chunking boundaries.

---

# 4. Metadata & Tagging Schema

For the Retrieval Pipeline to effectively filter context, every Markdown file must include a YAML Frontmatter block.

**Example `sliding_window.md` Frontmatter:**
```yaml
---
topic: "sliding_window"
domain: "pattern"
difficulty: "medium"
related_tags: ["array", "string", "hash_table"]
author_confidence: 0.95
---
```

When ingested, ChromaDB maps this YAML directly into its SQLite metadata store, allowing the Orchestrator to execute strict queries like: 
`WHERE domain="pattern" AND "array" IN related_tags`.

---

# 5. Relationships & Cross-Linking

Algorithmic concepts are rarely isolated. The KB relies on explicit cross-linking to establish relationships, helping the Context Builder merge related concepts.

- **Explicit References:** A document on `dijkstra.md` will explicitly mention `[[priority_queue]]` or `[[bfs]]`. 
- **Retrieval Impact:** While traversing the knowledge base, if the vector search detects these explicit bracketed keywords, it naturally pulls in the related documents via dense embedding similarity, seamlessly providing prerequisite knowledge without requiring a secondary keyword database.

---

# 6. Growth Strategy

The Knowledge Base is designed to scale iteratively without human bottlenecking:

1. **Bootstrap Phase (Manual):** Seed the KB with high-quality, manually curated notes for the top 15 most common DSA patterns (Sliding Window, Two Pointers, BFS, DFS, etc.).
2. **Automated Expansion (LLM-Driven):** Run an offline background script that feeds high-quality Wikipedia or CP-Algorithms pages into an LLM, prompting it to refactor the raw text into our specific YAML/Markdown format.
3. **Feedback Loop (Analytics):** If the pipeline consistently generates sub-par scripts for "Bit Manipulation" problems (detected via user feedback or low retention metrics), the developer manually injects a `bit_manipulation.md` file filled with fresh analogies and templates. The system incrementally re-indexes and instantly improves on the next run.

---

# 7. Maintenance & Quality Control

Because the LLM blindly trusts the KB, erroneous information here propagates globally.

### 7.1 Version Control
The entire `data/knowledge_base/` directory is tracked via Git. This allows developers to diff changes, rollback regressions in educational quality, and branch experimental visual analogy directives.

### 7.2 Linter Validation
Before the ingestion pipeline executes, a local Python linter (`src.rag.kb_linter`) parses the markdown files to enforce strict quality controls:
- **Schema Validation:** Ensures YAML Frontmatter exists and matches the Pydantic schema (including `visual_assets` paths).
- **Code Enforcement:** Verifies that all code blocks have language tags (`cpp`).
- **Header Structure:** Checks that H2 headers map to acceptable categories (e.g., throwing an error if it sees `## My Thoughts` instead of `## Educational Insights`).
- **Single Source of Truth Enforcement:** The linter scans across all files within a specific `topic` tag and strictly throws a `ConflictError` if it detects competing time/space complexities (e.g., two files asserting different Big-O for `sliding_window`). This guarantees the Context Builder never retrieves contradictory theories.

### 7.3 Deprecation
Algorithmic theory rarely changes, but visual preferences do. If a specific Manim animation style becomes outdated, the `visual_analogies` files are updated, the file modification time (`mtime`) is bumped, and the ingestion engine automatically deletes the old chunks and re-embeds the new directives.
