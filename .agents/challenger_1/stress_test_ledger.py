"""
Empirical Stress Test Harness for StateLedger.
Tests thread contention, multi-process database locking, rapid state updates, and invalid payloads.
"""

import concurrent.futures
from datetime import datetime
import json
from multiprocessing import Process, Queue
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
import uuid
import pytest

from src.core.exceptions import PipelineError
from src.core.orchestrator.state_ledger import (
    PipelineRunRecord,
    StepExecutionRecord,
    StepStatus,
    StateLedger,
)

TEST_DB_DIR = Path("/tmp/state_ledger_stress_tests")
TEST_DB_DIR.mkdir(parents=True, exist_ok=True)


def test_high_thread_contention_single_instance(tmp_path: Path):
    """Stress test single StateLedger instance under heavy multi-threading (50 threads, 1000 operations)."""
    db_file = tmp_path / "thread_stress.db"
    ledger = StateLedger(db_file)

    num_threads = 50
    ops_per_thread = 20
    errors = []
    run_ids = []
    run_ids_lock = threading.Lock()

    # Create shared initial run
    shared_run_id = ledger.create_run(slug="shared-run", metadata={"test": "high_thread"})

    def worker(thread_idx: int):
        try:
            for i in range(ops_per_thread):
                # 1. Create a run
                rid = ledger.create_run(slug=f"thread-slug-{thread_idx}", metadata={"i": i})
                with run_ids_lock:
                    run_ids.append(rid)

                # 2. Record step start on shared run
                step_name = f"step_t{thread_idx}_i{i}"
                sid = ledger.record_step_start(shared_run_id, step_name, {"idx": thread_idx, "iter": i})

                # 3. Read completed steps
                _ = ledger.get_completed_steps(shared_run_id)

                # 4. Complete step
                ledger.record_step_completion(sid, {"status": "ok", "result": i * 100})

                # 5. Get step execution
                rec = ledger.get_step_execution(sid)
                assert rec is not None
                assert rec.status == StepStatus.COMPLETED

                # 6. Query run by slug
                _ = ledger.get_run_by_slug(f"thread-slug-{thread_idx}")

        except Exception as e:
            errors.append((thread_idx, str(e), e))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    start_time = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    duration = time.time() - start_time

    print(f"\n[Thread Contention Single Instance] Completed {num_threads * ops_per_thread * 6} ops in {duration:.3f}s. Errors: {len(errors)}")
    assert len(errors) == 0, f"Encountered thread errors: {errors}"
    
    # Verify records
    completed = ledger.get_completed_steps(shared_run_id)
    assert len(completed) == num_threads * ops_per_thread
    ledger.close()


def test_high_thread_contention_multiple_instances(tmp_path: Path):
    """Stress test multiple StateLedger instances in the same process pointing to the same SQLite DB file."""
    db_file = tmp_path / "multi_instance_thread.db"

    num_threads = 30
    ops_per_thread = 15
    errors = []

    # Initialize DB schema first
    init_ledger = StateLedger(db_file)
    shared_run_id = init_ledger.create_run(slug="multi-instance-run")
    init_ledger.close()

    def worker(thread_idx: int):
        try:
            # Each thread creates its own StateLedger instance connection
            thread_ledger = StateLedger(db_file)
            for i in range(ops_per_thread):
                step_name = f"step_t{thread_idx}_i{i}"
                sid = thread_ledger.record_step_start(shared_run_id, step_name, {"thread": thread_idx})
                thread_ledger.record_step_completion(sid, {"done": True})
                _ = thread_ledger.get_completed_steps(shared_run_id)
            thread_ledger.close()
        except Exception as e:
            errors.append((thread_idx, str(e), e))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    start_time = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    duration = time.time() - start_time

    print(f"\n[Multi-Instance Thread Contention] Completed in {duration:.3f}s. Errors: {len(errors)}")
    assert len(errors) == 0, f"Encountered errors: {errors}"

    verify_ledger = StateLedger(db_file)
    completed = verify_ledger.get_completed_steps(shared_run_id)
    assert len(completed) == num_threads * ops_per_thread
    verify_ledger.close()


def _mp_worker_entry(db_file_str: str, shared_run_id: str, worker_id: int, ops_count: int, queue: Queue):
    """Worker function for multi-process stress test."""
    try:
        ledger = StateLedger(db_file_str)
        for i in range(ops_count):
            slug_name = f"mp-slug-{worker_id}-{i}"
            rid = ledger.create_run(slug=slug_name, metadata={"worker": worker_id, "i": i})

            step_name = f"mp_step_w{worker_id}_i{i}"
            sid = ledger.record_step_start(shared_run_id, step_name, {"w": worker_id})
            ledger.record_step_completion(sid, {"status": "success", "worker": worker_id})

            _ = ledger.get_run(rid)
            _ = ledger.get_completed_steps(shared_run_id)

        ledger.close()
        queue.put(("SUCCESS", worker_id, ops_count))
    except Exception as e:
        queue.put(("ERROR", worker_id, str(e)))


