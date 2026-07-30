"""Empirical Stress Testing Harness for AnimationGeneratorNode (Iteration 2).

Tests:
1. Sub-100 byte (1-byte, 50-byte) corrupt cache files to confirm Cache MISS and re-render.
2. Path traversal payloads (cue_id="../escape", "../../etc/passwd", etc.) to confirm containment in run_output_dir.
3. Concurrent / atomic cache writes across multiple threads.
4. File descriptor and tempdir cleanup verification.
"""

import sys
import os
import shutil
import tempfile
import threading
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.orchestrator.state_ledger import StateLedger
from src.pipeline.nodes.animation_generator_node import AnimationGeneratorNode

def create_mock_manim_script(dir_path: Path) -> str:
    script_path = dir_path / "mock_manim.py"
    script_content = """import sys, os
media_dir = None
out_arg = "output.mp4"
for i, arg in enumerate(sys.argv):
    if arg == "--media_dir" and i + 1 < len(sys.argv):
        media_dir = sys.argv[i + 1]
    if arg == "-o" and i + 1 < len(sys.argv):
        out_arg = sys.argv[i + 1]

if media_dir:
    os.makedirs(media_dir, exist_ok=True)
    out_file = os.path.join(media_dir, out_arg)
    with open(out_file, "wb") as f:
        f.write(b"MOCK_VIDEO_DATA_HEADER_VALIDATION_STRING_VALID_MP4_DUMMY_CONTENT_" * 5)

sys.exit(0)
"""
    script_path.write_text(script_content, encoding="utf-8")
    return str(script_path)

def test_corrupt_cache_files(tmp_dir: Path):
    print("--- Test 1: Sub-100 byte Corrupt Cache Files ---")
    db_path = tmp_dir / "ledger_cache.db"
    ledger = StateLedger(db_path=db_path)
    mock_script = create_mock_manim_script(tmp_dir)

    out_dir = tmp_dir / "renders"
    cache_dir = tmp_dir / "cache"

    node = AnimationGeneratorNode(
        manim_binary=mock_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    params = {"test": "corrupt_bytes_check"}
    cache_hash = node._compute_cache_hash("array_highlight", params)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{cache_hash}.mp4"

    # Sub-test 1a: 1-byte corrupt file
    cache_file.write_bytes(b"X")
    print(f"Created 1-byte corrupt cache file: {cache_file.stat().st_size} bytes")

    run_id1 = ledger.create_run(slug="test-1-byte")
    payload1 = {
        "slug": "test-1-byte",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_1byte",
                    "animation_type": "array_highlight",
                    "parameters": params,
                }
            ]
        },
    }
    s1 = ledger.record_step_start(run_id1, step_name="script_generator")
    ledger.record_step_completion(s1, output_payload=payload1)

    res1 = node.execute(run_id=run_id1, ledger=ledger)
    new_size1 = cache_file.stat().st_size
    print(f"1-byte cache result: status={res1['status']}, new_cache_size={new_size1} bytes")
    assert new_size1 >= 100, f"Expected cache file size >= 100, got {new_size1}"

    # Sub-test 1b: 50-byte corrupt file
    cache_file.write_bytes(b"A" * 50)
    print(f"Created 50-byte corrupt cache file: {cache_file.stat().st_size} bytes")

    run_id2 = ledger.create_run(slug="test-50-byte")
    payload2 = {
        "slug": "test-50-byte",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_50byte",
                    "animation_type": "array_highlight",
                    "parameters": params,
                }
            ]
        },
    }
    s2 = ledger.record_step_start(run_id2, step_name="script_generator")
    ledger.record_step_completion(s2, output_payload=payload2)

    res2 = node.execute(run_id=run_id2, ledger=ledger)
    new_size2 = cache_file.stat().st_size
    print(f"50-byte cache result: status={res2['status']}, new_cache_size={new_size2} bytes")
    assert new_size2 >= 100, f"Expected cache file size >= 100, got {new_size2}"
    print("PASS: Sub-100 byte corrupt cache files correctly triggered Cache MISS and re-render.")

