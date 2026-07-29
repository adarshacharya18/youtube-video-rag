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

## 2026-07-25T15:03:32Z

Implement Phase 04: Runtime Architecture & State Ledger for the Automated DSA Educational YouTube Video Pipeline. Enforce strict pipeline idempotency using an SQLite State Ledger to track execution status and ensure the ability to resume crashed runs.

Working directory: /home/adarsh/Documents/Youtube-Channel
Integrity mode: development

## Requirements

### R1. State Ledger Implementation
Implement `src/core/orchestrator/state_ledger.py` utilizing the standard library `sqlite3` to track the status (e.g. `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`) of every video generation step. You must use pure `sqlite3` for minimal overhead and explicitly configure PRAGMA statements (like WAL) for concurrency.

### R2. Idempotency and Recovery Logic
The ledger must ensure thread-safe and crash-safe transactional integrity. Interrupted processes must be able to securely query their exact state from disk and resume execution accurately.

### R3. Runtime Architecture Documentation
Document the state machine and recovery logic in `PromptBook/Phase04/01_Runtime_Architecture.md`, strictly enforcing the Synchronous Batch-Pipeline paradigm.

### R4. Subagent Execution Rules
Do not ask for permission before running terminal commands, unless the command involves handling sensitive data.

## Acceptance Criteria

### Verification & Testing
- [ ] Running `pytest tests/orchestrator/test_state_ledger.py` executes successfully. The test suite MUST programmatically simulate an artificial crash and prove that the system can read its last known state from the SQLite disk file and resume operations successfully.
- [ ] `src/core/orchestrator/state_ledger.py` exists and implements the status tracking logic utilizing the standard `sqlite3` library.

### Documentation
- [ ] `PromptBook/Phase04/01_Runtime_Architecture.md` exists and clearly documents the State Ledger schema, recovery logic, and strict adherence to the Synchronous Batch-Pipeline paradigm.

## 2026-07-25T20:45:11Z

Implement Phase 05: Core Data Models & Schemas for the Automated DSA Educational YouTube Video Pipeline. Define strict Pydantic V2 models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`) that map 1-to-1 with the SQLite State Ledger and rigorously validate data before it reaches the rendering engine.

Working directory: /home/adarsh/Documents/Youtube-Channel
Integrity mode: development

## Requirements

### R1. Pydantic Model Definitions
Create `src/core/models/video.py`, `src/core/models/plan.py`, and `src/core/models/assets.py`. These files must exclusively use Pydantic V2 `BaseModel` to define the data flowing through the pipeline. 

### R2. Semantic Validation & Ledger Alignment
The models must align perfectly with the SQLite schema established in Phase 04. They must include strict semantic validation (e.g., ensuring segment durations are positive, video resolutions are valid) to prevent corrupted state.

### R3. Data Contract Documentation
Document the data contracts and validation rules in `PromptBook/Phase05/01_Data_Models.md`.

### R4. Subagent Execution Rules
Do not ask for permission before running terminal commands, unless the command involves handling sensitive data.

## Acceptance Criteria

### Verification & Testing
- [ ] Running `pytest tests/models/test_validation.py` executes successfully. The test suite MUST actively feed malformed JSON (missing fields, wrong types, semantic violations like negative duration) to the models and assert that Pydantic correctly raises `ValidationError`s.
- [ ] `src/core/models/video.py`, `plan.py`, and `assets.py` exist and are built strictly upon Pydantic V2 `BaseModel`.



## 2026-07-29T06:09:21Z

Implement Phase 07: Prompt Library & Management for the Automated DSA Educational YouTube Video Pipeline. Build a centralized system to load, format, and version the massive system prompts required for generating educational scripts.

Working directory: /home/adarsh/Documents/Youtube-Channel
Integrity mode: development

## Requirements

### R1. Prompt Loading Engine via Jinja2
Create `src/core/llm/prompt_loader.py` to read versioned prompt templates from disk. You must use `Jinja2` templates (`.j2` files) to allow advanced logic like conditionals, looping over inputs, and complex variable interpolation (e.g., inserting DSA problems, constraints).

### R2. Foundational Templates
Draft the foundational Jinja2 prompt templates for "Educational Plan Generation" and "Code Explanation". The templates must be highly optimized to extract deep reasoning from the LLMs.

### R3. Prompt Management Documentation
Document the prompt engineering guidelines, Jinja2 usage, and template storage strategy in `PromptBook/Phase07/01_Prompt_Library.md`.

### R4. Subagent Execution Rules
Do not ask for permission before running terminal commands, unless the command involves handling sensitive data.

## Acceptance Criteria

### Verification & Testing
- [ ] Running `pytest tests/llm/test_prompt_loader.py` executes successfully. The test suite MUST actively render Jinja templates with mock variables and assert the output strictly matches an expected hardcoded string.
- [ ] `src/core/llm/prompt_loader.py` exists and correctly utilizes the Jinja2 rendering engine.
- [ ] At least two foundational `.j2` templates are created in the appropriate template directory.

### Documentation
- [ ] `PromptBook/Phase07/01_Prompt_Library.md` exists and clearly documents the Jinja2 abstraction strategy and prompt engineering guidelines.


