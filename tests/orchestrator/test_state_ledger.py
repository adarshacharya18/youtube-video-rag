"""
Unit and Crash Recovery Test Suite for StateLedger.

Tests SQLite DB initialization, WAL mode PRAGMAs, thread safety, step lifecycle management,
in-memory / disk persistence, same-process crash recovery, and multi-process SIGKILL crash safety.
"""

from multiprocessing import Process, Queue
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time
import pytest

from src.core.exceptions import PipelineError
from src.core.orchestrator.state_ledger import (
    PipelineRunRecord,
    StepExecutionRecord,
    StepStatus,
    StateLedger,
)


def test_ledger_initialization_and_pragmas(tmp_path: Path) -> None:
    """Verify StateLedger DB initialization, schema creation, and PRAGMA settings."""
    db_file = tmp_path / "ledger.db"
    ledger = StateLedger(db_file)

    assert db_file.exists()

    # Query PRAGMA settings directly from ledger connection
    cursor = ledger._conn.cursor()

    journal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
    assert journal_mode.lower() == "wal"

    synchronous = cursor.execute("PRAGMA synchronous;").fetchone()[0]
    # 1 corresponds to NORMAL in SQLite (0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA)
    assert synchronous == 1

    foreign_keys = cursor.execute("PRAGMA foreign_keys;").fetchone()[0]
    assert foreign_keys == 1

    busy_timeout = cursor.execute("PRAGMA busy_timeout;").fetchone()[0]
    assert busy_timeout == 5000

    # Verify tables exist
    tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    assert "pipeline_runs" in tables
    assert "step_executions" in tables

    # Verify indexes exist
    indexes = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()]
    assert "idx_step_executions_run_id" in indexes
    assert "idx_pipeline_runs_slug" in indexes

    ledger.close()

    # Also verify journal_mode is persistent on disk for a separate new connection
    conn2 = sqlite3.connect(str(db_file))
    jm2 = conn2.execute("PRAGMA journal_mode;").fetchone()[0]
    assert jm2.lower() == "wal"
    conn2.close()


