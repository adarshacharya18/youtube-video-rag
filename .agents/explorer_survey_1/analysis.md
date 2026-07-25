# Phase 04 Codebase Exploration & State Ledger Architecture Analysis

**Author:** Explorer 1  
**Date:** 2026-07-25  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Working Directory:** `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_survey_1`

---

## 1. Executive Summary

This report presents a thorough investigation of the existing codebase under `/home/adarsh/Documents/Youtube-Channel` to prepare for **Phase 04: Runtime Architecture & State Ledger**.

### Core Discoveries:
1. **Existing Core Modules (`src/core/`)**:
   - `base.py`: Defines structural protocols (`PipelineModule`, `Service`, `Repository`, `Factory`, `Command`, `Lifecycle`) and standard `BasePipelineResult[T]` generic dataclass.
   - `config.py`: Root `PipelineConfig` and sub-configs (`ScraperConfig`, `RAGConfig`, `GeminiConfig`, `YouTubeConfig`) using Pydantic Settings with env hydration.
   - `exceptions.py`: Hierarchical custom exception system rooted at `PipelineError`, subdivided into `FatalError` and `RetryableError`, alongside module-specific errors (`ScraperError`, `RAGError`, `ScriptGenerationError`, `VoiceGenerationError`, etc.).
   - `logger.py`: Centralized structured logging using `structlog` supporting ISO-8601 timestamps, context variable binding (`pipeline_id`), rotating JSON log files, and execution timing context managers (`log_execution_time`).
   - `ingestion/` (Phase 02): AST markdown parser (`DSAParser`) using `markdown-it-py` and `BeautifulSoup` + sanitizer (`MarkdownSanitizer`) enforcing strict fail-fast validation.
   - `rag/` (Phase 03): Dual chunker (`TextChunker`, `CodeChunker`), embedder (`MockEmbedder`, `OpenAIEmbedder`), and vector store (`ChromaVectorStore` with genuine `_InMemoryClient` fallback).

2. **Orchestrator Directory State**:
   - `src/orchestrator/pipeline.py` and `src/orchestrator/checkpoint.py` exist as empty 0-byte placeholder files.
   - `src/core/orchestrator/` directory does NOT exist yet. Phase 04 requires creating `src/core/orchestrator/state_ledger.py`.
   - `tests/orchestrator/test_state_ledger.py` needs to be created to validate crash-recovery and transactional idempotency.

3. **Test Suite Status**:
   - Unit tests for Phase 01-03 core modules pass cleanly via `.venv/bin/pytest tests/ingestion/test_parser.py tests/rag/test_vector_store.py tests/core/` (43 passed tests in 0.44s).

---

## 2. Codebase Architecture & Conventions Survey

### 2.1 Dataclasses & Data Serialization
- All domain models use `@dataclass(frozen=True)` or standard `@dataclass`.
- Example from `src/models/problem.py`:
  ```python
  @dataclass(frozen=True)
  class ScrapedProblem:
      slug: str
      title: str
      number: int
      difficulty: Difficulty
      description: str
      constraints: List[str]
      examples: List[Example]
      tags: List[str]
      accepted_code: str
      code_language: str
      scraped_at: str

      def to_dict(self) -> Dict[str, Any]: ...
      @classmethod
      def from_dict(cls, data: Dict[str, Any]) -> "ScrapedProblem": ...
  ```
- Result encapsulation uses `BasePipelineResult[T]` from `src/core/base.py`:
  ```python
  @dataclass
  class BasePipelineResult(Generic[T]):
      success: bool
      data: T | None = None
      error: Exception | None = None
      error_message: str | None = None
      execution_time_ms: float = 0.0
      timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
  ```