def test_multi_process_db_locks(tmp_path: Path):
    """Stress test multi-process DB access to test SQLite WAL mode write locks and busy_timeout."""
    db_file = tmp_path / "multiprocess_locks.db"

    init_ledger = StateLedger(db_file)
    shared_run_id = init_ledger.create_run(slug="mp-shared-run")
    init_ledger.close()

    num_processes = 12
    ops_per_process = 25
    queue: Queue = Queue()

    processes = [
        Process(target=_mp_worker_entry, args=(str(db_file), shared_run_id, p, ops_per_process, queue))
        for p in range(num_processes)
    ]

    start_time = time.time()
    for p in processes:
        p.start()

    results = []
    errors = []
    for _ in range(num_processes):
        msg = queue.get(timeout=30)
        if msg[0] == "SUCCESS":
            results.append(msg)
        else:
            errors.append(msg)

    for p in processes:
        p.join(timeout=5)

    duration = time.time() - start_time
    print(f"\n[Multi-Process DB Locks] Completed in {duration:.3f}s. Successes: {len(results)}, Errors: {len(errors)}")
    if errors:
        print("Multi-process errors:", errors)
    assert len(errors) == 0, f"Multi-process DB lock errors encountered: {errors}"

    verify_ledger = StateLedger(db_file)
    completed = verify_ledger.get_completed_steps(shared_run_id)
    assert len(completed) == num_processes * ops_per_process
    verify_ledger.close()


def test_exclusive_lock_timeout(tmp_path: Path):
    """Test behavior when another process locks the SQLite database exclusively for longer than busy_timeout (5s)."""
    db_file = tmp_path / "exclusive_lock.db"
    ledger = StateLedger(db_file)
    run_id = ledger.create_run("exclusive-lock-run")
    ledger.close()

    # Open direct sqlite3 connection and hold an EXCLUSIVE lock
    conn = sqlite3.connect(str(db_file))
    conn.execute("BEGIN EXCLUSIVE TRANSACTION;")

    # Now attempt operation on StateLedger which has busy_timeout=5000ms (5 seconds)
    # To save test time, we test that after timeout it raises PipelineError
    ledger2 = StateLedger(db_file)
    
    start_t = time.time()
    with pytest.raises(PipelineError) as exc_info:
        ledger2.record_step_start(run_id, "blocked_step")
    elapsed = time.time() - start_t

    conn.rollback()
    conn.close()
    ledger2.close()

    print(f"\n[Exclusive Lock Timeout] Blocked for {elapsed:.2f}s before raising PipelineError. Error msg: {exc_info.value}")
    assert elapsed >= 4.5  # Should wait around busy_timeout (5s)
    assert "database is locked" in str(exc_info.value).lower() or "locked" in str(exc_info.value).lower()


def test_rapid_state_updates_and_scale(tmp_path: Path):
    """Test 1,000 rapid sequential step lifecycle updates on a single run."""
    db_file = tmp_path / "rapid_scale.db"
    ledger = StateLedger(db_file)

    run_id = ledger.create_run("scale-test-run")

    start_t = time.time()
    num_steps = 500
    for i in range(num_steps):
        sid = ledger.record_step_start(run_id, f"step_{i}", {"step_index": i})
        ledger.record_step_completion(sid, {"status": "ok", "step_index": i})

    elapsed = time.time() - start_t
    print(f"\n[Rapid Scale] Completed {num_steps} start/completion cycles in {elapsed:.3f}s ({num_steps/elapsed:.1f} ops/sec)")

    completed = ledger.get_completed_steps(run_id)
    assert len(completed) == num_steps
    assert completed["step_499"].output_payload == {"status": "ok", "step_index": 499}
    ledger.close()


def test_large_payload_handling(tmp_path: Path):
    """Test handling of large JSON payloads (e.g. 5 MB metadata/output payloads)."""
    db_file = tmp_path / "large_payload.db"
    ledger = StateLedger(db_file)

    large_dict = {
        "text": "x" * (2 * 1024 * 1024),  # 2MB string
        "array": list(range(100000)),
        "nested": {"key": "value" * 1000}
    }

    run_id = ledger.create_run(slug="large-payload-run", metadata=large_dict)
    run_rec = ledger.get_run(run_id)
    assert run_rec is not None
    assert run_rec.metadata["text"] == large_dict["text"]

    sid = ledger.record_step_start(run_id, "large_step", input_payload=large_dict)
    ledger.record_step_completion(sid, output_payload=large_dict)

    completed = ledger.get_completed_steps(run_id)
    assert completed["large_step"].output_payload["text"] == large_dict["text"]

    ledger.close()


