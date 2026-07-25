## 2026-07-25T05:24:12Z

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

You are Worker 1 for Phase 03: RAG & Knowledge Organization.
Your working directory is `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_phase03_1`.

Please review Explorer 1's detailed technical design and specifications at:
- `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_explorer_phase03_1/analysis.md`
- `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_explorer_phase03_1/handoff.md`

Your tasks:
1. Ensure dependencies (`chromadb`, `openai`, `tiktoken`) are installed in `.venv`. Use `run_command` to install them if missing (`.venv/bin/pip install chromadb openai tiktoken`).
2. Implement `src/core/rag/__init__.py` cleanly exporting RAG components.
3. Implement `src/core/rag/embedder.py`:
   - Dataclass `Chunk` (`chunk_id`, `content`, `chunk_type` ["text"|"code"], `metadata`, `parent_slug`).
   - `TextChunker`: markdown section & paragraph aware splitter.
   - `CodeChunker`: syntax/statement-aware splitter preserving algorithmic context (functions, classes, blocks, comments).
   - `BaseEmbedder` interface with `embed_text` and `embed_chunks`.
   - `OpenAIEmbedder` using OpenAI `text-embedding-3-small` (1536 dims).
   - `MockEmbedder`: deterministic SHA-256 text-hash L2-normalized 1536-dim unit vector generator for offline/testing fallback.
   - `get_embedder(model_name: Optional[str] = None, use_mock: bool = False) -> BaseEmbedder`.
4. Implement `src/core/rag/vector_store.py`:
   - `ChromaVectorStore`: wrapper around ChromaDB supporting both `chromadb.PersistentClient` (default path: `data/vector_store/chroma`) and `chromadb.EphemeralClient` (for tests).
   - `add_problem(problem: ScrapedProblem) -> List[str]`: chunks description/examples/code, embeds, and inserts into collection.
   - `add_chunks(chunks: List[Chunk]) -> List[str]`
   - `query(query_text: str, top_k: int = 5, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]`
   - `query_by_text(...)`
   - `delete_by_slug(slug: str) -> bool`
   - `delete_collection() -> None`
   - `get_stats() -> Dict[str, Any]`
5. Document architecture in `PromptBook/Phase03/01_RAG_Architecture.md`:
   - Cover chunking strategies (text vs code), ChromaDB storage architecture, embedding models, schema & metadata design, query workflow, and fallbacks.
6. Implement comprehensive tests:
   - `tests/rag/__init__.py`
   - `tests/rag/test_embedder.py`
   - `tests/rag/test_vector_store.py`: test synthetic DSA problem insertion, semantic search queries, metadata filtering (`difficulty`, `tags`), slug deletion, and stats.
7. Execute tests: `.venv/bin/pytest tests/rag/test_vector_store.py` and `.venv/bin/pytest tests/` to confirm all tests pass.
8. Document execution and test results in `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_phase03_1/handoff.md`.
9. Send a completion message back to parent orchestrator (conversation ID: 8f381ec0-0a11-43e5-afd2-842c2ad1f1db).