### 2.2 Naming Conventions
- **Classes**: `UpperCamelCase` (e.g., `MarkdownSanitizer`, `ChromaVectorStore`, `BaseEmbedder`).
- **Functions/Methods/Variables**: `snake_case` (e.g., `sanitize_problem`, `embed_chunks`, `add_problem`).
- **Constants/Enums**: `ALL_CAPS` (e.g., `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `EASY`, `MEDIUM`, `HARD`).

### 2.3 Import Patterns
- Modules use explicit absolute package imports:
  ```python
  from src.core.config import PipelineConfig, RAGConfig
  from src.core.exceptions import FatalError, RetryableError, RAGError
  from src.core.logger import get_logger
  from src.models import ScrapedProblem, Difficulty
  ```

### 2.4 Error Handling & Logging Strategy
- Centralized exception base: `PipelineError` in `src/core/exceptions.py`.
- Operational distinctions:
  - `FatalError`: Halts execution immediately (e.g. `ConfigurationError`, `ValidationError`, `IndexNotFoundError`).
  - `RetryableError`: Indicates transient failure for retry loops (e.g. `NetworkError`, `RateLimitError`, `EmbeddingError`).
- Structlog integration:
  ```python
  logger = get_logger(__name__)
  logger.info("stage_completed", stage="ingestion", duration_sec=1.23)
  ```

---

## 3. Detailed Requirements for `src/core/orchestrator/state_ledger.py`

### 3.1 Status Enums & Core Types
The state ledger must support the four canonical status states:
- `PENDING`: Step registered but execution has not begun.
- `IN_PROGRESS`: Step execution active.
- `COMPLETED`: Step successfully executed and output payload stored.
- `FAILED`: Step failed with error details recorded.

Recommended Python Enum definition in `state_ledger.py`:
```python
from enum import StrEnum

class LedgerStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
```

### 3.2 Database Engine & PRAGMA Performance Optimizations
- **Standard Library SQLite**: Must use python standard library `sqlite3` without external ORMs.
- **WAL Pragma Mode**: SQLite defaults to rollback journal which can lock on concurrent reads/writes. `state_ledger.py` must explicitly execute:
  ```sql
  PRAGMA journal_mode=WAL;
  PRAGMA synchronous=NORMAL;
  PRAGMA foreign_keys=ON;
  PRAGMA busy_timeout=5000;
  ```
- **Thread Safety**:
  - Since step parallelism (e.g., parallel Voice and Manim generation) can run via `ThreadPoolExecutor`, database operations must be thread-safe.
  - Recommended pattern: Re-usable thread-safe context manager, connection-per-thread factory, or explicit `threading.Lock()` wrapping all database write transactions to avoid `sqlite3.OperationalError: database is locked`.

### 3.3 Recommended Database Schema
```sql
CREATE TABLE IF NOT EXISTS state_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED')),
    attempt INTEGER NOT NULL DEFAULT 1,
    input_payload TEXT,
    output_payload TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(pipeline_run_id, step_name)
);

CREATE INDEX IF NOT EXISTS idx_ledger_slug ON state_ledger(slug);
CREATE INDEX IF NOT EXISTS idx_ledger_lookup ON state_ledger(pipeline_run_id, step_name);
CREATE INDEX IF NOT EXISTS idx_ledger_status ON state_ledger(status);
```

### 3.4 Transaction Management & API Contract
`StateLedger` class implementation structure:
1. `__init__(db_path: Path | str = "data/pipeline_state.db")`:
   - Ensures directory exists.
   - Initializes schema & applies PRAGMAs.
2. `record_step_start(pipeline_run_id: str, slug: str, step_name: str, input_payload: dict | None = None) -> None`:
   - Transitions step to `IN_PROGRESS` atomically.
3. `record_step_complete(pipeline_run_id: str, step_name: str, output_payload: dict | None = None) -> None`:
   - Transitions step to `COMPLETED`, storing serialized output payload.
4. `record_step_failure(pipeline_run_id: str, step_name: str, error: Exception | str) -> None`:
   - Transitions step to `FAILED`, recording exception message & stack trace.
5. `get_step_status(pipeline_run_id: str, step_name: str) -> LedgerStatus | None`:
   - Returns current state for a given pipeline run and step.
6. `get_last_run(slug: str) -> Optional[str]`:
   - Retrieves most recent `pipeline_run_id` for a given problem slug to support resumption.
7. `get_completed_steps(pipeline_run_id: str) -> Dict[str, Any]`:
   - Returns a dict of `step_name -> output_payload` for all steps marked `COMPLETED`.

### 3.5 Idempotency & Crash Recovery Mechanics
- When `PipelineOrchestrator.run(slug)` starts:
  1. It queries `StateLedger` for existing `pipeline_run_id` for `slug`.
  2. For each pipeline step in sequence (`scraper` -> `tags` -> `rag` -> `script` -> `voice` -> `manim` -> `assembly` -> `youtube` -> `memory`):
     - If step status == `COMPLETED`: Load `output_payload` from ledger and skip re-execution.
     - If step status in (`PENDING`, `FAILED`, `IN_PROGRESS`): Execute or re-execute the step, update ledger to `IN_PROGRESS` then `COMPLETED` or `FAILED`.
- Crash Simulation Test Requirement (`tests/orchestrator/test_state_ledger.py`):
  - Must simulate process interruption after step $N$ (e.g. mock exception or process kill).
  - Verify that re-running orchestrator with the same DB file skips steps $1..N$ and resumes execution from step $N+1$.

---

## 4. Verification & Build Command Findings

- **Build / Environment Check**:
  - Python Environment: `/home/adarsh/Documents/Youtube-Channel/.venv` (Python 3.13.7).
  - Test Command: `.venv/bin/pytest tests/ingestion/test_parser.py tests/rag/test_vector_store.py tests/core/`
  - Output: 43 passing tests in 0.44 seconds.
