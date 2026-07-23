# Phase02/03_Chunking_Strategy.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core Chunking Parameters](#2-core-chunking-parameters)
3. [Primary Chunking Strategies](#3-primary-chunking-strategies)
    - [Semantic Chunking](#31-semantic-chunking-markdown-headers)
    - [Parent-Child Chunking](#32-parent-child-chunking-auto-merging)
    - [Recursive Character Chunking](#33-recursive-character-chunking)
4. [Domain-Specific Content Handling](#4-domain-specific-content-handling)
    - [Code & Pseudo-Code](#41-code--pseudo-code-chunking)
    - [Table Chunking](#42-table-chunking)
    - [Mathematical Formulas](#43-mathematical-formulas)
5. [Strategy Selection Guide](#5-strategy-selection-guide)
6. [Tradeoffs & Best Practices](#6-tradeoffs--best-practices)
7. [Examples](#7-examples)

---

# 1. Executive Summary

This document defines the chunking strategies used by the RAG Ingestion Pipeline to parse educational Data Structures and Algorithms (DSA) content. Because educational content is highly structured (theory -> code -> complexity analysis), naive character splitting destroys context. 

Our strategy emphasizes **Semantic Chunking** and **Parent-Child** relationships to ensure the Script Generator LLM receives perfectly scoped, highly relevant context without losing the surrounding narrative.

---

# 2. Core Chunking Parameters

Regardless of the strategy used, the following baseline parameters apply:

- **Window Size (Chunk Size):** 512 tokens (~2000 characters). This size is optimal for dense algorithmic explanations. It is large enough to hold a complete C++ function or a full complexity proof, but small enough to maintain a highly specific embedding vector.
- **Overlap:** 15% (75 tokens). Overlap prevents critical sentences from being sliced in half across chunk boundaries, ensuring continuous context for the LLM.
- **Metadata Preservation:** Every chunk inherently inherits the metadata of its parent document. Crucially, the chunking mechanism injects local metadata:
  - `Header Path`: e.g., `["Graph Theory", "Dijkstra's Algorithm", "Time Complexity"]`
  - `Chunk Index`: `[2/5]`
  - `Content Type`: `code_block`, `table`, `text`

---

# 3. Primary Chunking Strategies

### 3.1 Semantic Chunking (Markdown Headers)
**Mechanism:** Uses LlamaIndex's `MarkdownNodeParser`. It parses the AST of the Markdown document and creates chunks explicitly bounded by headers (`#`, `##`, `###`).
**When to use:** Curated Notes, heavily formatted Algorithm Articles, LeetCode Editorials.
**Why:** Algorithms are inherently hierarchical. A `## Space Complexity` section should be its own distinct chunk, perfectly embedded to answer "What is the space complexity?" queries.

### 3.2 Parent-Child Chunking (Auto-Merging)
**Mechanism:** Large documents are parsed into a hierarchy. Small, highly specific "Child" chunks (e.g., 128 tokens) are embedded and stored in ChromaDB. When retrieval hits a high concentration of Child chunks from the same Parent (e.g., a 1024-token section), the retriever automatically swaps out the children and returns the entire Parent chunk to the LLM.
**When to use:** Deep-dive theoretical articles and Wikipedia pages.
**Why:** It provides the best of both worlds: the extreme retrieval precision of small embeddings, combined with the comprehensive generative context of large texts.

### 3.3 Recursive Character Chunking
**Mechanism:** The fallback approach. It attempts to split text using a prioritized list of separators: `["\n\n", "\n", ".", " "]`. It only splits at lower-priority separators if the higher-priority one results in a chunk exceeding the Window Size.
**When to use:** Unstructured TXT files, poorly formatted PDFs, legacy documentation.
**Why:** Guarantees that chunks never exceed token limits while doing its best to respect natural paragraph and sentence boundaries.

---

# 4. Domain-Specific Content Handling

### 4.1 Code & Pseudo-Code Chunking
**Rule:** Code blocks (` ```cpp ... ``` `) must **never** be split in half.
**Implementation:** The `CodeSplitter` (built into LlamaIndex) uses Tree-sitter to parse the AST of the code. If a file is too large, it splits code at function or class boundaries, never inside a `while` loop.
**Metadata Added:** `{"language": "cpp", "signatures": ["void dfs(int node)"]}`

### 4.2 Table Chunking
**Rule:** Markdown tables must be preserved in their entirety. If a table exceeds the window size, it is flattened into a descriptive list format before chunking.
**Implementation:** A custom pre-processor detects `|---|---|` structures. Small tables remain intact.
**Why:** LLMs struggle to read tables split across two different chunks.

### 4.3 Mathematical Formulas
**Rule:** LaTeX blocks (`$$ ... $$` or `$ ... $`) must be kept intact. 
**Implementation:** The semantic chunker treats `$$` blocks identically to code blocks.
**Why:** Splitting `O(V + E)` into two chunks destroys the algorithmic time complexity definition.

---

# 5. Strategy Selection Guide

| Source Material | Primary Strategy | Fallback Strategy | Reasoning |
|---|---|---|---|
| **Author's Notes (.md)** | Semantic (Markdown) | Recursive | Notes are naturally organized by headers. |
| **Wikipedia Articles** | Parent-Child | Recursive | Wiki pages are long; precise search is needed, but broad context is required for generation. |
| **C++ Documentation** | Code (AST) Splitter | Semantic | Syntax and method definitions must remain structurally intact. |
| **PDF Textbooks** | Recursive Character | None | PDFs lack reliable header tags post-OCR. |
| **LeetCode Editorial** | Semantic (Markdown) | Code Splitter | Editorials blend text and code seamlessly under headers. |

---

# 6. Tradeoffs & Best Practices

### Best Practices
1. **Metadata is King:** The more structural metadata attached to a chunk (e.g., "This chunk is under the `## Optimization` header"), the better the LLM can integrate it into the video script.
2. **Prioritize Structural Boundaries over Token Limits:** It is better to have a chunk of 600 tokens containing a full function than two chunks of 300 tokens where the function is torn in half.

### Tradeoffs
| Strategy | Pros | Cons |
|---|---|---|
| **Semantic** | Perfect contextual boundaries; highly educational. | Fails completely on unstructured text; can create massively oversized chunks if a section lacks subheaders. |
| **Parent-Child** | Extreme retrieval accuracy; rich LLM generation context. | Doubles the embedding cost/time (must embed both parents and children); increases ChromaDB storage size. |
| **Recursive** | Robust; never exceeds token limits; works on any text. | Context-blind; can split an explanation mid-thought, confusing the Script Generator. |

---

# 7. Examples

### Example: Semantic Chunking Success

**Raw Input:**
```markdown
## Breadth-First Search
BFS is used to find the shortest path in an unweighted graph.
### Time Complexity
The time complexity is O(V + E) because we visit every vertex and edge once.
```

**Resulting Chunks:**
- **Chunk 1:** `BFS is used to find the shortest path in an unweighted graph.` (Metadata: Header=`Breadth-First Search`)
- **Chunk 2:** `The time complexity is O(V + E) because we visit every vertex and edge once.` (Metadata: Header=`Breadth-First Search > Time Complexity`)

*Retrieving Chunk 2 instantly answers complexity queries with perfect precision.*
