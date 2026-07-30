"""Empirical Stress Test & Edge Case Harness for AnimationGeneratorNode (M2)."""

import concurrent.futures
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
import pytest

from src.core.exceptions import AnimationError, PipelineStageError
from src.core.orchestrator.state_ledger import StateLedger
from src.pipeline.nodes.animation_generator_node import AnimationGeneratorNode


def create_mock_manim_script(tmp_path: Path) -> str:
    script_path = tmp_path / "mock_manim.py"
    script_content = """import sys, os, time

media_dir = None
out_arg = "output.mp4"
for i, arg in enumerate(sys.argv):
    if arg == "--media_dir" and i + 1 < len(sys.argv):
        media_dir = sys.argv[i + 1]
    if arg == "-o" and i + 1 < len(sys.argv):
        out_arg = sys.argv[i + 1]

if "--fail" in sys.argv:
    sys.stderr.write("Simulated Manim rendering failure\\n")
    sys.exit(1)

# Artificial delay to simulate heavy rendering
time.sleep(0.02)

if media_dir:
    os.makedirs(media_dir, exist_ok=True)
    out_file = os.path.join(media_dir, out_arg)
    with open(out_file, "wb") as f:
        f.write((b"MOCK_VIDEO_DATA_CONTENT_STRESS_TEST_" + out_arg.encode("utf-8")) * 5)

sys.exit(0)
"""
    script_path.write_text(script_content, encoding="utf-8")
    return str(script_path)


def test_concurrent_rendering_and_caching(tmp_dir: Path):
    """Test concurrent executions with shared cache directory to check race conditions."""
    print("\n--- [1/8] Concurrent Rendering & Cache Race Condition Check ---")
    mock_script = create_mock_manim_script(tmp_dir)
    db_path = tmp_dir / "ledger_concurrent.db"
    ledger = StateLedger(db_path=db_path)

    out_dir = tmp_dir / "renders_concurrent"
    cache_dir = tmp_dir / "cache_concurrent"

    def run_worker(worker_id: int):
        run_id = ledger.create_run(slug=f"concurrent-run-{worker_id}")
        script_payload = {
            "slug": f"concurrent-run-{worker_id}",
            "script": {
                "visual_cues": [
                    {
                        "cue_id": "shared_cue_01",
                        "animation_type": "array_highlight",
                        "timestamp_seconds": 0.0,
                        "parameters": {"shared_key": "shared_value"},
                    },
                    {
                        "cue_id": f"unique_cue_{worker_id}",
                        "animation_type": "tree_traversal",
                        "timestamp_seconds": 5.0,
                        "parameters": {"worker": worker_id},
                    },
                ]
            },
        }
        step_id = ledger.record_step_start(run_id, step_name="script_generator")
        ledger.record_step_completion(step_id, output_payload=script_payload)

        node = AnimationGeneratorNode(
            manim_binary=mock_script,
            quality="low",
            output_dir=out_dir,
            cache_dir=cache_dir,
        )
        return node.execute(run_id=run_id, ledger=ledger)

    results = []
    errors = []
    num_threads = 10
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {executor.submit(run_worker, i): i for i in range(num_threads)}
        for future in concurrent.futures.as_completed(futures):
            worker_id = futures[future]
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                errors.append((worker_id, e))

    elapsed = time.time() - start_time
    print(f"Completed {len(results)} concurrent executions in {elapsed:.2f}s with {len(errors)} errors")
    if errors:
        for w_id, err in errors:
            print(f"  Worker {w_id} failed: {type(err).__name__}: {err}")

    # Validate output files exist and are not truncated/empty
    corrupted_files = []
    for res in results:
        for seg in res["segments"]:
            path = Path(seg["visual_path"])
            if not path.exists() or path.stat().st_size == 0:
                corrupted_files.append(path)

    print(f"Corrupted or missing files in concurrent test: {len(corrupted_files)}")
    return len(errors), len(corrupted_files)


