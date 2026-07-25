# Phase 04 Survey Analysis: Test Suite Patterns, Execution & SQLite Crash Simulation

## 1. Executive Summary

This report presents a comprehensive investigation into the existing test infrastructure of the Automated DSA Educational YouTube Video Pipeline repository (`/home/adarsh/Documents/Youtube-Channel/`). It establishes the testing patterns, fixture conventions, pytest configuration, execution commands, and a complete programmatic strategy for simulating SQLite artificial crashes and validating crash recovery in pytest for Phase 04 (`StateLedger`).

Key findings:
- **Test Runner & Virtual Environment**: Tests must be executed using `./.venv/bin/pytest` as pytest is installed inside the project's virtual environment.
- **Current Passing Test Scope**: Core infrastructure (`tests/core/`), Phase 02 Ingestion (`tests/ingestion/test_parser.py`), and Phase 03 RAG (`tests/rag/test_vector_store.py`, `tests/rag/test_embedder.py`) total 43 passing tests.
- **Target Test File Path**: As mandated by `ORIGINAL_REQUEST.md` (Phase 04 acceptance criteria), the state ledger test suite must be located at `tests/orchestrator/test_state_ledger.py` and executed via `./.venv/bin/pytest tests/orchestrator/test_state_ledger.py`.
- **SQLite Crash Simulation Strategy**: A disk-backed SQLite database using pytest's `tmp_path` fixture (`tmp_path / "state_ledger.db"`) paired with step-level disconnection/exception injection or OS-level `SIGKILL` child process termination provides complete programmatic crash simulation and idempotency validation.

---

## 2. Existing Test Suite Architecture & Patterns

### 2.1 Pytest Configuration Files
1. **`pytest.ini`** (Root directory):
   ```ini
   [pytest]
   addopts = --strict-markers --cov=src --cov-report=term-missing -v
   testpaths = tests
   markers =
       unit: Fast, isolated unit tests that do not touch the filesystem or network.
       integration: Tests that wire multiple modules together or hit the local filesystem.
       e2e: Full end-to-end pipeline execution tests.
       performance: Slow execution tests profiling time/memory (e.g. video rendering).
   ```
2. **`pyproject.toml`** (Root directory):
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   pythonpath = ["."]
   addopts = "-v --tb=short"
   ```
   *Note*: `pytest.ini` takes precedence over `pyproject.toml` when pytest runs.

### 2.2 Global Fixtures (`tests/conftest.py`)
- **`os.environ["ENVIRONMENT"] = "testing"`**: Explicitly forces test environment configuration on import.
- **`temp_data_dir(tmp_path: Path) -> Path`**: Creates an isolated temporary directory `tmp_path / "data"`.
- **`test_config(temp_data_dir: Path) -> PipelineConfig`**: Returns a deterministic `PipelineConfig` instance re-routing data directory to `temp_data_dir`.
- **`mock_logger(mocker: Any) -> MagicMock`**: Patches `src.core.logger.get_logger` via `pytest-mock` to prevent terminal noise.
- **`mock_problem_factory() -> Callable[..., dict[str, Any]]`**: Generates synthetic problem dictionaries for tests.

### 2.3 Existing Module Test Patterns

| Test Suite Module | Test Files | Fixture & Mocking Strategy | Assertion Style |
| :--- | :--- | :--- | :--- |
| **Core (`tests/core/`)** | `test_base.py`, `test_config.py`, `test_exceptions.py`, `test_logger.py` | Pure unit tests, `tmp_path`, `mocker` for logger patching | Standard `assert`, `pytest.raises` |
| **Ingestion (`tests/ingestion/`)** | `test_parser.py` | Markdown/HTML fixtures in `tests/fixtures/ingestion/` (`load_fixture()`) | Dataclass validation, immutability checks (`FrozenInstanceError`), entity unescaping checks |
| **RAG (`tests/rag/`)** | `test_vector_store.py`, `test_embedder.py` | Ephemeral `ChromaVectorStore(is_test=True)` and `MockEmbedder()` | Dataclass serialization, embedding chunk count, metadata filter verification, delete operations |

---

## 3. Test Execution Commands

Since pytest is installed in the local `.venv`, tests must be run using `./.venv/bin/pytest`.

### 3.1 Standard Test Execution Commands
- **Run all active phase tests (Core, Ingestion, RAG)**:
  ```bash
  ./.venv/bin/pytest tests/core/ tests/ingestion/ tests/rag/
  ```
- **Run Phase 01 Core tests**:
  ```bash
  ./.venv/bin/pytest tests/core/
  ```
- **Run Phase 02 Ingestion tests**:
  ```bash
  ./.venv/bin/pytest tests/ingestion/test_parser.py
  ```
- **Run Phase 03 RAG tests**:
  ```bash
  ./.venv/bin/pytest tests/rag/test_vector_store.py tests/rag/test_embedder.py
  ```
- **Run Phase 04 State Ledger target test suite**:
  ```bash
  ./.venv/bin/pytest tests/orchestrator/test_state_ledger.py
  ```

### 3.2 Useful Pytest Flags
- `-v`: Verbose output.
- `--tb=short`: Short tracebacks for quick debugging.
- `-k "test_pattern"`: Filter tests by pattern (e.g. `./.venv/bin/pytest -k "crash"`).
- `-m unit`: Run only unit-marked tests.
- `--cov=src/core/orchestrator`: Generate code coverage report for the orchestrator module.

---

## 4. Programmatic SQLite Crash Simulation & Recovery Validation

### 4.1 Fundamentals of SQLite Ledger Persistence in Phase 04
To satisfy Requirement R1 and R2 of Phase 04:
- The ledger tracks step execution statuses: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`.
- Standard `sqlite3` must be used with explicit PRAGMAs:
  - `PRAGMA journal_mode=WAL;` (Write-Ahead Logging for concurrency and crash resistance)
  - `PRAGMA synchronous=NORMAL;` (Optimal durability for WAL)
  - `PRAGMA busy_timeout=5000;` (Wait up to 5s if table is locked)
  - `PRAGMA foreign_keys=ON;`
