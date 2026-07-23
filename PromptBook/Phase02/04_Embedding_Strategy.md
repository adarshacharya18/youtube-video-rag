# Phase02/04_Embedding_Strategy.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Embedding Model Specification](#2-embedding-model-specification)
3. [The Embedding Pipeline](#3-the-embedding-pipeline)
4. [Dimensionality & Storage](#4-dimensionality--storage)
5. [Batch Size & Performance](#5-batch-size--performance)
6. [Metadata Integration](#6-metadata-integration)
7. [Caching & Duplicate Detection](#7-caching--duplicate-detection)
8. [Update Strategy & Versioning](#8-update-strategy--versioning)
9. [Future Migration Path](#9-future-migration-path)

---

# 1. Executive Summary

This document defines the strategy for transforming parsed text chunks into mathematical vectors for semantic retrieval. The system standardizes on Google's **Gemini `text-embedding-004`** model due to its state-of-the-art performance on code and reasoning tasks, massive context window, and native integration within the project's existing Google ecosystem stack.

---

# 2. Embedding Model Specification

- **Primary Model:** `models/text-embedding-004`
- **Task Type Designation:** We explicitly use the `RETRIEVAL_DOCUMENT` task type during offline ingestion and the `RETRIEVAL_QUERY` task type during runtime search. This distinction optimizes the model's internal attention mechanism for asymmetric search tasks (short questions retrieving long documents).
- **Supported Languages:** Optimized for English natural language and C++/Python syntax.

---

# 3. The Embedding Pipeline

The pipeline abstracts the complexity of network calls and error handling away from the ingestion engine.

1. **Input Generation:** The chunking strategy yields a `Document` node containing the raw text and attached metadata dictionary.
2. **Batch Accumulation:** Nodes are held in a memory buffer until the designated `batch_size` is reached.
3. **API Invocation:** The LlamaIndex `GoogleGenAIEmbedding` class transmits the batch to the Gemini API over gRPC/REST. Exponential backoff is applied for HTTP 429 (Rate Limit) errors.
4. **Vector Attachment:** The returned float arrays are attached to the `embedding` property of the `Document` node.
5. **Persistence:** The nodes are committed to the local ChromaDB.

---

# 4. Dimensionality & Storage

- **Output Dimensions:** `text-embedding-004` natively outputs **768-dimensional** vectors.
- **Dimension Handling:** We will use the native 768 dimensions without truncation. 
- **Storage Calculations:** 
  - Each 768-dimensional vector (using 32-bit floats) consumes exactly 3,072 bytes (3 KB).
  - For an educational database of 50,000 algorithmic chunks, the raw vector payload is ~150 MB.
  - Coupled with ChromaDB's HNSW graph overhead and SQLite metadata storage, total disk usage stays comfortably under **500 MB**, perfectly suitable for lightweight local storage (`data/chroma_db`).

---

# 5. Batch Size & Performance

To maximize ingestion speed without violating API rate limits:

- **Batch Size:** Set to `100` documents per API call during ingestion.
- **Runtime Search:** Set to `1` (single query embedding) during the actual video pipeline execution.
- **Performance Expectation:** Embedding 10,000 chunks in batches of 100 via the Gemini API takes approximately 30-45 seconds, bound primarily by network I/O, rather than compute.

---

# 6. Metadata Integration

Embeddings capture semantic meaning, but pure similarity search often fails on algorithmic categorization (e.g., retrieving a Graph DFS implementation when the query was about Tree DFS). 

To solve this, metadata is embedded alongside the vector in ChromaDB for pre-filtering:
- `topic`: e.g., "Graph Theory"
- `language`: "cpp"
- `difficulty`: "Hard"

*Note:* We use **Metadata Filtering** at retrieval time (e.g., `WHERE language="cpp"`) rather than attempting to encode the language solely into the vector semantics.

---

# 7. Caching & Duplicate Detection

Re-embedding unchanged documents wastes API quotas and time.

1. **Document-Level Hash Cache:** A local SQLite cache tracks the SHA-256 hash of every source file. If the hash hasn't changed since the last run, the ingestion pipeline completely skips chunking and embedding.
2. **Node-Level Deduplication:** In the event that distinct documents contain identical chunks (e.g., a standard standard `swap()` implementation), LlamaIndex uses a node-level deduplication cache (`IngestionCache`) backed by a local Key-Value store. If the exact string exists in the cache, the API call is skipped and the cached vector is reused.

---

# 8. Update Strategy & Versioning

### 8.1 Vector Index Updates
The ChromaDB index is purely additive/destructive. There are no "in-place" vector mutations. If a source document changes:
1. The old `chunk_ids` associated with the document are deleted from ChromaDB.
2. The new document is chunked and embedded.
3. The new vectors are inserted.

### 8.2 Collection Versioning
ChromaDB organizes vectors into "Collections". We version collections by the embedding model used.
- **Current Collection Name:** `educational_kb_gemini_004`
- If we update the prompt engineering guidelines significantly or swap embedding models, we create a new collection (e.g., `educational_kb_gemini_005`) and re-index from scratch. This prevents vector space contamination (mixing 768D vectors from different models/versions).

---

# 9. Future Migration Path

While `text-embedding-004` provides phenomenal quality, long-term offline autonomy may dictate moving to local embeddings to eliminate API costs entirely.

**Migration Strategy:**
1. Update `RAGConfig.embedding_model` to point to a local model (e.g., HuggingFace `BAAI/bge-small-en-v1.5` which outputs 384D vectors).
2. The pipeline creates a new ChromaDB collection: `educational_kb_bge_small`.
3. The `index_knowledge_base` method executes, parsing all Markdown files and running them through the local CPU/NPU embedder.
4. Once completed, the Orchestrator config is flipped to read from the new collection. 
5. Because the pipeline leverages LlamaIndex's `BaseEmbedding` abstraction, changing the model requires exactly one line of code change in the module factory.
