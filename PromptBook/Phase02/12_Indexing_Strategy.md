# Phase02/12_Indexing_Strategy.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Indexing Workflows](#2-indexing-workflows)
   - [Initial Indexing](#21-initial-indexing)
   - [Incremental Indexing](#22-incremental-indexing)
   - [Background Indexing](#23-background-indexing)
   - [Complete Reindexing](#24-complete-reindexing)
3. [Lifecycle Management](#3-lifecycle-management)
   - [Duplicate Detection](#31-duplicate-detection)
   - [Updates & Deletions](#32-updates--deletions)
4. [Versioning Strategy](#4-versioning-strategy)
5. [Scheduling & Monitoring](#5-scheduling--monitoring)
6. [Performance Optimization](#6-performance-optimization)

---

# 1. Executive Summary

This document specifies the operational Indexing Strategy for the local ChromaDB vector store. Because vector embeddings incur API costs (via Gemini API) and consume time, the strategy heavily penalizes redundant work. The system employs intelligent hash-caching to ensure that only net-new or explicitly modified algorithmic knowledge is processed, chunked, and embedded into the database.

---

# 2. Indexing Workflows

### 2.1 Initial Indexing
- **Trigger:** First-time setup (`python -m src.rag.ingest --force-all`).
- **Process:** Iterates through the entire `data/knowledge_base/` directory. Parses every Markdown file, validates the metadata schema, chunks the text, invokes the Embedding API in max-size batches, and populates the fresh ChromaDB collection.
- **Output:** Generates the foundational `HashCache.sqlite` file, mapping exact file paths and their SHA-256 hashes to generated vector `chunk_ids`.

### 2.2 Incremental Indexing
- **Trigger:** Pre-pipeline runtime check or developer CLI command (`python -m src.rag.ingest --incremental`).
- **Process:** 
  1. Scans `data/knowledge_base/`.
  2. Computes the SHA-256 hash of every file.
  3. Compares hashes against the local `HashCache.sqlite`.
  4. Only processes files where `hash_cache[file] != current_hash` or the file is entirely new.
- **Goal:** Near-instant ingestion. Keeps the database perfectly synced with Git commits without re-embedding thousands of unchanged files.

### 2.3 Background Indexing
- **Trigger:** System cron job or filesystem watcher (e.g., `watchdog`).
- **Process:** As authors write new visual analogies or templates in their IDE, the background watcher detects file `SAVE` events. It quietly queues the file, runs the Incremental Indexing logic silently in the background, and dynamically updates ChromaDB. 
- **Goal:** Ensures that when the main pipeline is triggered at 2 AM, it never wastes time compiling the database, as the database is kept perpetually hot.

### 2.4 Complete Reindexing
- **Trigger:** A structural change to the chunking logic (e.g., changing from 512 to 1024 token windows) or swapping the embedding model.
- **Process:** The current ChromaDB collection is left intact for fallback. A completely new collection is created (e.g., `kb_gemini_v2`). The `HashCache` is wiped, and an Initial Indexing pass is forced. Once completed and verified, the Orchestrator config points to the new collection, and the old one is dropped.

---

# 3. Lifecycle Management

### 3.1 Duplicate Detection
- **File-Level (HashCache):** Prevents the pipeline from re-embedding the same `.md` file twice.
- **Node-Level (LlamaIndex `IngestionCache`):** If two distinct Markdown files contain the exact same C++ boilerplate block, LlamaIndex calculates a hash of the raw text string for that specific chunk. If that exact chunk hash exists in the KV store, the API call to Gemini is skipped, and the cached vector is referenced, preventing semantic duplication in ChromaDB.

### 3.2 Updates & Deletions
ChromaDB does not support "in-place" partial vector updates.
- **Updates:** If `dijkstra.md` is modified, the system queries the `HashCache` to find all `chunk_ids` previously associated with that file. It issues a `delete()` to ChromaDB for those IDs, clearing the old data. It then re-chunks and embeds the new file, inserting the fresh vectors.
- **Deletions:** If a file is deleted from the file system, the Incremental indexer flags the missing path, drops the associated `chunk_ids` from ChromaDB, and removes the entry from the `HashCache`.

---

# 4. Versioning Strategy

The indexing strategy heavily leverages Collection-Level versioning to prevent catastrophic database corruption.
- Vector dimensions and distance metrics are immutable once a collection is created. 
- Any change to the embedding model triggers an automatic version bump (`kb_v1` -> `kb_v2`).
- The pipeline uses a symlink-style configuration (e.g., `ACTIVE_COLLECTION=kb_v2`) ensuring zero-downtime swaps during reindexing operations.

---

# 5. Scheduling & Monitoring

### 5.1 Scheduling
- **Pre-Flight Hook:** Before the Orchestrator pulls the first LeetCode problem off the queue, it inherently triggers the Incremental Indexer. This guarantees the pipeline always operates on the absolute latest knowledge.
- **Nightly Cron:** A scheduled background job runs at 1:00 AM to sweep the `data/knowledge_base/` for any changes pushed via Git that day.

### 5.2 Monitoring & Telemetry
Every indexing pass logs structured JSON data via `structlog`:
- `files_scanned`: Total files checked.
- `files_modified`: Number of files that failed the hash check.
- `chunks_deleted`: Number of stale vectors pruned.
- `chunks_embedded`: Number of new vectors created.
- `api_cost_estimated`: Calculated cost based on token length (e.g., `$0.0004`).
- **Alerts:** If `files_modified == 0` but `chunks_embedded > 0`, the system raises a developer warning that the HashCache logic has disconnected.

---

# 6. Performance Optimization

1. **Async Batching:** During large ingestion sweeps, document parsing (I/O bound) and chunking (CPU bound) are parallelized. Embedding calls are batched in groups of 100 via `asyncio.gather` to maximize API throughput.
2. **Local Over Cloud:** By keeping the HashCache as a local SQLite file adjacent to ChromaDB, cache lookups take microseconds, allowing an incremental scan of 5,000 files to complete in `< 2 seconds`.
3. **Lazy Model Loading:** If using a local embedding model in the future, the model weights are only loaded into RAM if `files_modified > 0`. If the index is perfectly synced, the script exits without ever spinning up the NPU/GPU.