- **Crucial Rule**: Crash simulation tests CANNOT use `:memory:`. They MUST use a file-backed SQLite database stored on disk (e.g., `db_path = tmp_path / "test_ledger.db"`).

---

### 4.2 Programmatic Crash Simulation & Recovery Techniques

#### Strategy A: Instance Re-instantiation / Process Restart Simulation (Recommended Primary Pattern)
Simulates an abrupt process termination between pipeline steps.

**Workflow**:
1. Instantiate `ledger_1 = StateLedger(db_path)`.
2. Register tasks/pipeline steps (`step_1`, `step_2`, `step_3`).
3. Mark `step_1` as `IN_PROGRESS` -> `COMPLETED`.
4. Mark `step_2` as `IN_PROGRESS`.
5. **Simulate Crash**: Abruptly close or drop `ledger_1` (without completing `step_2` or `step_3`).
6. **Simulate Process Restart**: Instantiate `ledger_2 = StateLedger(db_path)` pointing to the *same* `db_path`.
7. **Verify Recovery**:
   - `ledger_2.get_step_status("step_1")` returns `COMPLETED`.
   - `ledger_2.get_step_status("step_2")` returns `IN_PROGRESS` or `FAILED` (interrupted).
   - `ledger_2.get_uncompleted_steps()` starts execution at `step_2`, skipping `step_1` entirely.
8. Resume pipeline to completion and assert all steps are `COMPLETED`.

#### Strategy B: Exception / Fault Injection Mid-Execution
Simulates an unhandled application exception during a step transition.

**Workflow**:
1. Run a pipeline loop using `StateLedger(db_path)`.
2. Step 1 completes cleanly.
3. During Step 2, raise `RuntimeError("Simulated Power Loss / API Outage")` inside a `pytest.raises` block.
4. Verify that step 2 is marked `FAILED` or remaining in `IN_PROGRESS` with recorded error details.
5. Create a new `StateLedger(db_path)` instance, call `ledger.resume()`, verify step 1 is skipped, step 2 is retried, and the run finishes cleanly.

#### Strategy C: True OS Process Termination via `multiprocessing` / `SIGKILL`
Simulates a hard operating system crash (e.g., `kill -9` or power failure) while writing to SQLite WAL.

**Workflow**:
1. Define a target worker function that opens `StateLedger(db_path)`, begins writing step state changes, and signals a `multiprocessing.Event`.
2. In the main pytest thread, start the worker process (`multiprocessing.Process`).
3. Once the event is set (worker is mid-operation), call `proc.kill()` (`SIGKILL`).
4. Join the process to ensure it is dead.
5. Instantiate `StateLedger(db_path)` in the main test thread.
6. Verify SQLite automatically recovers the WAL file without database corruption and state queries accurately reflect the last committed transaction.

---

### 4.3 Proposed Pytest Code Structure for `tests/orchestrator/test_state_ledger.py`

Below is the concrete blueprint to be provided to Implementer 1 for `tests/orchestrator/test_state_ledger.py`:

