"""Adversarial stress and edge-case test suite for AnimationGeneratorNode."""

import os
import sys
import time
import shutil
import tempfile
import traceback
from pathlib import Path
import pytest

# Ensure repository root is in python path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.core.exceptions import AnimationError, PipelineStageError
from src.core.orchestrator.state_ledger import StateLedger
from src.pipeline.nodes.animation_generator_node import AnimationGeneratorNode


def get_open_fd_count():
    """Get open file descriptor count for current process."""
    if hasattr(os, "listdir"):
        try:
            return len(os.listdir("/proc/self/fd"))
        except (FileNotFoundError, PermissionError):
            pass
    return 0


def create_ledger(tmp_path):
    db_path = tmp_path / "test_ledger.db"
    return StateLedger(db_path=db_path)


def test_empty_visual_cues(tmp_path):
    """Test 1: Empty visual cues list."""
    ledger = create_ledger(tmp_path)
    run_id = ledger.create_run(slug="empty-cues")

    script_payload = {
        "slug": "empty-cues",
        "script": {
            "topic": "Empty",
            "slug": "empty-cues",
            "visual_cues": [],
        },
    }
    step_id = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(step_id, output_payload=script_payload)

    node = AnimationGeneratorNode(
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )
    result = node.execute(run_id=run_id, ledger=ledger)

    assert result["status"] == "completed"
    assert result["render_count"] == 0
    assert result["segments"] == []
    print("PASS: test_empty_visual_cues")


