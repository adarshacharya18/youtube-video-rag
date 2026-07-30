"""Empirical Adversarial Test Suite for AnimationGeneratorNode and ManimRenderer.

This suite stress-tests edge cases, resource cleanup, leak prevention,
and absence of fake artifact bytes under various failure modes.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.animation.renderer import ManimRenderer
from src.core.exceptions import AnimationError, PipelineStageError
from src.core.models.assets import RenderSegment
from src.core.orchestrator.state_ledger import StateLedger
from src.pipeline.nodes.animation_generator_node import (
    AnimationGeneratorNode,
    ANIMATION_TYPE_MAP,
)

def test_zero_fake_bytes_renderer(tmp_path: Path):
    """Verify ManimRenderer NEVER writes fake/synthetic MP4 bytes on failure or empty output."""
    print("Running Test 1: Zero fake bytes in ManimRenderer...")

    # Mock script 1: exits 0 but creates nothing
    script_empty = tmp_path / "mock_empty.py"
    script_empty.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    renderer = ManimRenderer(manim_binary=str(script_empty))
    out_dir = tmp_path / "renderer_out1"

    try:
        renderer.render(
            scene_script=Path("src/animation/scenes/array_scene.py"),
            class_name="ArrayScene",
            output_dir=out_dir,
            output_filename="test.mp4"
        )
        assert False, "Should have raised AnimationError when no MP4 was produced!"
    except AnimationError as e:
        assert "produced no valid video artifact" in str(e) or "produced no video artifact" in str(e)

    target_file = out_dir / "test.mp4"
    assert not target_file.exists(), f"File {target_file} was created when it shouldn't be!"

    # Mock script 2: exits 0 and creates empty (0-byte) MP4
    script_0byte = tmp_path / "mock_0byte.py"
    script_0byte.write_text(
        "import sys, os\n"
        "media_dir = sys.argv[sys.argv.index('--media_dir') + 1]\n"
        "out_file = sys.argv[sys.argv.index('-o') + 1]\n"
        "os.makedirs(media_dir, exist_ok=True)\n"
        "open(os.path.join(media_dir, out_file), 'wb').close()\n"
        "sys.exit(0)\n",
        encoding="utf-8"
    )

    renderer2 = ManimRenderer(manim_binary=str(script_0byte))
    out_dir2 = tmp_path / "renderer_out2"

    try:
        renderer2.render(
            scene_script=Path("src/animation/scenes/array_scene.py"),
            class_name="ArrayScene",
            output_dir=out_dir2,
            output_filename="test.mp4"
        )
        assert False, "Should have raised AnimationError when 0-byte MP4 was produced!"
    except AnimationError as e:
        assert "produced no valid video artifact" in str(e)

    # Check if target_file is empty or cleaned up
    target_file2 = out_dir2 / "test.mp4"
    if target_file2.exists():
        assert target_file2.stat().st_size == 0, "Target file has non-zero bytes!"

    print("  -> PASSED Test 1")


def test_zero_fake_bytes_animation_node(tmp_path: Path):
    """Verify AnimationGeneratorNode NEVER writes fake MP4 bytes when rendering produces no artifact."""
    print("Running Test 2: Zero fake bytes in AnimationGeneratorNode...")

    db_path = tmp_path / "ledger.db"
    ledger = StateLedger(db_path=db_path)
    run_id = ledger.create_run(slug="fake-bytes-test")

    script_no_out = tmp_path / "mock_no_out.py"
    script_no_out.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    script_payload = {
        "slug": "fake-bytes-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_01",
                    "animation_type": "array_highlight",
                    "timestamp_seconds": 0.0,
                    "parameters": {}
                }
            ]
        }
    }
    step_id = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(step_id, output_payload=script_payload)

    out_dir = tmp_path / "node_out"
    node = AnimationGeneratorNode(
        manim_binary=str(script_no_out),
        output_dir=out_dir,
        cache_dir=tmp_path / "cache"
    )

    try:
        node.execute(run_id=run_id, ledger=ledger)
        assert False, "AnimationGeneratorNode should have raised AnimationError!"
    except AnimationError as e:
        assert "produced no valid video artifact" in str(e)

    run_out_dir = out_dir / run_id
    if run_out_dir.exists():
        assert not list(run_out_dir.glob("*.mp4")), f"Found MP4 files in {run_out_dir}!"

    print("  -> PASSED Test 2")


def test_partial_output_cleanup(tmp_path: Path):
    """Verify partial outputs in run_output_dir are cleaned up on midway multi-cue failure."""
    print("Running Test 3: Partial output cleanup on multi-cue failure...")

    db_path = tmp_path / "ledger_partial.db"
    ledger = StateLedger(db_path=db_path)
    run_id = ledger.create_run(slug="partial-cleanup")

    # Mock script: Cue 1 and 2 succeed, Cue 3 fails
    script_partial = tmp_path / "mock_partial.py"
    script_partial.write_text(
        "import sys, os\n"
        "media_dir = sys.argv[sys.argv.index('--media_dir') + 1]\n"
        "out_file = sys.argv[sys.argv.index('-o') + 1]\n"
        "if 'cue_03' in out_file:\n"
        "    sys.stderr.write('Simulated failure on cue 3\\n')\n"
        "    sys.exit(1)\n"
        "os.makedirs(media_dir, exist_ok=True)\n"
        "with open(os.path.join(media_dir, out_file), 'wb') as f:\n"
        "    f.write(b'REAL_CLIP_DATA_CUE')\n"
        "sys.exit(0)\n",
        encoding="utf-8"
    )

    script_payload = {
        "slug": "partial-cleanup",
        "script": {
            "visual_cues": [
                {"cue_id": "cue_01", "animation_type": "array_highlight", "timestamp_seconds": 0.0, "parameters": {}},
                {"cue_id": "cue_02", "animation_type": "tree_traversal", "timestamp_seconds": 5.0, "parameters": {}},
                {"cue_id": "cue_03", "animation_type": "code_highlight", "timestamp_seconds": 10.0, "parameters": {}},
                {"cue_id": "cue_04", "animation_type": "hashmap_operation", "timestamp_seconds": 15.0, "parameters": {}},
            ]
        }
    }
    step_id = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(step_id, output_payload=script_payload)

    out_dir = tmp_path / "partial_out"
    node = AnimationGeneratorNode(
        manim_binary=str(script_partial),
        output_dir=out_dir,
        cache_dir=tmp_path / "cache"
    )

    try:
        node.execute(run_id=run_id, ledger=ledger)
        assert False, "Should have raised AnimationError on cue_03 failure!"
    except AnimationError:
        pass

    run_out_dir = out_dir / run_id
    if run_out_dir.exists():
        remaining = list(run_out_dir.iterdir())
        assert len(remaining) == 0, f"Expected run_output_dir to be empty, found: {remaining}"

    print("  -> PASSED Test 3")


def test_fd_and_tempdir_leak_under_stress(tmp_path: Path):
    """Verify zero tempdir or file descriptor leaks under 50 repeated executions (success, failure, timeout)."""
    print("Running Test 4: FD & Tempdir leak stress test (50 iterations)...")

    db_path = tmp_path / "ledger_stress.db"
    ledger = StateLedger(db_path=db_path)

    # 1. Success script
    script_ok = tmp_path / "script_ok.py"
    script_ok.write_text(
        "import sys, os\n"
        "media_dir = sys.argv[sys.argv.index('--media_dir') + 1]\n"
        "out_file = sys.argv[sys.argv.index('-o') + 1]\n"
        "os.makedirs(media_dir, exist_ok=True)\n"
        "with open(os.path.join(media_dir, out_file), 'wb') as f:\n"
        "    f.write(b'OK')\n"
        "sys.exit(0)\n",
        encoding="utf-8"
    )

    # 2. Failure script
    script_fail = tmp_path / "script_fail.py"
    script_fail.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")

    # 3. Timeout script
    script_timeout = tmp_path / "script_timeout.py"
    script_timeout.write_text("import time\ntime.sleep(2.0)\n", encoding="utf-8")

    temp_parent = tmp_path / "stress_temps"
    temp_parent.mkdir()

    initial_fd_count = len(os.listdir("/proc/self/fd"))

    for i in range(50):
        run_id = ledger.create_run(slug=f"stress-{i}")
        script_payload = {
            "slug": f"stress-{i}",
            "script": {
                "visual_cues": [
                    {"cue_id": f"c_{i}_1", "animation_type": "array_highlight", "timestamp_seconds": 0.0, "parameters": {"i": i}},
                    {"cue_id": f"c_{i}_2", "animation_type": "linkedlist_operation", "timestamp_seconds": 5.0, "parameters": {"i": i}},
                ]
            }
        }
        step_id = ledger.record_step_start(run_id, step_name="script_generator")
        ledger.record_step_completion(step_id, output_payload=script_payload)

        # Alternate between OK, Fail, Timeout
        mode = i % 3
        if mode == 0:
            node = AnimationGeneratorNode(
                manim_binary=str(script_ok),
                output_dir=tmp_path / "renders",
                cache_dir=tmp_path / "cache",
                temp_dir=temp_parent
            )
            node.execute(run_id=run_id, ledger=ledger)
        elif mode == 1:
            node = AnimationGeneratorNode(
                manim_binary=str(script_fail),
                output_dir=tmp_path / "renders",
                cache_dir=tmp_path / "cache",
                temp_dir=temp_parent
            )
            try:
                node.execute(run_id=run_id, ledger=ledger)
            except AnimationError:
                pass
        else:
            node = AnimationGeneratorNode(
                manim_binary=str(script_timeout),
                output_dir=tmp_path / "renders",
                cache_dir=tmp_path / "cache",
                timeout=0.1,
                temp_dir=temp_parent
            )
            try:
                node.execute(run_id=run_id, ledger=ledger)
            except AnimationError:
                pass

    final_fd_count = len(os.listdir("/proc/self/fd"))
    remaining_temps = list(temp_parent.iterdir())

    assert len(remaining_temps) == 0, f"Leaked temporary directories: {remaining_temps}"
    assert abs(final_fd_count - initial_fd_count) <= 2, (
        f"File descriptor leak detected! Initial FD count: {initial_fd_count}, Final FD count: {final_fd_count}"
    )

    print(f"  -> PASSED Test 4 (Initial FDs: {initial_fd_count}, Final FDs: {final_fd_count}, Remaining Tempdirs: 0)")


def test_section_dict_fallback_extraction():
    """Verify Section Dict Fallback Visual Cue Extraction."""
    print("Running Test 5: Section Dict Fallback Extraction...")

    node = AnimationGeneratorNode()
    payload = {
        "slug": "malformed-payload",
        "script": {
            "topic": "Malformed",
            "total_duration": "INVALID",
            "hook": {
                "visual_cues": [{"cue_id": "h1", "animation_type": "array_highlight", "timestamp_seconds": 0.0, "parameters": {}}]
            },
            "context": {
                "visual_cues": [{"cue_id": "c1", "animation_type": "tree_traversal", "timestamp_seconds": 5.0, "parameters": {}}]
            },
            "solution": {
                "visual_cues": [{"cue_id": "s1", "animation_type": "code_highlight", "timestamp_seconds": 10.0, "parameters": {}}]
            },
            "complexity": {
                "visual_cues": [{"cue_id": "x1", "animation_type": "complexity_chart", "timestamp_seconds": 15.0, "parameters": {}}]
            }
        }
    }

    cues = node._extract_visual_cues(payload)
    assert len(cues) == 4
    ids = [c["cue_id"] for c in cues]
    assert ids == ["h1", "c1", "s1", "x1"]
    print("  -> PASSED Test 5")


def main():
    print("Starting Empirical Adversarial Test Suite for Gate Evaluation Iteration 2...\n")
    temp_dir_obj = tempfile.TemporaryDirectory()
    tmp_path = Path(temp_dir_obj.name)

    try:
        test_zero_fake_bytes_renderer(tmp_path)
        test_zero_fake_bytes_animation_node(tmp_path)
        test_partial_output_cleanup(tmp_path)
        test_fd_and_tempdir_leak_under_stress(tmp_path)
        test_section_dict_fallback_extraction()
        print("\nALL ADVERSARIAL EMPIRICAL TESTS PASSED SUCCESSFULLY! (5/5)")
    finally:
        temp_dir_obj.cleanup()


if __name__ == "__main__":
    main()
