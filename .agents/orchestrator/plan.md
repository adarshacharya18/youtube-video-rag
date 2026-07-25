# Phase 03: RAG & Knowledge Organization — Project Plan

## Architecture & Scope
Phase 03 implements the Retrieval-Augmented Generation (RAG) and Knowledge Organization layer for the Automated DSA Educational YouTube Video Pipeline.
It builds an embedding engine with chunking strategies tailored for code vs text, integrates local ChromaDB vector store persistence, documents the RAG architecture in `PromptBook/Phase03/01_RAG_Architecture.md`, and provides comprehensive test suites in `tests/rag/test_vector_store.py`.

## Milestones

| # | Milestone Name | Scope & Deliverables | Dependencies | Status |
|---|----------------|----------------------|--------------|--------|
| M1 | Exploration & Context Analysis | Explore repository, inspect existing problem models, dependencies (`chromadb`, `openai`, `pytest`), and formulate implementation strategy | None | IN_PROGRESS |
| M2 | Core Implementation & Documentation | Implement `src/core/rag/embedder.py`, `src/core/rag/vector_store.py`, `PromptBook/Phase03/01_RAG_Architecture.md`, and `tests/rag/test_vector_store.py` | M1 | PLANNED |
| M3 | Review & Adversarial Challenge | Independent code review by 2 Reviewers; empirical verification & stress-testing by 2 Challengers | M2 | PLANNED |
| M4 | Forensic Integrity Audit | Forensic integrity audit by Auditor (`teamwork_preview_auditor`) to ensure authentic implementation without shortcuts or hardcoded outputs | M3 | PLANNED |

## Interface Contracts & Data Models
- `src/core/rag/embedder.py`:
  - `Chunk`: Dataclass containing chunk_id, text/code content, chunk_type ("text" | "code"), metadata, parent_id.
  - `CodeChunker`: Splits code preserving function signatures, class boundaries, control flow blocks, and comments.
  - `TextChunker`: Splits text preserving paragraph boundaries, markdown headers, and sentence integrity.
  - `EmbeddingEngine`: Interface & implementation supporting OpenAI `text-embedding-3-small` with local/mock fallback mode when API key is missing or in offline test environment.
- `src/core/rag/vector_store.py`:
  - `ChromaVectorStore`: Local ChromaDB vector store wrapper utilizing `chromadb.PersistentClient` (or ephemeral client for tests).
  - Methods: `add_problem(problem: ScrapedProblem)`, `add_chunks(chunks: List[Chunk])`, `query(query_text: str, top_k: int = 5, where: Optional[Dict] = None)`, `delete_collection()`, `get_stats()`.
- `PromptBook/Phase03/01_RAG_Architecture.md`:
  - Detailed documentation of text vs code chunking strategies, embedding dimensions, ChromaDB schema, distance metrics, query pipeline, metadata indexing, and evaluation.
- `tests/rag/test_vector_store.py`:
  - Tests inserting synthetic DSA problems, embedding, querying semantic matches, metadata filtering (e.g. difficulty, tags), and persistence verification.