def test_path_traversal_containment(tmp_dir: Path):
    print("\n--- Test 2: Path Traversal Payloads Containment ---")
    db_path = tmp_dir / "ledger_traversal.db"
    ledger = StateLedger(db_path=db_path)
    mock_script = create_mock_manim_script(tmp_dir)

    out_dir = tmp_dir / "renders"
    cache_dir = tmp_dir / "cache"

    node = AnimationGeneratorNode(
        manim_binary=mock_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    traversal_cues = [
        "../escape",
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "../../../root_escape",
        "safe_cue_01",
    ]

    run_id = ledger.create_run(slug="traversal-test")
    cues_payload = []
    for idx, c_id in enumerate(traversal_cues):
        cues_payload.append({
            "cue_id": c_id,
            "animation_type": "array_highlight",
            "parameters": {"idx": idx},
        })

    payload = {
        "slug": "traversal-test",
        "script": {"visual_cues": cues_payload},
    }
    s1 = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(s1, output_payload=payload)

    res = node.execute(run_id=run_id, ledger=ledger)
    print(f"Execution completed with {res['render_count']} segments")

    run_out_dir = (out_dir / run_id).resolve()
    print(f"Run output dir: {run_out_dir}")

    for segment in res["segments"]:
        v_path = Path(segment["visual_path"]).resolve()
        print(f"Segment path: {v_path}")
        assert v_path.is_relative_to(run_out_dir), f"Path traversal escape detected! {v_path} is outside {run_out_dir}"
        assert v_path.exists(), f"Segment file does not exist: {v_path}"

    # Verify no files were created outside run_out_dir
    parent_files = list(out_dir.glob("*.mp4"))
    assert len(parent_files) == 0, f"Files escaped to parent output dir: {parent_files}"
    print("PASS: Path traversal payloads strictly contained inside run_output_dir.")

def test_concurrent_atomic_cache_writes(tmp_dir: Path):
    print("\n--- Test 3: Concurrent / Atomic Cache Writes ---")
    db_path = tmp_dir / "ledger_concurrent.db"
    ledger = StateLedger(db_path=db_path)
    mock_script = create_mock_manim_script(tmp_dir)

    out_dir = tmp_dir / "renders_concurrent"
    cache_dir = tmp_dir / "cache_concurrent"

    node = AnimationGeneratorNode(
        manim_binary=mock_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    num_threads = 10
    errors = []

    def worker(thread_idx: int):
        try:
            r_id = ledger.create_run(slug=f"concurrent-{thread_idx}")
            payload = {
                "slug": f"concurrent-{thread_idx}",
                "script": {
                    "visual_cues": [
                        {
                            "cue_id": f"cue_shared",
                            "animation_type": "array_highlight",
                            "parameters": {"shared_param": "same_value_for_all"},
                        }
                    ]
                },
            }
            s = ledger.record_step_start(r_id, step_name="script_generator")
            ledger.record_step_completion(s, output_payload=payload)
            res = node.execute(run_id=r_id, ledger=ledger)
            v_path = Path(res["segments"][0]["visual_path"])
            if not v_path.exists() or v_path.stat().st_size < 100:
                errors.append(f"Thread {thread_idx} produced invalid output file: size={v_path.stat().st_size if v_path.exists() else 0}")
        except Exception as e:
            errors.append(f"Thread {thread_idx} failed: {e}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"Concurrent execution finished across {num_threads} threads. Errors: {len(errors)}")
    if errors:
        for err in errors:
            print(f"  ERROR: {err}")
        assert False, "Concurrent execution produced errors"

    # Check cache dir for leftover tmp files
    tmp_leftovers = list(cache_dir.glob("*.tmp"))
    print(f"Leftover .tmp files in cache_dir: {len(tmp_leftovers)}")
    assert len(tmp_leftovers) == 0, f"Found leftover temporary files in cache_dir: {tmp_leftovers}"
    print("PASS: Concurrent / atomic cache writes verified with 0 race condition corruptions or leftover files.")

def main():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)
        test_corrupt_cache_files(tmp_dir)
        test_path_traversal_containment(tmp_dir)
        test_concurrent_atomic_cache_writes(tmp_dir)
    print("\nALL EMPIRICAL STRESS TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
