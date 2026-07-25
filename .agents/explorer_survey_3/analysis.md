# Analysis Report: PromptBook Conventions & Phase 04 Runtime Architecture Specification

**Author:** Explorer 3 (Phase 04 Survey Agent)  
**Target File:** `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_survey_3/analysis.md`  
**Date:** 2026-07-25  

---

## Executive Summary

This report delivers a thorough architectural investigation of the `PromptBook/` documentation ecosystem across Phase 01, Phase 02, and Phase 03 in `/home/adarsh/Documents/Youtube-Channel`. Furthermore, it synthesizes the exact requirements for updating `PromptBook/Phase04/01_Runtime_Architecture.md` to mandate an **SQLite State Ledger** (`src/core/orchestrator/state_ledger.py`), **crash safety & recovery logic**, and **strict adherence to the Synchronous Batch-Pipeline paradigm**.

---

## 1. Survey of PromptBook Structure & Conventions (Phases 01–03)

### 1.1 Directory & Filing Conventions
- **Root Architecture Specifications**: `PromptBook/` contains core project rules (`01_Global_Rules.md`, `02_Project_Architecture.md`, `03_Project_Standards.md`, `04_Folder_Structure.md`).
- **Phase Subdirectories**: Phased milestones are organized in dedicated folders (`Phase01/`, `Phase02/`, `Phase03/`, `Phase04/`).
- **Document Naming**: Files use double-digit numerical prefixes indicating logical ordering (e.g., `01_Ingestion_Strategy.md`, `02_Document_Pipeline.md`, `01_RAG_Architecture.md`).

### 1.2 Document Formatting & Structural Conventions
Across all canonical PromptBook documents, a standard Markdown layout is strictly enforced:

1. **Document Header Metadata Block**:
   ```markdown
   # Phase0X: Title
   **Author:** Principal Software Architect / Domain Architect
   **Target System:** Automated DSA Educational YouTube Video Pipeline
   **Target Environment:** Intel Core Ultra 7 155H · Ubuntu 25.10 LTS · Python 3.12 · Intel Arc GPU
   **Document Version:** X.Y.Z
   **Date / Last Updated:** [Date]
   **Status:** Canonical / Draft / Approved
   ```
2. **Table of Contents (TOC)**: Required for all documents exceeding 100 lines, with relative anchor links matching section headers.
3. **Section Hierarchy**:
   - `# Document Title` (Level 1)
   - `## 1. Executive Summary & Overview` (Level 2 with numbered sections)
   - `### 1.1 Subsection` (Level 3 for component breakdown)
4. **Callout / Alert Blocks**:
   - `> [!IMPORTANT]` for core architectural rules and mandates.
   - `> [!CAUTION]` or `> [!WARNING]` for anti-patterns and prohibited abstractions.
   - `> [!NOTE]` for implementation hints and environmental defaults.
5. **Tabular Specifications**: Complex contracts (metadata fields, hardware contracts, component inventories, change logs) are structured using Markdown tables.
6. **Code & Schema Blocks**: Explicit syntax highlighting for Python dataclasses (`python`), SQL DDL (`sql`), bash commands (`bash`), and JSON payloads (`json`).

### 1.3 Tone & Architectural Voice
- **Authoritative & Prescriptive**: Uses normative keywords (`MUST`, `MUST NOT`, `STRICTLY FORBIDDEN`, `REQUIRED`).
- **Explicit Anti-Patterns**: Every specification explicitly enumerates prohibited patterns (e.g., "What It Is — And Is Not", "Things Explicitly Avoided").
- **Zero Ambiguity**: Avoids pseudo-code where concrete types and dataclasses can be declared; specifies exact file paths (e.g. `src/core/orchestrator/state_ledger.py`) and line-level responsibilities.

### 1.4 Architectural Diagramming Standards
- **ASCII Flow Diagrams**: Monospaced text box diagrams showing linear pipeline flow and module boundaries.
- **Mermaid Diagrams**:
  - `mermaid graph TD` / `graph LR` for component flow and data lineage.
  - `mermaid sequenceDiagram` for inter-component message exchange and execution sequence.
  - `mermaid stateDiagram-v2` for state transitions (`PENDING` -> `IN_PROGRESS` -> `COMPLETED` / `FAILED`).

