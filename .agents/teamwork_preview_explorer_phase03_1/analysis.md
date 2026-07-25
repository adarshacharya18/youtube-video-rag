# Phase 03: RAG & Knowledge Organization — Architectural Analysis & Technical Plan

**Author:** Explorer 1 (Phase 03: RAG & Knowledge Organization)  
**Working Directory:** `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_explorer_phase03_1`  
**Date:** 2026-07-25  
**Target Subsystem:** RAG & Knowledge Vector Indexing (Module 3)  

---

## 1. Executive Summary

Phase 03 of the Youtube Content Generation Pipeline focuses on **RAG & Knowledge Organization**. The primary objective is to build a robust, deterministic, offline-first vector storage and semantic retrieval engine that indexes scraped LeetCode Data Structure & Algorithm (DSA) problems along with curated algorithmic knowledge.

This report presents a thorough analysis of:
1. **Existing Codebase Foundations**: Dataclasses (`ScrapedProblem`, `Example`, `Difficulty`), Pydantic settings (`RAGConfig`), core abstractions (`Repository`, `Service`), exception hierarchy (`RAGError`, `EmbeddingError`, `IndexNotFoundError`), and test fixture conventions.
2. **Dual Chunking Strategy**: Specialized `TextChunker` (header/paragraph-aware markdown splitter) and `CodeChunker` (AST/line/indentation-aware algorithm code splitter).
3. **Embedding Engine**: Dual-mode embedder supporting OpenAI `text-embedding-3-small` (1536 dims) with deterministic hash-seeded `MockEmbedder` fallback for testing and offline execution without API keys.
4. **Local Vector Store**: `ChromaVectorStore` wrapping `chromadb.PersistentClient` (and in-memory ephemeral client for Pytest) with rich metadata filtering (difficulty, tags, slug, chunk_type).
5. **Documentation & Test Plan**: Canonical architecture documentation for `PromptBook/Phase03/01_RAG_Architecture.md` and comprehensive Pytest suite for `tests/rag/test_vector_store.py`.

---

## 2. Codebase Inspection & Baseline Analysis

### 2.1 Domain Models (`src/models/problem.py` & `src/models/enums.py`)
- **`Difficulty` Enum** (`src/models/enums.py:5-31`):
  - Values: `Difficulty.EASY` ("Easy"), `Difficulty.MEDIUM` ("Medium"), `Difficulty.HARD` ("Hard").
  - Includes robust normalization via `Difficulty.from_string(...)` handling uppercase, lowercase, and "Med" aliases.
- **`Example` Dataclass** (`src/models/problem.py:7-28`):
  - Fields: `input: str`, `output: str`, `explanation: str = ""`.
  - Methods: `to_dict()` and `from_dict(cls, data: Dict[str, Any])`.
- **`ScrapedProblem` Dataclass** (`src/models/problem.py:31-93`):
  - `@dataclass(frozen=True)` ensuring immutability across pipeline stages.
  - Key attributes:
    - `slug: str` (e.g. `"two-sum"`) — primary identifier across vector store entries.
    - `title: str` (e.g. `"Two Sum"`)
    - `number: int` (e.g. `1`)
    - `difficulty: Difficulty` (`EASY`, `MEDIUM`, `HARD`)
    - `description: str` (cleaned markdown text)
    - `constraints: List[str]`
    - `examples: List[Example]`
    - `tags: List[str]` (e.g. `["Array", "Hash Table"]`)
    - `accepted_code: str` (solution code snippet)
    - `code_language: str` (e.g. `"python"`, `"cpp"`)
    - `scraped_at: str` (ISO 8601 timestamp string)
  - Serialization roundtrip tested and verified in `tests/ingestion/test_parser.py:54-81`.

### 2.2 Configuration Framework (`src/core/config.py`)
- **`RAGConfig` Settings Class** (`src/core/config.py:38-44`):
  ```python
  class RAGConfig(BaseSettings):
      chroma_db_dir: Path = Field(default=Path("data/vector_store/chroma"))
      knowledge_base_dir: Path = Field(default=Path("data/knowledge_base"))
      collection_name: str = Field(default="dsa_knowledge")
      top_k: int = Field(default=10, ge=1, le=50)
  ```
