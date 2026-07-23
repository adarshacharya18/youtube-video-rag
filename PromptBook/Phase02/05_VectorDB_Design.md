# Phase02/05_VectorDB_Design.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Database Architecture Diagram](#2-database-architecture-diagram)
3. [Collections & Namespaces](#3-collections--namespaces)
4. [Persistence & Storage](#4-persistence--storage)
5. [Indexing & Similarity Search](#5-indexing--similarity-search)
6. [Metadata & Filtering](#6-metadata--filtering)
7. [Lifecycle Management (Updates, Deletion, Versioning)](#7-lifecycle-management-updates-deletion-versioning)
8. [Backup & Snapshots](#8-backup--snapshots)
9. [Future Scaling](#9-future-scaling)

---

# 1. Executive Summary

This document specifies the Vector Database layer of the RAG engine using **ChromaDB**. The architecture emphasizes an "offline-first" methodology, leveraging Chroma's local `PersistentClient` to completely eliminate network dependencies during pipeline execution. The design ensures high-speed similarity search using HNSW indexes, strictly versioned collections to prevent vector contamination, and robust metadata filtering to guarantee domain-specific context retrieval.

---

# 2. Database Architecture Diagram

```mermaid
graph TD
    subgraph ChromaDB Local Instance
        A[PersistentClient] --> B(Collection: educational_kb_gemini_v1)
        A --> C(Collection: leetcode_meta_gemini_v1)
        
        B --> D{HNSW Vector Index}
        B --> E[(SQLite Metadata Store)]
        
        C --> F{HNSW Vector Index}
        C --> G[(SQLite Metadata Store)]
    end

    subgraph Orchestrator (Runtime)
        H[Query Embedding] --> I[Similarity Search]
        J[Metadata Filters] --> I
        I --> D
        I --> E
    end

    subgraph Ingestion Pipeline (Offline)
        K[Chunk Embeddings] --> L[Upsert / Delete API]
        L --> B
    end
```

---

# 3. Collections & Namespaces

ChromaDB organizes data into logical namespaces called **Collections**. We strictly separate knowledge domains into distinct collections to optimize search space and avoid cross-contamination of contexts.

### Defined Collections:
1. `educational_kb_{model}_{version}`: Contains the core algorithmic theory, complexity proofs, and C++ syntax guides. (e.g., `educational_kb_gemini_004_v1`).
2. `leetcode_meta_{model}_{version}`: Contains editorial solutions and constraints specific to LeetCode problems.

**Why?** If the Script Generator specifically needs the standard time complexity for Dijkstra's, searching *only* the `educational_kb` collection prevents the retrieval of a highly similar but irrelevant LeetCode problem description.

---

# 4. Persistence & Storage

- **Mode:** `chromadb.PersistentClient(path="data/chroma_db")`
- **Engine:** Chroma uses SQLite for metadata and document storage, and hnswlib for the vector index.
- **Location:** The database is stored inside the project's root `data/` directory. This ensures the database is portable, easily backed up, and does not pollute the OS environment.
- **Memory Footprint:** The local instance loads the HNSW index into RAM upon the first query. For 50,000 chunks of 768D vectors, RAM usage peaks at ~250 MB.

---

# 5. Indexing & Similarity Search

- **Algorithm:** HNSW (Hierarchical Navigable Small World). This provides Approximate Nearest Neighbor (ANN) search, guaranteeing sub-100ms retrieval times locally.
- **Distance Metric:** **Cosine Similarity**. Since Gemini embeddings are optimized for Cosine Distance, the collection must be initialized with `metadata={"hnsw:space": "cosine"}`. 
- **Search Execution:** LlamaIndex abstracts the search. Given a query vector, ChromaDB traverses the HNSW graph to find the `top_k=5` closest vectors based on the cosine angle, then returns the associated text documents.

---

# 6. Metadata & Filtering

Pure semantic search is powerful but blunt. We use ChromaDB's `where` filtering to enforce strict logical bounds before the vector similarity is even calculated.

### Metadata Schema
Every chunk stored in ChromaDB carries a strictly typed metadata dictionary:
```json
{
  "source_type": "wikipedia", // "notes", "cpp_docs"
  "category": "graph_theory", 
  "language": "cpp",
  "difficulty": "hard",
  "chunk_index": 4
}
```

### Filtering Example
When retrieving context for a Hard Graph problem in C++:
```python
retriever = index.as_retriever(
    similarity_top_k=5,
    filters=MetadataFilters(
        filters=[
            ExactMatchFilter(key="category", value="graph_theory"),
            ExactMatchFilter(key="language", value="cpp")
        ]
    )
)
```
*Effect:* ChromaDB first uses SQLite to filter out all non-Graph, non-C++ chunks, then performs the HNSW search on the remaining subset. This drastically reduces hallucinations and improves search speed.

---

# 7. Lifecycle Management (Updates, Deletion, Versioning)

### 7.1 Updates & Deletion
ChromaDB supports `upsert` and `delete` via unique string IDs.
- **ID Format:** `hash(filepath)_chunkIndex` (e.g., `a7f9b2..._04`).
- **Deletion:** When the ingestion pipeline detects a modified Markdown file, it calculates the old IDs and issues a `collection.delete(ids=[...])` command before re-embedding the new file. This prevents stale ghost-chunks from lingering in the vector space.

### 7.2 Versioning Strategy
Vector databases cannot easily migrate dimensional spaces (e.g., switching from 768D to 384D). Therefore, we version at the **Collection level**.
- If we switch from Gemini to HuggingFace, a new collection `educational_kb_huggingface_v1` is created.
- The pipeline points to the new collection.
- The old collection is dropped (`client.delete_collection("educational_kb_gemini_004_v1")`) to reclaim disk space.

---

# 8. Backup & Snapshots

Because the ingestion pipeline costs API credits, the compiled ChromaDB state is valuable.

### Snapshots
- **Mechanism:** Since ChromaDB's `PersistentClient` is fundamentally just SQLite files and Parquet logs residing in `data/chroma_db`, taking a snapshot is as simple as creating a `.tar.gz` archive of the directory.
- **Schedule:** A snapshot is generated automatically by a background script every Sunday, or manually via a CLI command prior to a massive batch ingestion.

### Restoration
To recover from a corrupted index, the pipeline extracts the `.tar.gz` over the `data/chroma_db` directory. ChromaDB will instantly recognize the restored state on the next boot.

---

# 9. Future Scaling

The current architecture is highly optimized for a single-machine, offline-first pipeline. If the system scales to a distributed cloud model (e.g., multiple Orchestrators running concurrently across different nodes):

1. **Client/Server Migration:** The local `PersistentClient` will be swapped for `chromadb.HttpClient(...)`, pointing to a centralized ChromaDB Docker container.
2. **Concurrent Access:** The Dockerized Chroma server handles concurrent read/write locks, preventing database corruption if two Orchestrators attempt to query/ingest simultaneously.
3. **Tenant Scaling:** If the platform opens to multiple users (e.g., users uploading their own notes), Chroma's `Tenant` and `Database` namespaces will be activated to logically isolate User A's vectors from User B's vectors without needing separate containers.