---

## 2. Requirements for `PromptBook/Phase04/01_Runtime_Architecture.md`

`PromptBook/Phase04/01_Runtime_Architecture.md` currently details the entry point and CLI composition root, but completely lacks specification of the **SQLite State Ledger**, **crash safety PRAGMAs**, and **idempotent step recovery logic** required by `ORIGINAL_REQUEST.md` (Phase 04).

Below are the exact requirements to be integrated into `PromptBook/Phase04/01_Runtime_Architecture.md`.

---

### 2.1 Component 1: SQLite State Ledger Schema & Specifications

The State Ledger must be implemented in `src/core/orchestrator/state_ledger.py` using standard library `sqlite3`. It provides persistent execution state tracking for every step in the 9-stage video pipeline.

#### A. Database Storage & Configuration
- **Database Path**: `data/state/pipeline_ledger.db` (configurable via `PipelineConfig.state_db_path`).
- **Engine**: Python standard library `sqlite3`. Pure SQLite with zero external ORM dependencies (no SQLAlchemy, Peewee, or Tortoise).

#### B. Relational Schema (SQL DDL)

```sql
-- Pipeline Execution Runs Table
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    problem_slug TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT
);

-- Step Execution Ledger Table
CREATE TABLE IF NOT EXISTS step_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED')),
    input_hash TEXT,
    output_payload_json TEXT,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    UNIQUE (run_id, step_name)
);

-- Performance & Lookup Indexes
CREATE INDEX IF NOT EXISTS idx_runs_slug_status ON runs(problem_slug, status);
CREATE INDEX IF NOT EXISTS idx_steps_run_order ON step_executions(run_id, step_order);
CREATE INDEX IF NOT EXISTS idx_steps_run_status ON step_executions(run_id, status);
```

#### C. Python Domain Dataclasses & Enums

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any

class StepStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass(frozen=True)
class PipelineRunRecord:
    run_id: str
    problem_slug: str
    status: StepStatus
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

@dataclass(frozen=True)
class StepExecutionRecord:
    run_id: str
    step_name: str
    step_order: int
    status: StepStatus
    input_hash: Optional[str] = None
    output_payload_json: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