- **Proposed RAGConfig Extensions**:
  To support embedding selection and offline mock behavior, `RAGConfig` should be expanded with:
  - `openai_api_key: SecretStr = Field(default=SecretStr(""))`
  - `embedding_model: str = Field(default="text-embedding-3-small")`
  - `embedding_dim: int = Field(default=1536)`
  - `use_mock_embedder: bool = Field(default=False)`

### 2.3 Structural Base Protocols & Exception Hierarchy
- **`Repository[T]` Protocol** (`src/core/base.py:64-78`):
  - Abstract persistence protocol defining `get(id)`, `save(entity)`, `delete(id)`.
  - `ChromaVectorStore` conforms to the repository pattern for problem chunk vectors.
- **`Lifecycle` Protocol** (`src/core/base.py:133-144`):
  - Hooks `initialize()` and `shutdown()` for client lifecycle management.
- **RAG Exception Hierarchy** (`src/core/exceptions.py:95-111`):
  - Base: `RAGError(PipelineError)`
  - `IndexNotFoundError(RAGError, FatalError)` — missing database or collection.
  - `EmbeddingError(RAGError, RetryableError)` — API error during vector calculation.
  - `KnowledgeConflictError(RAGError, FatalError)` — contradictory documents.

### 2.4 Test Fixtures & Synthetic DSA Problems (`tests/fixtures/ingestion/`)
Existing markdown problem fixtures in `tests/fixtures/ingestion/`:
1. `two_sum.md`: Array, Hash Table; Easy; Python solution with `seen` dictionary.
2. `reverse_linked_list.md`: Linked List; Easy; Python solution with `prev`, `curr` pointers.
3. `binary_tree_level_order.md`: Tree, BFS; Medium; Python solution with `collections.deque`.
4. Edge-case fixtures: `messy_html_problem.md`, `varied_code_headers_problem.md`, `missing_optional_fields.md`.

These fixtures provide realistic synthetic DSA problem objects for unit and integration testing of chunking, embedding, and vector storage.

### 2.5 Dependencies & Environment Audit
- Currently installed packages in `.venv`: `pydantic` (2.13.4), `pydantic-settings` (2.14.2), `structlog` (26.1.0), `pytest` (9.1.1).
- Key packages required for Phase 03:
  - `chromadb`: Vector DB engine (`chromadb.PersistentClient`, `chromadb.EphemeralClient`).
  - `openai`: Client for OpenAI `text-embedding-3-small`.
  - `tiktoken`: Tokenizer for token count estimation in text/code chunking.
- Audit result: `chromadb`, `openai`, `tiktoken` are listed for inclusion in `requirements.txt` and `pyproject.toml`.

---

## 3. Detailed Architectural Requirements for Phase 03

### 3.1 Dual Chunking Strategy (`TextChunker` vs `CodeChunker`)

To preserve algorithmic context, text and code must be chunked using strategies tailored to their structural properties:

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
   | (Markdown Header/ |                 |  (AST/Function/   |
   | Paragraph Aware)  |                 | Line-Block Aware) |
   +---------+---------+                 +---------+---------+
             |                                     |
             v                                     v
     Text Chunks (dsa_text)                Code Chunks (dsa_code)
```

#### 1. TextChunker
- **Target**: `description`, `constraints`, `examples`, `tags`, title headers.
- **Strategy**:
  - Markdown header-aware splitting (`#`, `##`, `###`).
  - Keeps section boundaries intact (e.g. `## Description`, `## Constraints`, `## Examples` are preserved in chunk header context).
  - Parametrized `chunk_size` (default ~500 chars / ~120 tokens) and `chunk_overlap` (default ~50 chars / ~15 tokens).
  - Generates `Chunk` objects with `chunk_type="text"`.