def test_missing_script_generator_step(tmp_path):
    """Test 2: Missing script_generator prior ledger step."""
    ledger = create_ledger(tmp_path)
    run_id = ledger.create_run(slug="no-script")

    node = AnimationGeneratorNode(
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    with pytest.raises(PipelineStageError) as excinfo:
        node.execute(run_id=run_id, ledger=ledger)
    assert "script_generator" in str(excinfo.value)
    print("PASS: test_missing_script_generator_step")


def test_malformed_visual_cues_string_duration(tmp_path):
    """Test 3a: Visual cue with non-numeric duration string."""
    ledger = create_ledger(tmp_path)
    run_id = ledger.create_run(slug="malformed-duration")

    script_payload = {
        "slug": "malformed-duration",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_bad_dur",
                    "animation_type": "array_highlight",
                    "timestamp_seconds": 0.0,
                    "parameters": {"duration": "invalid_duration_str"},
                }
            ]
        },
    }
    step_id = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(step_id, output_payload=script_payload)

    mock_script = tmp_path / "mock_manim.py"
    mock_script.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    node = AnimationGeneratorNode(
        manim_binary=str(mock_script),
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    try:
        node.execute(run_id=run_id, ledger=ledger)
        print("UNEXPECTED SUCCESS: malformed duration string did not raise error")
    except Exception as e:
        print(f"RAISED ({type(e).__name__}): {e}")


def test_malformed_visual_cues_string_timestamp(tmp_path):
    """Test 3b: Visual cue with non-numeric timestamp string."""
    ledger = create_ledger(tmp_path)
    run_id = ledger.create_run(slug="malformed-ts")

    script_payload = {
        "slug": "malformed-ts",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_bad_ts",
                    "animation_type": "array_highlight",
                    "timestamp_seconds": "not_a_number",
                    "parameters": {"duration": 5.0},
                }
            ]
        },
    }
    step_id = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(step_id, output_payload=script_payload)

    mock_script = tmp_path / "mock_manim.py"
    mock_script.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    node = AnimationGeneratorNode(
        manim_binary=str(mock_script),
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    try:
        node.execute(run_id=run_id, ledger=ledger)
        print("UNEXPECTED SUCCESS: malformed timestamp did not raise error")
    except Exception as e:
        print(f"RAISED ({type(e).__name__}): {e}")


def test_malformed_visual_cues_non_dict_parameters(tmp_path):
    """Test 3c: Visual cue with parameters as a string instead of a dict."""
    ledger = create_ledger(tmp_path)
    run_id = ledger.create_run(slug="malformed-params")

    script_payload = {
        "slug": "malformed-params",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_bad_params",
                    "animation_type": "array_highlight",
                    "timestamp_seconds": 0.0,
                    "parameters": "this_is_a_string_not_a_dict",
                }
            ]
        },
    }
    step_id = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(step_id, output_payload=script_payload)

    mock_script = tmp_path / "mock_manim.py"
    mock_script.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    node = AnimationGeneratorNode(
        manim_binary=str(mock_script),
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    try:
        node.execute(run_id=run_id, ledger=ledger)
        print("UNEXPECTED SUCCESS: non-dict parameters did not raise error")
    except Exception as e:
        print(f"RAISED ({type(e).__name__}): {e}")


def test_timeout_and_tempdir_cleanup(tmp_path):
    """Test 4: Process timeout and tempdir cleanup."""
    ledger = create_ledger(tmp_path)
    run_id = ledger.create_run(slug="timeout-test")

    sleep_script = tmp_path / "sleep_manim.py"
    sleep_script.write_text(
        "import sys, time\ntime.sleep(5)\nsys.exit(0)\n",
        encoding="utf-8",
    )

    script_payload = {
        "slug": "timeout-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_timeout",
                    "animation_type": "tree_traversal",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(step_id, output_payload=script_payload)

    temp_parent = tmp_path / "custom_temp_dir"
    temp_parent.mkdir()

    initial_fd = get_open_fd_count()

    node = AnimationGeneratorNode(
        manim_binary=str(sleep_script),
        timeout=0.2,  # 200ms timeout
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
        temp_dir=temp_parent,
    )

    timeout_raised = False
    try:
        node.execute(run_id=run_id, ledger=ledger)
    except AnimationError as e:
        if "timed out" in str(e):
            timeout_raised = True

    assert timeout_raised, "Expected AnimationError due to timeout"

    remaining_subdirs = [d for d in temp_parent.iterdir() if d.is_dir()]
    assert len(remaining_subdirs) == 0, f"Temp directories leaked: {remaining_subdirs}"

    final_fd = get_open_fd_count()
    if initial_fd > 0:
        assert final_fd <= initial_fd + 2, f"FD leak detected: initial={initial_fd}, final={final_fd}"

    print("PASS: test_timeout_and_tempdir_cleanup")


def test_non_zero_exit_code_and_cleanup(tmp_path):
    """Test 5: Non-zero exit code and tempdir cleanup."""
    ledger = create_ledger(tmp_path)
    run_id = ledger.create_run(slug="exit-code-test")

    fail_script = tmp_path / "fail_manim.py"
    fail_script.write_text(
        "import sys\nsys.stderr.write('CRITICAL MANIM ERROR\\n')\nsys.exit(137)\n",
        encoding="utf-8",
    )

    script_payload = {
        "slug": "exit-code-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_fail",
                    "animation_type": "code_highlight",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(step_id, output_payload=script_payload)

    temp_parent = tmp_path / "custom_temp_dir"
    temp_parent.mkdir()

    initial_fd = get_open_fd_count()

    node = AnimationGeneratorNode(
        manim_binary=str(fail_script),
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
        temp_dir=temp_parent,
    )

    error_raised = False
    try:
        node.execute(run_id=run_id, ledger=ledger)
    except AnimationError as e:
        if "exit code 137" in str(e) and "CRITICAL MANIM ERROR" in str(e):
            error_raised = True

    assert error_raised, "Expected AnimationError with stderr and exit code 137"

    remaining_subdirs = [d for d in temp_parent.iterdir() if d.is_dir()]
    assert len(remaining_subdirs) == 0, f"Temp directories leaked: {remaining_subdirs}"

    final_fd = get_open_fd_count()
    if initial_fd > 0:
        assert final_fd <= initial_fd + 2, f"FD leak detected: initial={initial_fd}, final={final_fd}"

    print("PASS: test_non_zero_exit_code_and_cleanup")


def test_stress_repeated_failures_fd_and_temp_leak(tmp_path):
    """Test 6: Repeated stress failures (50 iterations) checking FD and temp leaks."""
    ledger = create_ledger(tmp_path)

    fail_script = tmp_path / "fail_manim.py"
    fail_script.write_text("import sys\nsys.exit(42)\n", encoding="utf-8")

    temp_parent = tmp_path / "stress_temp_dir"
    temp_parent.mkdir()

    initial_fd = get_open_fd_count()

    node = AnimationGeneratorNode(
        manim_binary=str(fail_script),
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
        temp_dir=temp_parent,
    )

    failures = 0
    for i in range(50):
        run_id = ledger.create_run(slug=f"stress-{i}")
        script_payload = {
            "slug": f"stress-{i}",
            "script": {
                "visual_cues": [
                    {
                        "cue_id": f"cue_stress_{i}",
                        "animation_type": "array_highlight",
                        "timestamp_seconds": 0.0,
                        "parameters": {"i": i},
                    }
                ]
            },
        }
        step_id = ledger.record_step_start(run_id, step_name="script_generator")
        ledger.record_step_completion(step_id, output_payload=script_payload)

        try:
            node.execute(run_id=run_id, ledger=ledger)
        except AnimationError:
            failures += 1

    assert failures == 50, f"Expected 50 failures, got {failures}"

    remaining_subdirs = [d for d in temp_parent.iterdir() if d.is_dir()]
    assert len(remaining_subdirs) == 0, f"Leaked temp directories after 50 failures: {len(remaining_subdirs)}"

    final_fd = get_open_fd_count()
    if initial_fd > 0:
        assert final_fd <= initial_fd + 5, f"FD leak over 50 runs: initial={initial_fd}, final={final_fd}"

    print("PASS: test_stress_repeated_failures_fd_and_temp_leak (50 iterations)")