```

---

### 2.2 Component 2: Recovery Logic & Crash Safety Architecture

#### A. SQLite PRAGMA Configuration
To guarantee high performance, thread safety, and crash-safe transactional integrity on local SSDs, `StateLedger` MUST execute the following PRAGMAs immediately upon connection opening:

```sql
PRAGMA journal_mode = WAL;         -- Write-Ahead Logging for high concurrency & atomic persistence
PRAGMA synchronous = NORMAL;       -- Fast write performance with zero corruption risk in WAL mode
PRAGMA foreign_keys = ON;          -- Enforce cascade integrity between runs and step_executions
PRAGMA busy_timeout = 5000;        -- Wait up to 5000ms if database is locked by concurrent readers
```

#### B. Transactional Integrity & Context Management
- All write operations (`start_run`, `start_step`, `complete_step`, `fail_step`) MUST execute within explicit transactions (`BEGIN IMMEDIATE ... COMMIT / ROLLBACK`).
- Context manager pattern in `StateLedger`:
  ```python
  @contextmanager
  def transaction(self):
      conn = self._get_connection()
      try:
          conn.execute("BEGIN IMMEDIATE")
          yield conn
          conn.commit()
      except Exception:
          conn.rollback()
          raise
  ```

#### C. Thread Safety
- Multi-thread access (e.g. parallel Voice/Manim execution) MUST use `sqlite3.connect(check_same_thread=False)` paired with a reentrant lock (`threading.RLock()`) or thread-local connections to guarantee thread-safe transaction execution without database corruption.

#### D. Crash Recovery & Idempotent Resume Workflow
1. **Startup Inspection**: When `PipelineOrchestrator.run(slug)` is invoked:
   - Queries `runs` table for an existing run matching `problem_slug` with status `IN_PROGRESS` or `FAILED`.
2. **State Reconciliation**:
   - If an existing run is found:
     - Steps with status `COMPLETED` are loaded; their cached outputs (`output_payload_json`) are restored.
     - Any step left in status `IN_PROGRESS` at crash time is updated to `FAILED` (or reset to `PENDING`).
     - Pipeline execution resumes synchronously from the first uncompleted step (`PENDING` or `FAILED`).
   - If no existing run is found (or if `--force-regenerate` flag is passed):
     - A new `run_id` (UUIDv4) is generated.
     - All 9 pipeline steps (`scraper`, `tags`, `rag`, `script`, `voice`, `manim`, `assembly`, `youtube`, `memory`) are registered in `step_executions` with status `PENDING`.

#### E. Artificial Crash Verification Strategy
The test suite `tests/orchestrator/test_state_ledger.py` MUST verify crash recovery:
- Simulate process termination mid-pipeline execution (after Step 3 `rag`).
- Re-instantiate `StateLedger` pointing to the same SQLite disk file.
- Verify `StateLedger.get_resume_state(slug)` returns `COMPLETED` for Steps 1–3 and `PENDING` for Step 4 (`script`).
- Confirm execution resumes seamlessly without re-running Steps 1–3.

---

### 2.3 Component 3: Synchronous Batch-Pipeline Paradigm Compliance

`01_Runtime_Architecture.md` MUST explicitly reinforce alignment with the core project architecture:

1. **Single Composition Root**: `src/__main__.py` parses CLI arguments, loads configuration, configures `structlog`, initializes `StateLedger`, instantiates the 9 concrete pipeline modules, and injects them into `PipelineOrchestrator`.
2. **No DI Container Framework**: Direct constructor dependency injection. No auto-wiring or reflection.
3. **Synchronous Execution Flow**:
   - Steps execute sequentially in linear order:
     `Scraper` -> `Tags` -> `RAG` -> `Script` -> `Voice` -> `Manim` -> `Assembly` -> `YouTube` -> `Memory`.
   - Before executing step $i$, orchestrator calls `ledger.start_step(run_id, step_name)`.
   - After successful execution, orchestrator calls `ledger.complete_step(run_id, step_name, payload)`.
   - On error, orchestrator calls `ledger.fail_step(run_id, step_name, error_message)`.
4. **No Async Event Loop or Message Queues**:
   - `asyncio`, pub/sub event buses, RabbitMQ, Redis, and Dead-Letter Queues (DLQ) are strictly forbidden in runtime orchestration.

---

## 3. Recommended Structure for `PromptBook/Phase04/01_Runtime_Architecture.md` Revision

To ensure complete coverage of Phase 04 requirements while preserving existing composition root documentation, the updated document should be structured as follows:

```markdown
# Phase04/01_Runtime_Architecture.md — Runtime Architecture & State Ledger Specification

1. Executive Summary
2. Architectural Alignment Statement & Synchronous Batch Paradigm
3. Composition Root & Runtime Entry Point (src/__main__.py)
4. State Ledger Schema & Specifications (src/core/orchestrator/state_ledger.py)
   4.1 Relational Schema & DDL
   4.2 Dataclasses & Status Enums
   4.3 Serialization & Payload Storage
5. Crash Safety & Recovery Architecture
   5.1 SQLite PRAGMA Configuration
   5.2 Transactional Integrity & Context Management
   5.3 Idempotent Resume State Machine Workflow
   5.4 Artificial Crash Testing & Verification Contract
6. Runtime Startup & Shutdown Sequences
7. Error Handling & Module Criticality Matrix
8. Visualizations (Mermaid State Machine & Sequence Diagrams)
9. Change Log (Appendix A)
```

---

## Summary of Findings & Next Steps

1. **PromptBook Quality**: PromptBook documentation is clean, rigorous, and highly structured across Phases 01–03.
2. **Phase 04 Gap**: `PromptBook/Phase04/01_Runtime_Architecture.md` currently covers CLI composition root but lacks SQLite State Ledger schema, recovery logic, and PRAGMA specifications.
3. **Actionable Roadmap**: Explorer 3 has fully detailed the State Ledger schema, DDL, PRAGMA rules, recovery algorithm, and synchronous paradigm constraints required to update `PromptBook/Phase04/01_Runtime_Architecture.md`.