#### 2. CodeChunker
- **Target**: `accepted_code` (Python, C++, Java, etc.).
- **Strategy**:
  - Function / Class / Method aware splitting.
  - Detects top-level function definitions (`def solve(...)`, `class Solution:`) and loop blocks (`for`, `while`).
  - Avoids breaking code mid-indentation block or mid-statement.
  - If code fits within single chunk limit (~1000 chars), keeps code intact as a unified block.
  - For large multi-function solutions, prepends class header / signature context to sub-chunks.
  - Generates `Chunk` objects with `chunk_type="code"`, including `start_line` and `end_line` metadata.

#### 3. Standardized `Chunk` Data Model
```python
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class Chunk:
    chunk_id: str
    content: str
    chunk_type: str  # "text" or "code"
    metadata: Dict[str, Any]
    start_line: Optional[int] = None
    end_line: Optional[int] = None
```

---

### 3.2 Embedding Engine Architecture (`src/core/rag/embedder.py`)

#### 1. Abstract Base Class / Protocol (`BaseEmbedder`)
```python
from abc import ABC, abstractmethod

class BaseEmbedder(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension (e.g. 1536)."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of text strings in batch."""
        pass
```

#### 2. Concrete OpenAI Embedder (`OpenAIEmbedder`)
- Model: `text-embedding-3-small` (1536 dimensions).
- Uses `openai.OpenAI(api_key=...)`.
- Batches texts up to max batch size (e.g. 64 texts).
- Catches network/API exceptions and wraps them in `EmbeddingError(RAGError, RetryableError)`.

#### 3. Deterministic Fallback Embedder (`MockEmbedder`)
- Used when `OPENAI_API_KEY` is not provided, during Pytest runs, or in offline environment.
- Algorithm: Uses SHA-256 hash of the input text + seed to generate a reproducible pseudo-random vector of length 1536, normalized to unit L2 length ($\|v\|_2 = 1.0$).
- Determinism Guarantee: Identical strings produce identical 1536-dimensional vectors. Different strings produce distinct unit vectors.
- Offline & Fast: No network dependencies, sub-millisecond execution.

#### 4. Embedder Factory (`get_embedder(config: RAGConfig) -> BaseEmbedder`)
- Automatically selects `OpenAIEmbedder` if API key is present and `use_mock_embedder=False`.
- Automatically falls back to `MockEmbedder` if API key is absent or `use_mock_embedder=True`.

---

### 3.3 ChromaDB Vector Store Wrapper (`src/core/rag/vector_store.py`)

#### 1. Class Design: `ChromaVectorStore`
- Wraps `chromadb.PersistentClient(path=str(chroma_db_dir))` for production.
- Supports `chromadb.EphemeralClient()` (or `is_test=True`) for in-memory Pytest execution.
- Collection: `"dsa_knowledge"` (configurable via `RAGConfig`).

#### 2. Vector Store Metadata Schema
Every chunk stored in ChromaDB contains:
- `id`: `{slug}_text_{idx}` or `{slug}_code_{idx}`
- `document`: Chunk content string.
- `embedding`: 1536-dimensional float vector.
- `metadata`:
  - `slug`: str (e.g. `"two-sum"`)
  - `number`: int (e.g. `1`)
  - `title`: str (e.g. `"Two Sum"`)
  - `difficulty`: str (e.g. `"Easy"`)
  - `tags`: str (comma-separated, e.g. `"Array,Hash Table"`)
  - `chunk_type`: str (`"text"` or `"code"`)
  - `code_language`: str (e.g. `"python"`)
  - `scraped_at`: str

#### 3. Key Methods & API Specifications
```python
class ChromaVectorStore:
    def __init__(self, config: RAGConfig, is_test: bool = False):
        ...

    def add_problem(
        self, 
        problem: ScrapedProblem, 
        chunks: list[Chunk], 
        embeddings: list[list[float]]
    ) -> None:
        """Upsert problem chunks and embeddings into ChromaDB collection."""
        ...

    def query(
        self, 
        query_embedding: list[float], 
        top_k: int = 5, 
        filters: dict[str, Any] | None = None
    ) -> list[QueryResult]:
        """Perform vector search with optional metadata filters (difficulty, tags, slug, chunk_type)."""
        ...

    def query_by_text(
        self, 
        query_text: str, 
        embedder: BaseEmbedder, 
        top_k: int = 5, 
        filters: dict[str, Any] | None = None
    ) -> list[QueryResult]:
        """Convenience method to embed query text and execute vector search."""
        ...

    def delete_by_slug(self, slug: str) -> None:
        """Delete all chunks belonging to a specific problem slug."""
        ...

    def delete_collection(self) -> None:
        """Wipe collection."""
        ...

    def get_stats(self) -> dict[str, Any]:
        """Return total chunks, total unique problem slugs, and collection info."""
        ...
```