def test_in_memory_ledger_initialization() -> None:
    """Verify in-memory SQLite StateLedger functionality."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run(slug="in-memory-test", metadata={"env": "test"})
    assert run_id.startswith("run_")

    run_record = ledger.get_run(run_id)
    assert run_record is not None
    assert run_record.slug == "in-memory-test"
    assert run_record.status == StepStatus.PENDING
    assert run_record.metadata == {"env": "test"}

    ledger.close()


def test_create_and_get_run(tmp_path: Path) -> None:
    """Verify run creation, querying by ID, and querying by slug."""
    db_file = tmp_path / "ledger.db"
    ledger = StateLedger(db_file)

    run_id_1 = ledger.create_run(slug="two-sum", metadata={"version": 1})
    run_id_2 = ledger.create_run(slug="two-sum", metadata={"version": 2})

    assert run_id_1 != run_id_2

    record_1 = ledger.get_run(run_id_1)
    assert record_1 is not None
    assert record_1.pipeline_run_id == run_id_1
    assert record_1.slug == "two-sum"
    assert record_1.status == StepStatus.PENDING
    assert record_1.metadata == {"version": 1}

    record_2 = ledger.get_run(run_id_2)
    assert record_2 is not None
    assert record_2.metadata == {"version": 2}

    # get_run_by_slug should return the most recent run (run_id_2)
    latest_slug_record = ledger.get_run_by_slug("two-sum")
    assert latest_slug_record is not None
    assert latest_slug_record.pipeline_run_id == run_id_2

    # Querying non-existent records should return None
    assert ledger.get_run("non_existent_id") is None
    assert ledger.get_run_by_slug("non_existent_slug") is None

    ledger.close()


def test_step_lifecycle_success_path(tmp_path: Path) -> None:
    """Verify complete successful step lifecycle: start, complete, and query completed steps."""
    db_file = tmp_path / "ledger.db"
    ledger = StateLedger(db_file)

    run_id = ledger.create_run(slug="3sum")
    run_record = ledger.get_run(run_id)
    assert run_record is not None
    assert run_record.status == StepStatus.PENDING

    # 1. Start Step 1
    step_1_input = {"slug": "3sum", "timeout": 30}
    step_1_id = ledger.record_step_start(run_id, "scraper", step_1_input)
    assert step_1_id.startswith("step_")

    # Parent run should transition to IN_PROGRESS upon step start
    run_record_updated = ledger.get_run(run_id)
    assert run_record_updated is not None
    assert run_record_updated.status == StepStatus.IN_PROGRESS

    step_1_rec = ledger.get_step_execution(step_1_id)
    assert step_1_rec is not None
    assert step_1_rec.step_name == "scraper"
    assert step_1_rec.status == StepStatus.IN_PROGRESS
    assert step_1_rec.input_payload == step_1_input
    assert step_1_rec.output_payload is None

    # 2. Complete Step 1
    step_1_output = {"title": "3Sum", "difficulty": "Medium"}
    ledger.record_step_completion(step_1_id, step_1_output)

    step_1_completed = ledger.get_step_execution(step_1_id)
    assert step_1_completed is not None
    assert step_1_completed.status == StepStatus.COMPLETED
    assert step_1_completed.output_payload == step_1_output

    # 3. Start & Complete Step 2
    step_2_id = ledger.record_step_start(run_id, "tags", {"tags": ["array", "two-pointers"]})
    step_2_output = {"processed_tags": ["Array", "Two Pointers"]}
    ledger.record_step_completion(step_2_id, step_2_output)

    # 4. Verify get_completed_steps
    completed_map = ledger.get_completed_steps(run_id)
    assert len(completed_map) == 2
    assert "scraper" in completed_map
    assert "tags" in completed_map
    assert completed_map["scraper"].output_payload == step_1_output
    assert completed_map["tags"].output_payload == step_2_output

    ledger.close()


def test_step_lifecycle_failure_path(tmp_path: Path) -> None:
    """Verify step failure recording and automatic parent run FAILED transition."""
    db_file = tmp_path / "ledger.db"
    ledger = StateLedger(db_file)

    run_id = ledger.create_run(slug="trapping-rain-water")
    step_id = ledger.record_step_start(run_id, "voice", {"voice_model": "kokoro"})

    # Record step failure
    error_msg = "Voice synthesis failed due to API rate limit"
    error_details = {"http_code": 429, "retry_after": 60}
    ledger.record_step_failure(step_id, error_msg, error_details)

    step_rec = ledger.get_step_execution(step_id)
    assert step_rec is not None
    assert step_rec.status == StepStatus.FAILED
    assert step_rec.error_message == error_msg
    assert step_rec.error_details == error_details

    # Parent pipeline run must be updated to FAILED
    run_rec = ledger.get_run(run_id)
    assert run_rec is not None
    assert run_rec.status == StepStatus.FAILED

    ledger.close()


def test_error_handling_and_constraints(tmp_path: Path) -> None:
    """Verify exception handling for invalid IDs and closed database connections."""
    db_file = tmp_path / "ledger.db"
    ledger = StateLedger(db_file)

    # Record step start with non-existent pipeline_run_id raises PipelineError
    with pytest.raises(PipelineError, match="does not exist"):
        ledger.record_step_start("invalid_run_id", "scraper")

    # Record completion / failure with non-existent step_execution_id raises PipelineError
    with pytest.raises(PipelineError, match="not found"):
        ledger.record_step_completion("invalid_step_id", {"out": 1})

    with pytest.raises(PipelineError, match="not found"):
        ledger.record_step_failure("invalid_step_id", "Error message")

    # Verify context manager behavior
    with StateLedger(tmp_path / "ctx_ledger.db") as ctx_ledger:
        ctx_run_id = ctx_ledger.create_run("ctx-slug")
        assert ctx_run_id.startswith("run_")

    # Closed ledger operations must raise PipelineError
    ledger.close()
    with pytest.raises(PipelineError, match="Database connection is closed"):
        ledger.create_run("slug")

    with pytest.raises(PipelineError, match="Database connection is closed"):
        ledger.get_run("run_id")


def test_same_process_crash_recovery(tmp_path: Path) -> None:
    """
    Simulate an artificial crash (connection drop/abandonment) and prove state recovery
    when opening a NEW StateLedger instance pointing to the exact same disk file.
    """
    db_file = tmp_path / "crash_recovery.db"

    # --- PROCESS / INSTANCE 1: Start run, complete steps 1 & 2, start step 3, then crash ---
    ledger1 = StateLedger(db_file)
    run_id = ledger1.create_run(slug="binary-search", metadata={"attempt": 1})

    step1_id = ledger1.record_step_start(run_id, "scraper", {"slug": "binary-search"})
    ledger1.record_step_completion(step1_id, {"raw_html": "<html>...</html>"})

    step2_id = ledger1.record_step_start(run_id, "tags", {"input": "raw_html"})
    ledger1.record_step_completion(step2_id, {"tags": ["Binary Search", "Array"]})

    step3_id = ledger1.record_step_start(run_id, "script", {"prompt": "Explain binary search"})
    # Artificial Crash: Abandon ledger1 connection without recording step3 completion or clean exit
    ledger1.close()

    # --- PROCESS / INSTANCE 2: Re-open StateLedger on same disk file ---
    ledger2 = StateLedger(db_file)

    run_record = ledger2.get_run(run_id)
    assert run_record is not None
    assert run_record.slug == "binary-search"
    assert run_record.status == StepStatus.IN_PROGRESS

    completed_steps = ledger2.get_completed_steps(run_id)
    assert len(completed_steps) == 2
    assert "scraper" in completed_steps
    assert "tags" in completed_steps
    assert "script" not in completed_steps

    assert completed_steps["scraper"].output_payload == {"raw_html": "<html>...</html>"}
    assert completed_steps["tags"].output_payload == {"tags": ["Binary Search", "Array"]}

    # Prove resuming execution from Step 3:
    step3_resumed_id = ledger2.record_step_start(run_id, "script", {"prompt": "Explain binary search"})
    ledger2.record_step_completion(step3_resumed_id, {"script_text": "Welcome to Binary Search!"})

    step4_id = ledger2.record_step_start(run_id, "voice", {"text": "Welcome to Binary Search!"})
    ledger2.record_step_completion(step4_id, {"audio_path": "/path/to/audio.mp3"})

    all_completed = ledger2.get_completed_steps(run_id)
    assert len(all_completed) == 4
    assert "script" in all_completed
    assert "voice" in all_completed
    assert all_completed["script"].output_payload == {"script_text": "Welcome to Binary Search!"}

    ledger2.close()


def _worker_process_entry(db_file_str: str, queue: Queue) -> None:
    """Worker function executed in a separate process that gets SIGKILLed mid-execution."""
    try:
        ledger = StateLedger(db_file_str)
        run_id = ledger.create_run(slug="lru-cache", metadata={"worker_pid": os.getpid()})
        queue.put(("RUN_CREATED", run_id))

        # Step 1: Scraper
        s1_id = ledger.record_step_start(run_id, "scraper", {"slug": "lru-cache"})
        ledger.record_step_completion(s1_id, {"description": "Design an LRU Cache"})

        # Step 2: Tags
        s2_id = ledger.record_step_start(run_id, "tags", {"input": "lru-cache"})
        ledger.record_step_completion(s2_id, {"tags": ["Hash Table", "Linked List"]})

        # Step 3: Script (In Progress)
        ledger.record_step_start(run_id, "script", {"prompt": "Generate LRU script"})
        queue.put(("STEP3_STARTED", run_id))

        # Loop forever until SIGKILL arrives from parent
        while True:
            time.sleep(0.1)
    except Exception as e:
        queue.put(("ERROR", str(e)))


def test_multiprocess_sigkill_crash_recovery(tmp_path: Path) -> None:
    """
    Multi-process SIGKILL crash simulation test.
    Proves that when a process writing to SQLite is killed abruptly via SIGKILL (-9),
    the WAL disk ledger remains uncorrupted, last known completed steps are readable,
    and a new StateLedger process can resume execution cleanly.
    """
    db_file = tmp_path / "sigkill_crash.db"
    queue: Queue = Queue()

    proc = Process(target=_worker_process_entry, args=(str(db_file), queue))
    proc.start()

    # Wait for worker process to signal that run is created and Step 3 is started
    msg_type_1, run_id = queue.get(timeout=10)
    assert msg_type_1 == "RUN_CREATED"
    assert run_id.startswith("run_")

    msg_type_2, step3_run_id = queue.get(timeout=10)
    assert msg_type_2 == "STEP3_STARTED"
    assert step3_run_id == run_id

    # Terminate worker process abruptly with SIGKILL (-9)
    assert proc.pid is not None
    os.kill(proc.pid, signal.SIGKILL)
    proc.join(timeout=5)

    assert not proc.is_alive()
    # On Linux, exitcode for SIGKILL is -9 (or -signal.SIGKILL)
    assert proc.exitcode == -signal.SIGKILL or proc.exitcode != 0

    # Open NEW StateLedger instance in parent process on the exact same SQLite file
    ledger = StateLedger(db_file)

    run_record = ledger.get_run(run_id)
    assert run_record is not None
    assert run_record.slug == "lru-cache"

    completed_steps = ledger.get_completed_steps(run_id)
    assert len(completed_steps) == 2
    assert "scraper" in completed_steps
    assert "tags" in completed_steps
    assert "script" not in completed_steps

    assert completed_steps["scraper"].output_payload == {"description": "Design an LRU Cache"}
    assert completed_steps["tags"].output_payload == {"tags": ["Hash Table", "Linked List"]}

    # Prove resuming execution in parent process
    resumed_s3 = ledger.record_step_start(run_id, "script", {"prompt": "Resume LRU script"})
    ledger.record_step_completion(resumed_s3, {"script": "LRU Cache eviction policy..."})

    resumed_completed = ledger.get_completed_steps(run_id)
    assert len(resumed_completed) == 3
    assert "script" in resumed_completed
    assert resumed_completed["script"].output_payload == {"script": "LRU Cache eviction policy..."}

    ledger.close()


def test_thread_safety_concurrent_step_logging(tmp_path: Path) -> None:
    """Verify thread safety when multiple threads interact with the same StateLedger instance."""
    db_file = tmp_path / "thread_safety.db"
    ledger = StateLedger(db_file)
    run_id = ledger.create_run(slug="concurrent-test")

    errors: list[Exception] = []

    def worker_thread(thread_idx: int) -> None:
        try:
            step_name = f"thread_step_{thread_idx}"
            step_id = ledger.record_step_start(run_id, step_name, {"idx": thread_idx})
            time.sleep(0.01)
            ledger.record_step_completion(step_id, {"result": thread_idx * 10})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker_thread, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Thread errors encountered: {errors}"

    completed = ledger.get_completed_steps(run_id)
    assert len(completed) == 10
    for i in range(10):
        step_name = f"thread_step_{i}"
        assert step_name in completed
        assert completed[step_name].output_payload == {"result": i * 10}

    ledger.close()
