# Original User Request

## Initial Request — 2026-07-24T11:17:02+05:30

Implement Phase 02: Knowledge Ingestion for the Automated DSA Educational YouTube Video Pipeline. The system must ingest raw DSA problems (e.g. from LeetCode or markdown files) and parse descriptions, constraints, and solutions into standardized Python dataclasses.

Working directory: /home/adarsh/Documents/Youtube-Channel
Integrity mode: development

## Requirements

### R1. Markdown & AST Parsing
Create `src/core/ingestion/parser.py` to parse raw Markdown/HTML DSA problems. The parser must extract the problem description, constraints, and the optimal solution code (Python/C++). You must use a robust parsing library like `markdown-it-py` or `mistune` rather than brittle custom regex.

### R2. Data Sanitization & Standardization
Create `src/core/ingestion/sanitizer.py` to clean the parsed data and enforce strict standardization into Python dataclasses (building on Phase 01 configurations).

### R3. Ingestion Strategy Documentation
Document the ingestion pipeline architecture in `PromptBook/Phase02/01_Ingestion_Strategy.md`.

## Acceptance Criteria

### Verification & Testing
- [ ] The team must generate synthetic mock Markdown fixtures representing typical DSA problems.
- [ ] Running `pytest tests/ingestion/test_parser.py` executes successfully, validating that the parser correctly extracts data from the synthetic mock fixtures into the standardized Python dataclasses.
- [ ] `src/core/ingestion/parser.py` and `src/core/ingestion/sanitizer.py` exist and contain the required data extraction and cleaning logic.

### Documentation & Structure
- [ ] `PromptBook/Phase02/01_Ingestion_Strategy.md` exists and details the architecture for Markdown/HTML parsing and AST extraction.

## 2026-07-25T05:21:09Z

Implement Phase 03: RAG & Knowledge Organization for the Automated DSA Educational YouTube Video Pipeline. Chunk, embed, and store parsed DSA problems into a local ChromaDB Vector Database to enable accurate semantic search for cross-referencing algorithms.

Working directory: /home/adarsh/Documents/Youtube-Channel
Integrity mode: development

## Requirements

### R1. Embedding Engine
Implement `src/core/rag/embedder.py` (using a provider like OpenAI `text-embedding-3-small` or a local alternative). The embedder must support optimal chunking strategies tailored for code vs. text to preserve algorithmic context.

### R2. ChromaDB Local Vector Store
Implement `src/core/rag/vector_store.py` to persist the embeddings locally utilizing ChromaDB as the underlying serverless vector database.

### R3. RAG Architecture Documentation
Document the chunking and retrieval strategy in `PromptBook/Phase03/01_RAG_Architecture.md`.

### R4. Subagent Execution Rules
Do not ask for permission before running terminal commands, unless the command involves handling sensitive data.

## Acceptance Criteria

### Verification & Testing
- [ ] Running `pytest tests/rag/test_vector_store.py` executes successfully using a synthetic mock testing suite. The tests must insert dummy DSA problems, execute semantic retrieval queries, and validate that the correct matches are returned.
- [ ] `src/core/rag/embedder.py` and `src/core/rag/vector_store.py` exist and contain the required chunking, embedding, and ChromaDB insertion/query logic.

### Documentation
- [ ] `PromptBook/Phase03/01_RAG_Architecture.md` exists and details the chunking strategy (text vs. code) and ChromaDB retrieval architecture.