---

## 4. Implementation Artifact Specifications

### 4.1 Artifact 1: `src/core/rag/embedder.py`
- Implements `Chunk` dataclass.
- Implements `TextChunker` and `CodeChunker`.
- Implements `BaseEmbedder` abstract class.
- Implements `OpenAIEmbedder` and `MockEmbedder`.
- Implements `get_embedder(config: RAGConfig)`.

### 4.2 Artifact 2: `src/core/rag/vector_store.py`
- Implements `QueryResult` dataclass.
- Implements `ChromaVectorStore` wrapper class.
- Supports persistent disk storage and in-memory test storage.
- Implements `add_problem()`, `query()`, `query_by_text()`, `delete_by_slug()`, `delete_collection()`, `get_stats()`.

### 4.3 Artifact 3: `PromptBook/Phase03/01_RAG_Architecture.md`
- Comprehensive architecture documentation following PromptBook canonical format.
- Sections:
  1. Executive Summary & Core Requirements
  2. Architecture Overview & Diagrams (Ingestion & Retrieval)
  3. Dual Chunking Strategy (TextChunker vs CodeChunker)
  4. Embedding Engine & Deterministic Fallback Strategy
  5. Vector Store Schema & Metadata Filtering
  6. Semantic Query & Retrieval Workflow
  7. Error Handling, Resilience & Failure Recovery
  8. Scalability & Performance Benchmarks

### 4.4 Artifact 4: `tests/rag/test_vector_store.py`
- Full Pytest suite validating:
  1. `test_text_chunker_header_and_paragraph_splitting()`
  2. `test_code_chunker_function_and_structure_preservation()`
  3. `test_mock_embedder_determinism_and_dimensions()`
  4. `test_openai_embedder_fallback()`
  5. `test_chroma_vector_store_initialization_in_memory()`
  6. `test_chroma_vector_store_add_and_retrieve_problem()`
  7. `test_chroma_vector_store_metadata_filtering_by_difficulty()`
  8. `test_chroma_vector_store_metadata_filtering_by_tags()`
  9. `test_chroma_vector_store_metadata_filtering_by_chunk_type()`
  10. `test_chroma_vector_store_delete_by_slug()`
  11. `test_chroma_vector_store_stats()`

---

## 5. Technical Plan & Execution Sequence

| Step | Target File | Action Description |
|------|-------------|--------------------|
| **1** | `requirements.txt` & `pyproject.toml` | Verify/add `chromadb`, `openai`, `tiktoken` dependencies. |
| **2** | `src/core/rag/embedder.py` | Create chunkers (`TextChunker`, `CodeChunker`) and embedders (`BaseEmbedder`, `OpenAIEmbedder`, `MockEmbedder`). |
| **3** | `src/core/rag/vector_store.py` | Create `ChromaVectorStore` wrapper class with metadata filtering & stats. |
| **4** | `PromptBook/Phase03/01_RAG_Architecture.md` | Write canonical Phase 03 RAG Architecture documentation. |
| **5** | `tests/rag/test_vector_store.py` | Implement full Pytest suite utilizing synthetic DSA problem fixtures. |
| **6** | Verification | Execute `pytest tests/rag/test_vector_store.py` and full suite. |

---

## 6. Verification Strategy

1. **Unit Testing**:
   - Run `pytest tests/rag/test_vector_store.py` using `MockEmbedder` and `EphemeralClient`.
   - Verify 100% test pass rate with zero network requirements.
2. **Integration Verification**:
   - Run `pytest tests/ingestion/` to ensure no regression in problem parsing.
3. **Coverage Check**:
   - Run `pytest --cov=src/core/rag tests/rag/` to verify >90% code coverage.
