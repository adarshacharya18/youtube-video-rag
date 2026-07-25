# Phase 03: RAG & Knowledge Organization Architecture Specification

**Module:** RAG Knowledge Engine & Vector Retrieval (Module 3)  
**Version:** 1.0.0  
**Date:** 2026-07-25  

---

## 1. Overview & Architectural Goals

The **RAG Knowledge Engine** provides semantic indexing, document chunking, and similarity search for Data Structures & Algorithms (DSA) problems scraped from LeetCode. It forms the primary knowledge retrieval subsystem powering downstream AI script generation and animation scene planning.

### Key Capabilities
1. **Dual Chunking Strategy**: Specialized text chunker for markdown problem descriptions/examples and syntax-aware code chunker for algorithm solution snippets.
2. **Dual-Mode Embedding Engine**: OpenAI `text-embedding-3-small` (1536 dimensions) for production retrieval with a deterministic SHA-256 unit-vector `MockEmbedder` fallback for zero-network testing and offline development.
3. **Local Vector Storage**: `ChromaVectorStore` wrapping ChromaDB with persistent disk storage (`data/vector_store/chroma`) and ephemeral in-memory support for Pytest execution.
4. **Rich Metadata Indexing**: Metadata-filtered queries supporting problem difficulty (`Easy`, `Medium`, `Hard`), problem tags, chunk types (`text` vs `code`), and problem slug isolation.

---

## 2. RAG System Architecture

```
                          +-------------------+
                          |  ScrapedProblem   |
                          +---------+---------+
                                    |
                 +------------------+------------------+
                 |                                     |
                 v                                     v
       +-------------------+                 +-------------------+
       |    TextChunker    |                 |    CodeChunker    |
       | (Markdown Section |                 | (Syntax/Function/ |
       | & Paragraph Aware)|                 |  Block Aware)     |
       +---------+---------+                 +---------+---------+
                 |                                     |
                 v                                     v
        Text Chunks (500 chars)              Code Chunks (1000 chars)
                 |                                     |
                 +------------------+------------------+
                                    |
                                    v
                          +-------------------+
                          |  Embedding Engine |
                          | (OpenAI / Mock)   |
                          +---------+---------+
                                    |
                                    v
                          +-------------------+
                          | ChromaVectorStore |
                          | (ChromaDB Index)  |
                          +-------------------+
```

---

## 3. Chunking Strategy

### 3.1 TextChunker
- **Target Fields**: `description`, `constraints`, `examples`, `title`, `difficulty`, `tags`.
- **Strategy**:
  - Splits documents on markdown headers (`#`, `##`, `###`) and double newline paragraph boundaries (`\n\n`).
  - Preserves section context (e.g. `## Description`, `## Constraints`, `## Examples`).
  - Configurable chunk size (default: 500 characters) and overlap (default: 50 characters).
  - Formats headers and problem metadata into the chunk payload to retain full problem context.

### 3.2 CodeChunker
- **Target Fields**: `accepted_code` (Python, C++, Java, etc.).
- **Strategy**:
  - Syntax and block-aware code splitting preserving algorithmic context (functions, classes, loop blocks, comments).
  - If code length $\le$ 1000 characters, retains the complete solution as a single intact chunk.
  - If code exceeds 1000 characters, breaks at function/method boundaries (`def `, `class `) without severing mid-statement indentation.
  - Prepends class signature headers to sub-chunks when splitting long OOP solution classes.
  - Tracks line numbers (`start_line`, `end_line`) for precise code snippet referencing.

---

## 4. Embedding Engine & Deterministic Fallbacks

### 4.1 BaseEmbedder Interface
Abstract base protocol specifying:
- `dimension`: Vector dimension (1536).
- `embed_text(text: str) -> List[float]`
- `embed_chunks(chunks: List[Chunk]) -> List[List[float]]`
- `embed_batch(texts: List[str]) -> List[List[float]]`

### 4.2 OpenAIEmbedder
- **Model**: `text-embedding-3-small` (1536 dimensions).
- Uses `openai.OpenAI()` client to request dense vector representations.
- Wraps transient network/API failures in `EmbeddingError(RAGError, RetryableError)`.

### 4.3 MockEmbedder (Offline Fallback)
- **Algorithm**: Generates a deterministic 1536-dimensional L2-normalized unit vector using the SHA-256 hash of the input text as a pseudo-random number generator seed.
- **Properties**:
  - $\|v\|_2 = 1.0$ (Unit length).
  - Deterministic: Identical text strings produce identical vector outputs across runs.
  - Distinct: Different text inputs produce distinct orthogonal-like unit vectors.
  - Zero external network dependencies.

### 4.4 Embedder Factory (`get_embedder`)
Selects `OpenAIEmbedder` when an API key is available and `use_mock=False`. Automatically falls back to `MockEmbedder` when `OPENAI_API_KEY` is missing or when `use_mock=True`.

---

## 5. Vector Store Schema & Metadata Design

### 5.1 Storage Architecture
- Production: `chromadb.PersistentClient` stored at `data/vector_store/chroma`.
- Testing: `chromadb.EphemeralClient` in-memory store.
- Default Collection: `"dsa_knowledge"` with cosine distance space (`hnsw:space = cosine`).

### 5.2 Metadata Schema
Every chunk stored in ChromaDB contains standard metadata fields sanitized to primitive types:

| Field Name | Type | Description | Example |
|------------|------|-------------|---------|
| `slug` | `str` | Problem identifier slug | `"two-sum"` |
| `parent_slug` | `str` | Parent problem identifier | `"two-sum"` |
| `title` | `str` | Problem title | `"Two Sum"` |
| `number` | `int` | LeetCode problem number | `1` |
| `difficulty` | `str` | Normalized difficulty | `"Easy"` |
| `tags` | `str` | Comma-separated tag list | `"Array,Hash Table"` |
| `chunk_type` | `str` | Content classification | `"text"` or `"code"` |
| `code_language` | `str` | Programming language | `"python"` |
| `start_line` | `int` | Starting line number (code) | `1` |
| `end_line` | `int` | Ending line number (code) | `25` |
| `scraped_at` | `str` | ISO 8601 timestamp | `"2026-07-25T10:00:00Z"` |

---

## 6. Query & Retrieval Workflow

1. **Input Query**: Caller passes `query_text: str`, `top_k: int`, and optional `where: Dict[str, Any]` filter.
2. **Embedding**: `query_text` is embedded into a 1536-dim vector via `embedder.embed_text(query_text)`.
3. **Filter Translation**: `where` filters (e.g. `{"difficulty": "Easy", "chunk_type": "text"}`) are translated to valid ChromaDB `$and` / `$in` / `$contains` syntax.
4. **Vector Search**: ChromaDB searches collection using cosine distance metric.
5. **Score Normalization**: Distances $d$ are converted to similarity scores $s = \max(0.0, 1.0 - d)$.
6. **Result Payload**: Returns list of dictionary objects:
   ```python
   [
       {
           "id": "two-sum_text_0",
           "document": "# Problem 1: Two Sum\nDifficulty: Easy...",
           "metadata": {"slug": "two-sum", "difficulty": "Easy", "chunk_type": "text"},
           "distance": 0.12,
           "score": 0.88,
       }
   ]
   ```

---

## 7. Error Handling & Resilience

- `RAGError`: Base exception for RAG subsystem errors.
- `IndexNotFoundError`: Raised when ChromaDB directory or collection cannot be created or accessed.
- `EmbeddingError`: Raised when embedding API calls fail or credentials are missing.
- **Graceful Fallbacks**: Missing API keys or network isolation triggers `MockEmbedder` seamlessly.