def test_high_volume_fd_leak_check(tmp_dir: Path):
    """Test 50 sequential iterations to verify FD and temp directory leak stability."""
    print("\n--- [2/8] High-Volume FD & Tempdir Leak Check ---")
    mock_script = create_mock_manim_script(tmp_dir)
    db_path = tmp_dir / "ledger_fd.db"
    ledger = StateLedger(db_path=db_path)

    out_dir = tmp_dir / "renders_fd"
    cache_dir = tmp_dir / "cache_fd"

    node = AnimationGeneratorNode(
        manim_binary=mock_script,
        quality="low",
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    fds_before = len(os.listdir("/proc/self/fd"))
    iterations = 50

    for i in range(iterations):
        run_id = ledger.create_run(slug=f"fd-run-{i}")
        script_payload = {
            "slug": f"fd-run-{i}",
            "script": {
                "visual_cues": [
                    {
                        "cue_id": f"cue_fd_{i}",
                        "animation_type": "array_highlight",
                        "timestamp_seconds": 0.0,
                        "parameters": {"iter": i},
                    }
                ]
            },
        }
        step_id = ledger.record_step_start(run_id, step_name="script_generator")
        ledger.record_step_completion(step_id, output_payload=script_payload)
        node.execute(run_id=run_id, ledger=ledger)

    fds_after = len(os.listdir("/proc/self/fd"))
    print(f"FDs before: {fds_before}, FDs after {iterations} iterations: {fds_after}")

    # Check temp file count in system temp directory starting with manim_
    temp_dir = Path(tempfile.gettempdir())
    leftover_manim_temps = list(temp_dir.glob("manim_*"))
    print(f"Leftover manim temp dirs in {temp_dir}: {len(leftover_manim_temps)}")
    return fds_after - fds_before, len(leftover_manim_temps)


def test_path_traversal_in_cue_id(tmp_dir: Path):
    """Test if cue_id containing '../' leads to path traversal outside output directory."""
    print("\n--- [3/8] Path Traversal in cue_id Security Check ---")
    mock_script = create_mock_manim_script(tmp_dir)
    db_path = tmp_dir / "ledger_traversal.db"
    ledger = StateLedger(db_path=db_path)

    out_dir = tmp_dir / "renders_traversal"
    cache_dir = tmp_dir / "cache_traversal"

    node = AnimationGeneratorNode(
        manim_binary=mock_script,
        quality="low",
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    run_id = ledger.create_run(slug="traversal-run")
    escaped_filename = tmp_dir / "escaped_segment.mp4"

    script_payload = {
        "slug": "traversal-run",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "../escaped_segment",
                    "animation_type": "array_highlight",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(step_id, output_payload=script_payload)

    traversal_detected = False
    try:
        res = node.execute(run_id=run_id, ledger=ledger)
        created_path = Path(res["segments"][0]["visual_path"])
        print(f"Path produced for cue_id='../escaped_segment': {created_path}")

        # Check if created_path is outside run_output_dir
        expected_parent = out_dir / run_id
        try:
            created_path.relative_to(expected_parent)
        except ValueError:
            traversal_detected = True
            print(f"SECURITY VULNERABILITY DETECTED: File created outside target directory: {created_path}")
    except Exception as e:
        print(f"Exception during path traversal test: {type(e).__name__}: {e}")

    return traversal_detected


def test_unserializable_parameters(tmp_dir: Path):
    """Test visual cue parameters containing un-serializable JSON types."""
    print("\n--- [4/8] Un-serializable Parameters Handling ---")
    mock_script = create_mock_manim_script(tmp_dir)
    db_path = tmp_dir / "ledger_unserializable.db"
    ledger = StateLedger(db_path=db_path)

    out_dir = tmp_dir / "renders_unserializable"
    cache_dir = tmp_dir / "cache_unserializable"

    node = AnimationGeneratorNode(
        manim_binary=mock_script,
        quality="low",
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    run_id = ledger.create_run(slug="unserializable-run")
    script_payload = {
        "slug": "unserializable-run",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_set_param",
                    "animation_type": "array_highlight",
                    "timestamp_seconds": 0.0,
                    "parameters": {"invalid_set": {1, 2, 3}},
                }
            ]
        },
    }
    raised_error = None
    try:
        step_id = ledger.record_step_start(run_id, step_name="script_generator")
        ledger.record_step_completion(step_id, output_payload=script_payload)
        node.execute(run_id=run_id, ledger=ledger)
    except Exception as e:
        raised_error = e
        print(f"Exception for set in parameters: {type(e).__name__}: {e}")

    return raised_error


def test_malformed_script_payloads(tmp_dir: Path):
    """Test node behavior with missing/malformed script payload fields."""
    print("\n--- [5/8] Malformed Script Payloads ---")
    mock_script = create_mock_manim_script(tmp_dir)
    db_path = tmp_dir / "ledger_malformed.db"
    ledger = StateLedger(db_path=db_path)

    out_dir = tmp_dir / "renders_malformed"
    cache_dir = tmp_dir / "cache_malformed"

    node = AnimationGeneratorNode(
        manim_binary=mock_script,
        quality="low",
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    malformed_cases = [
        ("empty payload", {}),
        ("script is None", {"script": None}),
        ("script is string", {"script": "invalid_string"}),
        ("visual_cues is integer", {"script": {"visual_cues": 12345}}),
        ("visual_cues containing non-dict items", {"script": {"visual_cues": [None, 999, "string_cue"]}}),
        ("cue timestamp is invalid string", {
            "script": {
                "visual_cues": [
                    {
                        "cue_id": "cue_bad_ts",
                        "animation_type": "array_highlight",
                        "timestamp_seconds": "not_a_float",
                        "parameters": {},
                    }
                ]
            }
        }),
        ("cue parameters is string", {
            "script": {
                "visual_cues": [
                    {
                        "cue_id": "cue_str_params",
                        "animation_type": "array_highlight",
                        "parameters": "parameters_as_string",
                    }
                ]
            }
        }),
    ]

    results = []
    for name, payload in malformed_cases:
        run_id = ledger.create_run(slug=f"malformed-{len(results)}")
        step_id = ledger.record_step_start(run_id, step_name="script_generator")
        ledger.record_step_completion(step_id, output_payload=payload)

        try:
            res = node.execute(run_id=run_id, ledger=ledger)
            results.append((name, "HANDLED_SUCCESS", res))
            print(f"  [{name}]: Handled without error, render_count={res['render_count']}")
        except Exception as e:
            results.append((name, f"RAISED_{type(e).__name__}", str(e)))
            print(f"  [{name}]: Raised {type(e).__name__}: {e}")

    return results


def test_corrupt_cache_files(tmp_dir: Path):
    """Test 0-byte, partial, and 1-byte corrupt cache files."""
    print("\n--- [6/8] Corrupt & Boundary Cache File Handling ---")
    mock_script = create_mock_manim_script(tmp_dir)
    db_path = tmp_dir / "ledger_corrupt_cache.db"
    ledger = StateLedger(db_path=db_path)

    out_dir = tmp_dir / "renders_corrupt_cache"
    cache_dir = tmp_dir / "cache_corrupt_cache"

    node = AnimationGeneratorNode(
        manim_binary=mock_script,
        quality="low",
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    cue_params = {"test": 456}
    cache_hash = node._compute_cache_hash("array_highlight", cue_params)
    cache_dir.mkdir(parents=True, exist_ok=True)
    corrupt_cache_file = cache_dir / f"{cache_hash}.mp4"

    # Test 1: 0-byte file
    corrupt_cache_file.write_bytes(b"")
    run_id1 = ledger.create_run(slug="corrupt-cache-0byte")
    step_id1 = ledger.record_step_start(run_id1, step_name="script_generator")
    ledger.record_step_completion(
        step_id1,
        output_payload={
            "script": {
                "visual_cues": [
                    {
                        "cue_id": "cue_0b",
                        "animation_type": "array_highlight",
                        "parameters": cue_params,
                    }
                ]
            }
        },
    )
    res1 = node.execute(run_id=run_id1, ledger=ledger)
    size1 = corrupt_cache_file.stat().st_size
    print(f"  0-byte cache file replaced with size={size1} bytes")

    # Test 2: 1-byte corrupt file
    corrupt_cache_file.write_bytes(b"X")
    run_id2 = ledger.create_run(slug="corrupt-cache-1byte")
    step_id2 = ledger.record_step_start(run_id2, step_name="script_generator")
    ledger.record_step_completion(
        step_id2,
        output_payload={
            "script": {
                "visual_cues": [
                    {
                        "cue_id": "cue_1b",
                        "animation_type": "array_highlight",
                        "parameters": cue_params,
                    }
                ]
            }
        },
    )
    res2 = node.execute(run_id=run_id2, ledger=ledger)
    copied_mp4 = Path(res2["segments"][0]["visual_path"])
    print(f"  1-byte cache file output file size: {copied_mp4.stat().st_size} bytes (Cached 1 byte copied!)")

    return size1, copied_mp4.stat().st_size


def test_invalid_binary_paths_and_permissions(tmp_dir: Path):
    """Test binary being directory or non-executable file."""
    print("\n--- [7/8] Invalid Binary Paths & Permissions ---")
    db_path = tmp_dir / "ledger_bin.db"
    ledger = StateLedger(db_path=db_path)

    out_dir = tmp_dir / "renders_bin"
    cache_dir = tmp_dir / "cache_bin"

    # Test 1: binary is a directory
    dir_binary = tmp_dir / "binary_is_dir"
    dir_binary.mkdir()

    node_dir = AnimationGeneratorNode(
        manim_binary=str(dir_binary),
        quality="low",
        output_dir=out_dir,
        cache_dir=cache_dir,
    )
    run_id1 = ledger.create_run(slug="bin-is-dir")
    step_id1 = ledger.record_step_start(run_id1, step_name="script_generator")
    ledger.record_step_completion(
        step_id1,
        output_payload={"script": {"visual_cues": [{"cue_id": "c1", "animation_type": "array_highlight"}]}},
    )

    e1 = None
    try:
        node_dir.execute(run_id=run_id1, ledger=ledger)
    except Exception as e:
        e1 = e
        print(f"  Binary is Directory raised: {type(e).__name__}: {e}")

    # Test 2: binary is a non-executable file (permission denied)
    no_exec_binary = tmp_dir / "no_exec_bin"
    no_exec_binary.write_text("#!/bin/bash\necho bad", encoding="utf-8")
    no_exec_binary.chmod(0000)

    node_no_exec = AnimationGeneratorNode(
        manim_binary=str(no_exec_binary),
        quality="low",
        output_dir=out_dir,
        cache_dir=cache_dir,
    )
    run_id2 = ledger.create_run(slug="bin-no-exec")
    step_id2 = ledger.record_step_start(run_id2, step_name="script_generator")
    ledger.record_step_completion(
        step_id2,
        output_payload={"script": {"visual_cues": [{"cue_id": "c2", "animation_type": "array_highlight"}]}},
    )

    e2 = None
    try:
        node_no_exec.execute(run_id=run_id2, ledger=ledger)
    except Exception as e:
        e2 = e
        print(f"  Binary is Non-executable raised: {type(e).__name__}: {e}")

    # Reset chmod so tmp_dir cleanup doesn't fail
    no_exec_binary.chmod(0o755)

    return type(e1).__name__, type(e2).__name__


def test_failure_cleanup_residuals(tmp_dir: Path):
    """Test directory cleanup when non-MP4 files or orphan files are left behind during failure."""
    print("\n--- [8/8] Partial Failure Cleanup Residual Check ---")
    db_path = tmp_dir / "ledger_residuals.db"
    ledger = StateLedger(db_path=db_path)

    out_dir = tmp_dir / "renders_residuals"
    cache_dir = tmp_dir / "cache_residuals"

    script_with_extra_file = tmp_dir / "script_extra.py"
    script_with_extra_file.write_text(
        "import sys, os\n"
        "media_dir = sys.argv[sys.argv.index('--media_dir') + 1]\n"
        "os.makedirs(media_dir, exist_ok=True)\n"
        "# Write a log file\n"
        "with open(os.path.join(media_dir, 'manim_stdout.log'), 'w') as f:\n"
        "    f.write('logging info')\n"
        "sys.stderr.write('Forced failure\\n')\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )

    node = AnimationGeneratorNode(
        manim_binary=str(script_with_extra_file),
        quality="low",
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    run_id = ledger.create_run(slug="residual-run")
    step_id = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(
        step_id,
        output_payload={"script": {"visual_cues": [{"cue_id": "c_fail", "animation_type": "array_highlight"}]}},
    )

    try:
        node.execute(run_id=run_id, ledger=ledger)
    except AnimationError:
        pass

    run_out = out_dir / run_id
    leftover = list(run_out.glob("*")) if run_out.exists() else []
    print(f"Run output directory exists after failure? {run_out.exists()}, leftover files: {leftover}")

    return run_out.exists(), leftover


def main():
    with tempfile.TemporaryDirectory(prefix="m2_stress_") as temp_dir_str:
        tmp_dir = Path(temp_dir_str)
        print(f"Running stress harness in {tmp_dir}")

        test_concurrent_rendering_and_caching(tmp_dir)
        test_high_volume_fd_leak_check(tmp_dir)
        test_path_traversal_in_cue_id(tmp_dir)
        test_unserializable_parameters(tmp_dir)
        test_malformed_script_payloads(tmp_dir)
        test_corrupt_cache_files(tmp_dir)
        test_invalid_binary_paths_and_permissions(tmp_dir)
        test_failure_cleanup_residuals(tmp_dir)


if __name__ == "__main__":
    main()