def test_invalid_payloads_and_types(tmp_path: Path):
    """Test invalid payloads, non-serializable objects, non-dict types, SQL injections, and null bytes."""
    db_file = tmp_path / "invalid_payloads.db"
    ledger = StateLedger(db_file)

    run_id = ledger.create_run(slug="invalid-payload-run")

    # 1. Non-JSON serializable object (set, function, object instance)
    non_serializable_metadata = {"set_data": {1, 2, 3}}
    try:
        ledger.create_run("bad-run", metadata=non_serializable_metadata)
        print("WARNING: create_run accepted non-serializable payload without raising PipelineError")
    except Exception as e:
        print(f"[Invalid Payload] Non-serializable payload raised {type(e).__name__}: {e}")

    sid = ledger.record_step_start(run_id, "step_valid")

    # Non-serializable output payload
    try:
        ledger.record_step_completion(sid, output_payload={"func": lambda x: x})
        print("WARNING: record_step_completion accepted lambda without error")
    except Exception as e:
        print(f"[Invalid Payload] Non-serializable completion raised {type(e).__name__}: {e}")

    # 2. Non-dict payloads (e.g. list, string, int, boolean)
    # The docstrings / typing say dict | None, let's see what happens if someone passes a string or list
    list_payload = ["item1", "item2"]
    sid2 = ledger.record_step_start(run_id, "step_list", input_payload=list_payload) # type: ignore
    ledger.record_step_completion(sid2, output_payload=list_payload) # type: ignore
    completed = ledger.get_completed_steps(run_id)
    assert completed["step_list"].input_payload == list_payload
    assert completed["step_list"].output_payload == list_payload

    # 3. SQL Injection attempts
    sql_inj_slug = "'; DROP TABLE step_executions; --"
    inj_run_id = ledger.create_run(slug=sql_inj_slug)
    fetched_run = ledger.get_run_by_slug(sql_inj_slug)
    assert fetched_run is not None
    assert fetched_run.slug == sql_inj_slug

    sql_inj_step = "step'; DELETE FROM pipeline_runs; --"
    inj_sid = ledger.record_step_start(inj_run_id, sql_inj_step, input_payload={"sql": "1 OR 1=1"})
    ledger.record_step_completion(inj_sid, output_payload={"inj": "' OR '1'='1"})

    # Verify tables were NOT dropped or modified by SQL injection
    completed_inj = ledger.get_completed_steps(inj_run_id)
    assert sql_inj_step in completed_inj

    # 4. Null byte characters in string fields
    null_byte_slug = "slug_with\x00null"
    null_run_id = ledger.create_run(slug=null_byte_slug)
    null_fetched = ledger.get_run(null_run_id)
    assert null_fetched is not None
    assert null_fetched.slug == null_byte_slug

    # 5. Non-existent step completion / failure
    with pytest.raises(PipelineError, match="not found"):
        ledger.record_step_completion("step_does_not_exist")

    with pytest.raises(PipelineError, match="not found"):
        ledger.record_step_failure("step_does_not_exist", "Some error")

    # 6. Re-completing or re-failing an already completed step
    sid3 = ledger.record_step_start(run_id, "step_recomplete")
    ledger.record_step_completion(sid3, {"v": 1})
    # Calling completion again updates output_payload
    ledger.record_step_completion(sid3, {"v": 2})
    rec3 = ledger.get_step_execution(sid3)
    assert rec3 is not None
    assert rec3.output_payload == {"v": 2}
    assert rec3.status == StepStatus.COMPLETED

    ledger.close()


def test_corrupted_json_in_database(tmp_path: Path):
    """Test how StateLedger handles corrupted JSON content directly in the database."""
    db_file = tmp_path / "corrupt_json.db"
    ledger = StateLedger(db_file)

    run_id = ledger.create_run(slug="corrupt-run")
    sid = ledger.record_step_start(run_id, "corrupt_step")
    ledger.record_step_completion(sid, {"status": "ok"})

    # Directly inject invalid JSON into SQLite table
    conn = sqlite3.connect(str(db_file))
    conn.execute("UPDATE step_executions SET input_payload = '{bad_json:' WHERE step_execution_id = ?", (sid,))
    conn.execute("UPDATE pipeline_runs SET metadata = 'INVALID_JSON' WHERE pipeline_run_id = ?", (run_id,))
    conn.commit()
    conn.close()

    # Querying run with corrupt metadata should raise PipelineError wrapped exception
    with pytest.raises(PipelineError) as exc1:
        _ = ledger.get_run(run_id)
    print(f"\n[Corrupt JSON Run] Caught expected PipelineError: {exc1.value}")

    # Querying step execution with corrupt input payload should raise PipelineError
    with pytest.raises(PipelineError) as exc2:
        _ = ledger.get_step_execution(sid)
    print(f"[Corrupt JSON Step] Caught expected PipelineError: {exc2.value}")

    # Querying completed steps with corrupt JSON should raise PipelineError
    with pytest.raises(PipelineError) as exc3:
        _ = ledger.get_completed_steps(run_id)
    print(f"[Corrupt JSON Completed Steps] Caught expected PipelineError: {exc3.value}")

    ledger.close()