```python
"""
Tests for SQLite State Ledger & Crash Recovery (Phase 04).
"""

import pytest
from pathlib import Path
import sqlite3
import multiprocessing
import time

from src.core.orchestrator.state_ledger import StateLedger, LedgerStatus


@pytest.fixture
def ledger_db_path(tmp_path: Path) -> Path:
    """Provides a file-backed SQLite database path for persistent recovery tests."""
    return tmp_path / "state_ledger.db"


@pytest.fixture
def ledger(ledger_db_path: Path) -> StateLedger:
    """Initializes a fresh StateLedger on disk."""
    return StateLedger(db_path=ledger_db_path)


def test_ledger_initialization_and_pragma(ledger_db_path: Path):
    """Verifies SQLite database creation and WAL PRAGMA configuration."""
    ledger = StateLedger(db_path=ledger_db_path)
    assert ledger_db_path.exists()
    
    # Inspect PRAGMA mode directly via standard sqlite3
    conn = sqlite3.connect(ledger_db_path)
    cursor = conn.cursor()
    journal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
    assert journal_mode.lower() == "wal"
    conn.close()


def test_step_lifecycle_transitions(ledger: StateLedger):
    """Tests normal step status transitions: PENDING -> IN_PROGRESS -> COMPLETED."""
    run_id = "run-001"
    step_name = "parse_markdown"

    ledger.init_run(run_id=run_id, steps=[step_name])
    assert ledger.get_status(run_id, step_name) == LedgerStatus.PENDING

    ledger.mark_in_progress(run_id, step_name)
    assert ledger.get_status(run_id, step_name) == LedgerStatus.IN_PROGRESS

    ledger.mark_completed(run_id, step_name, result_metadata={"items": 1})
    assert ledger.get_status(run_id, step_name) == LedgerStatus.COMPLETED


def test_simulated_crash_and_resumption(ledger_db_path: Path):
    """
    Simulates process crash mid-pipeline and verifies idempotency & resumption.
    """
    run_id = "video-two-sum"
    steps = ["scrape", "rag_embed", "script_gen", "render_video"]

    # 1. Process Run 1: Completes step 1, starts step 2, crashes before step 3
    ledger1 = StateLedger(db_path=ledger_db_path)
    ledger1.init_run(run_id, steps)
    
    ledger1.mark_completed(run_id, "scrape", result_metadata={"slug": "two-sum"})
    ledger1.mark_in_progress(run_id, "rag_embed")
    
    # SIMULATED CRASH: Close process handle 1 without completing remaining steps
    del ledger1

    # 2. Process Run 2: Boot new instance pointing to exact same database file on disk
    ledger2 = StateLedger(db_path=ledger_db_path)
    
    # 3. Check recovery state
    assert ledger2.get_status(run_id, "scrape") == LedgerStatus.COMPLETED
    assert ledger2.is_step_completed(run_id, "scrape") is True
    
    uncompleted = ledger2.get_pending_or_interrupted_steps(run_id)
    assert "scrape" not in uncompleted
    assert uncompleted[0] == "rag_embed"

    # 4. Resume execution from interrupted step
    ledger2.mark_completed(run_id, "rag_embed")
    ledger2.mark_completed(run_id, "script_gen")
    ledger2.mark_completed(run_id, "render_video")
    
    assert ledger2.is_run_completed(run_id) is True


def _crash_worker(db_path: str, run_id: str):
    """Worker process that writes to ledger and gets killed mid-way."""
    ledger = StateLedger(db_path=Path(db_path))
    ledger.init_run(run_id, ["step1", "step2"])
    ledger.mark_completed(run_id, "step1")
    ledger.mark_in_progress(run_id, "step2")
    time.sleep(10)  # Intentionally hang so parent can SIGKILL


def test_hard_sigkill_process_crash_recovery(ledger_db_path: Path):
    """
    Simulates OS SIGKILL crash using multiprocessing child process.
    """
    run_id = "sigkill-test-run"
    p = multiprocessing.Process(target=_crash_worker, args=(str(ledger_db_path), run_id))
    p.start()
    
    time.sleep(0.5)  # Let child process initialize DB and write step1
    
    # HARD CRASH SIMULATION
    p.kill()
    p.join()

    # Re-open ledger in main test thread
    ledger = StateLedger(db_path=ledger_db_path)
    assert ledger.get_status(run_id, "step1") == LedgerStatus.COMPLETED
    assert ledger.get_status(run_id, "step2") in (LedgerStatus.IN_PROGRESS, LedgerStatus.PENDING)
```

---

## 5. Summary Recommendations for Phase 04 Implementation

1. **Module & Test Directory Creation**:
   - Source: `src/core/orchestrator/state_ledger.py`
   - Test: `tests/orchestrator/test_state_ledger.py` (ensure directory `tests/orchestrator` is created).
2. **Standard Library `sqlite3` Compliance**:
   - Use standard library `sqlite3` only.
   - Enforce WAL mode (`PRAGMA journal_mode=WAL;`).
   - Use parameter binding (`?`) for all SQL queries to ensure thread-safety and query safety.
3. **Execution Command**:
   - Verify with `./.venv/bin/pytest tests/orchestrator/test_state_ledger.py`.
