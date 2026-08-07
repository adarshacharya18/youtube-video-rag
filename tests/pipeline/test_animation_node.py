"""Tests for AnimationGeneratorNode and Manim subprocess execution."""

import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from src.core.exceptions import AnimationError, PipelineStageError
from src.core.models.assets import AssetReference, RenderSegment
from src.core.orchestrator.state_ledger import StateLedger
from src.pipeline.nodes.animation_generator_node import (
    AnimationGeneratorNode,
    ANIMATION_TYPE_MAP,
    DEFAULT_SCENE,
)


@pytest.fixture
def temp_ledger(tmp_path):
    """Fixture to provide a clean SQLite StateLedger."""
    db_path = tmp_path / "test_ledger.db"
    ledger = StateLedger(db_path=db_path)
    return ledger


@pytest.fixture
def mock_manim_script(tmp_path):
    """Fixture providing a mock python script simulating manim CLI binary."""
    script_path = tmp_path / "mock_manim.py"
    script_content = """import sys
import os

# Create mock video file inside media_dir if provided
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

if media_dir:
    os.makedirs(media_dir, exist_ok=True)
    out_file = os.path.join(media_dir, out_arg)
    with open(out_file, "wb") as f:
        f.write(b"MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5)

sys.exit(0)
"""
    script_path.write_text(script_content, encoding="utf-8")
    return str(script_path)


def test_node_name_and_init(tmp_path):
    """Verify node property name returns 'animation_generator'."""
    node = AnimationGeneratorNode(
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
        quality="low",
    )
    assert node.name == "animation_generator"
    assert node.quality_flag == "-ql"


def test_execute_without_ledger_raises_error():
    """Verify executing without StateLedger raises PipelineStageError."""
    node = AnimationGeneratorNode()
    with pytest.raises(PipelineStageError):
        node.execute(run_id="run_123", ledger=None)


def test_execute_without_script_step_output_raises_error(temp_ledger):
    """Verify missing script_generator prior step raises PipelineStageError."""
    run_id = temp_ledger.create_run(slug="two-sum")

    node = AnimationGeneratorNode()
    with pytest.raises(PipelineStageError):
        node.execute(run_id=run_id, ledger=temp_ledger)


def test_execute_successful_render(temp_ledger, mock_manim_script, tmp_path):
    """Verify successful visual cue extraction, rendering, caching, and payload structure."""
    run_id = temp_ledger.create_run(slug="two-sum")

    # Record completed script_generator step
    script_payload = {
        "slug": "two-sum",
        "script": {
            "topic": "Two Sum",
            "slug": "two-sum",
            "difficulty": "Easy",
            "total_duration": 30.0,
            "hook": {
                "title": "Hook",
                "narration": "Welcome to Two Sum",
                "estimated_duration": 5.0,
                "visual_cues": [
                    {
                        "cue_id": "cue_01",
                        "animation_type": "array_highlight",
                        "description": "Highlight array elements",
                        "timestamp_seconds": 0.0,
                        "parameters": {"array": [2, 7, 11, 15], "duration": 5.0},
                    }
                ],
            },
            "context": {
                "title": "Context",
                "narration": "Problem description",
                "estimated_duration": 5.0,
                "visual_cues": [],
            },
            "solution": {
                "title": "Solution",
                "narration": "Hashmap solution",
                "estimated_duration": 15.0,
                "visual_cues": [
                    {
                        "cue_id": "cue_02",
                        "animation_type": "hashmap_insert",
                        "description": "Insert key value pairs into hashmap",
                        "timestamp_seconds": 10.0,
                        "parameters": {"entries": {"2": 0}, "duration": 15.0},
                    }
                ],
            },
            "complexity": {
                "title": "Complexity",
                "narration": "Time O(N), Space O(N)",
                "estimated_duration": 5.0,
                "visual_cues": [],
            },
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    out_dir = tmp_path / "renders"
    cache_dir = tmp_path / "cache"

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        quality="low",
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    result = node.execute(run_id=run_id, ledger=temp_ledger)

    assert result["status"] == "completed"
    assert result["slug"] == "two-sum"
    assert result["render_count"] == 2
    assert len(result["segments"]) == 2

    # Validate first RenderSegment
    seg1_dict = result["segments"][0]
    seg1 = RenderSegment.model_validate(seg1_dict)
    assert seg1.segment_id == "seg_cue_01"
    assert seg1.segment_type == "visual_anim"
    assert seg1.duration == 5.0
    assert seg1.visual_path is not None
    assert Path(seg1.visual_path).exists()

    # Test Caching: execute a second time for identical run_id/cues
    run_id_2 = temp_ledger.create_run(slug="two-sum")
    step_id_2 = temp_ledger.record_step_start(run_id_2, step_name="script_generator")
    temp_ledger.record_step_completion(step_id_2, output_payload=script_payload)

    # Use a invalid binary path to prove subprocess is NOT called on cache hit
    cached_node = AnimationGeneratorNode(
        manim_binary="/nonexistent/binary/path",
        quality="low",
        output_dir=out_dir,
        cache_dir=cache_dir,
    )
    cached_result = cached_node.execute(run_id=run_id_2, ledger=temp_ledger)
    assert cached_result["render_count"] == 2


def test_subprocess_failure_raises_animation_error(temp_ledger, tmp_path):
    """Verify non-zero subprocess exit code raises AnimationError."""
    run_id = temp_ledger.create_run(slug="two-sum")

    fail_script = tmp_path / "fail_manim.py"
    fail_script.write_text("import sys\nsys.stderr.write('Manim Error')\nsys.exit(1)\n", encoding="utf-8")

    script_payload = {
        "slug": "two-sum",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_fail",
                    "animation_type": "array_highlight",
                    "description": "Failing cue",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    node = AnimationGeneratorNode(
        manim_binary=str(fail_script),
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    with pytest.raises(AnimationError) as exc_info:
        node.execute(run_id=run_id, ledger=temp_ledger)

    assert "Manim render failed" in str(exc_info.value)


def test_temp_directory_cleaned_up(temp_ledger, mock_manim_script, tmp_path):
    """Verify temporary directory is completely removed after execution."""
    run_id = temp_ledger.create_run(slug="two-sum")

    script_payload = {
        "slug": "two-sum",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_cleanup",
                    "animation_type": "tree_traversal",
                    "description": "Tree traversal",
                    "timestamp_seconds": 0.0,
                    "parameters": {"root": 1},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    explicit_temp_parent = tmp_path / "custom_temp"
    explicit_temp_parent.mkdir()

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
        temp_dir=explicit_temp_parent,
    )

    node.execute(run_id=run_id, ledger=temp_ledger)

    # Check that explicit_temp_parent is completely empty (no leftover files or dirs)
    assert list(explicit_temp_parent.iterdir()) == [], "Temporary parent directory must be completely empty"


def test_render_produces_no_mp4_raises_animation_error(temp_ledger, tmp_path):
    """Verify AnimationError is raised (and no fake MP4 bytes written) when subprocess exits 0 but produces no MP4 file."""
    run_id = temp_ledger.create_run(slug="no-mp4-test")

    no_output_script = tmp_path / "no_output_manim.py"
    no_output_script.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    script_payload = {
        "slug": "no-mp4-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_no_output",
                    "animation_type": "array_highlight",
                    "description": "No output cue",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    out_dir = tmp_path / "renders"
    node = AnimationGeneratorNode(
        manim_binary=str(no_output_script),
        output_dir=out_dir,
        cache_dir=tmp_path / "cache",
    )

    with pytest.raises(AnimationError) as exc_info:
        node.execute(run_id=run_id, ledger=temp_ledger)

    assert "produced no valid video artifact" in str(exc_info.value) or "produced no video artifact" in str(exc_info.value)

    target_mp4 = out_dir / run_id / "segment_cue_no_output.mp4"
    assert not target_mp4.exists()


def test_linkedlist_operation_mapping_and_execution(temp_ledger, mock_manim_script, tmp_path):
    """Verify 'linkedlist_operation' maps to LinkedListScene and executes correctly."""
    mapped = ANIMATION_TYPE_MAP.get("linkedlist_operation")
    assert mapped is not None, "'linkedlist_operation' missing from ANIMATION_TYPE_MAP"
    assert mapped[0] == "src/animation/scenes/linkedlist_scene.py"
    assert mapped[1] == "LinkedListScene"

    run_id = temp_ledger.create_run(slug="linkedlist-test")
    script_payload = {
        "slug": "linkedlist-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_ll_op",
                    "animation_type": "linkedlist_operation",
                    "description": "LinkedList operation",
                    "timestamp_seconds": 0.0,
                    "parameters": {"nodes": [1, 2, 3]},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"
    assert result["segments"][0]["scene_type"] == "LINKEDLIST_OPERATION"


def test_extract_visual_cues_fallback_from_section_dicts(temp_ledger, mock_manim_script, tmp_path):
    """Verify _extract_visual_cues retrieves visual cues from section dicts (hook, context, solution, complexity) when main model validation fails."""
    run_id = temp_ledger.create_run(slug="fallback-cues-test")

    invalid_script_payload = {
        "slug": "fallback-cues-test",
        "script": {
            "topic": "Binary Search",
            "slug": "binary-search",
            "total_duration": "INVALID_TYPE",
            "hook": {
                "title": "Hook",
                "narration": "Hook narration",
                "estimated_duration": 5.0,
                "visual_cues": [
                    {
                        "cue_id": "cue_hook",
                        "animation_type": "array_highlight",
                        "description": "Hook cue",
                        "timestamp_seconds": 0.0,
                        "parameters": {"array": [1, 2]},
                    }
                ],
            },
            "context": {
                "title": "Context",
                "narration": "Context narration",
                "estimated_duration": 5.0,
                "visual_cues": [
                    {
                        "cue_id": "cue_ctx",
                        "animation_type": "tree_traversal",
                        "description": "Context cue",
                        "timestamp_seconds": 5.0,
                        "parameters": {"root": 1},
                    }
                ],
            },
            "solution": {
                "title": "Solution",
                "narration": "Solution narration",
                "estimated_duration": 10.0,
                "visual_cues": [
                    {
                        "cue_id": "cue_sol",
                        "animation_type": "code_highlight",
                        "description": "Solution cue",
                        "timestamp_seconds": 10.0,
                        "parameters": {"code": "x = 1"},
                    }
                ],
            },
            "complexity": {
                "title": "Complexity",
                "narration": "Complexity narration",
                "estimated_duration": 5.0,
                "visual_cues": [
                    {
                        "cue_id": "cue_comp",
                        "animation_type": "complexity_chart",
                        "description": "Complexity cue",
                        "timestamp_seconds": 20.0,
                        "parameters": {},
                    }
                ],
            },
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=invalid_script_payload)

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    cues = node._extract_visual_cues(invalid_script_payload)
    assert len(cues) == 4
    cue_ids = [c["cue_id"] for c in cues]
    assert cue_ids == ["cue_hook", "cue_ctx", "cue_sol", "cue_comp"]

    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["render_count"] == 4
    assert len(result["segments"]) == 4


def test_base_dsa_scene_loads_parameters_from_json(tmp_path, monkeypatch):
    """Verify BaseDSAScene loads parameters from parameters.json."""
    from src.animation.scenes.linkedlist_scene import LinkedListScene

    params_data = {"nodes": [10, 20, 30, 40], "title": "Test LinkedList"}
    params_file = tmp_path / "parameters.json"
    params_file.write_text(json.dumps(params_data), encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    scene = LinkedListScene()
    loaded = scene.load_params_from_json("parameters.json")
    assert loaded == params_data
    assert scene.params == params_data


def test_animation_node_writes_parameters_json_to_temp_dir(temp_ledger, tmp_path):
    """Verify AnimationGeneratorNode writes parameters.json with exact visual parameters to working directory."""
    run_id = temp_ledger.create_run(slug="params-written-test")

    param_checker_script = tmp_path / "param_checker.py"
    param_checker_script.write_text(
        "import sys, os, json\n"
        "media_dir = sys.argv[sys.argv.index('--media_dir') + 1]\n"
        "out_arg = sys.argv[sys.argv.index('-o') + 1]\n"
        "params_path = os.path.join(media_dir, 'parameters.json')\n"
        "assert os.path.exists(params_path), 'parameters.json not written!'\n"
        "with open(params_path, 'r') as f:\n"
        "    data = json.load(f)\n"
        "assert data.get('test_key') == 'test_val'\n"
        "with open(os.path.join(media_dir, out_arg), 'wb') as f:\n"
        "    f.write(b'MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_' * 5)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )

    script_payload = {
        "slug": "params-written-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_param_check",
                    "animation_type": "array_highlight",
                    "description": "Param check",
                    "timestamp_seconds": 0.0,
                    "parameters": {"test_key": "test_val", "duration": 5.0},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    node = AnimationGeneratorNode(
        manim_binary=str(param_checker_script),
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"


def test_tempdir_cleanup_on_subprocess_failure(temp_ledger, tmp_path):
    """Verify tempdir cleanup when Manim subprocess exits non-zero."""
    run_id = temp_ledger.create_run(slug="fail-tempdir-test")
    fail_script = tmp_path / "fail_manim.py"
    fail_script.write_text("import sys\nsys.stderr.write('Render error')\nsys.exit(1)\n", encoding="utf-8")

    script_payload = {
        "slug": "fail-tempdir-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_fail",
                    "animation_type": "array_highlight",
                    "description": "Fail cue",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    explicit_temp_parent = tmp_path / "custom_temp"
    explicit_temp_parent.mkdir()

    node = AnimationGeneratorNode(
        manim_binary=str(fail_script),
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
        temp_dir=explicit_temp_parent,
    )

    with pytest.raises(AnimationError):
        node.execute(run_id=run_id, ledger=temp_ledger)

    assert list(explicit_temp_parent.iterdir()) == [], "Temporary parent directory must be completely empty"


def test_tempdir_cleanup_on_timeout(temp_ledger, tmp_path):
    """Verify tempdir cleanup when Manim subprocess times out."""
    run_id = temp_ledger.create_run(slug="timeout-tempdir-test")
    sleep_script = tmp_path / "sleep_manim.py"
    sleep_script.write_text("import time\ntime.sleep(5.0)\n", encoding="utf-8")

    script_payload = {
        "slug": "timeout-tempdir-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_timeout",
                    "animation_type": "array_highlight",
                    "description": "Timeout cue",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    explicit_temp_parent = tmp_path / "custom_temp"
    explicit_temp_parent.mkdir()

    node = AnimationGeneratorNode(
        manim_binary=str(sleep_script),
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
        timeout=0.2,
        temp_dir=explicit_temp_parent,
    )

    with pytest.raises(AnimationError) as exc_info:
        node.execute(run_id=run_id, ledger=temp_ledger)

    assert "timed out" in str(exc_info.value)
    assert list(explicit_temp_parent.iterdir()) == [], "Temporary parent directory must be completely empty"


def test_partial_output_cleanup_on_midway_failure(temp_ledger, tmp_path):
    """Verify partial output files in run_output_dir are cleaned up if a multi-cue run fails mid-execution, while cache remains intact."""
    run_id = temp_ledger.create_run(slug="partial-cleanup-test")

    cond_script = tmp_path / "cond_manim.py"
    cond_script.write_text(
        "import sys, os\n"
        "media_dir = sys.argv[sys.argv.index('--media_dir') + 1]\n"
        "out_file = sys.argv[sys.argv.index('-o') + 1]\n"
        "if 'cue_fail' in out_file:\n"
        "    sys.stderr.write('Cue 2 failed\\n')\n"
        "    sys.exit(1)\n"
        "os.makedirs(media_dir, exist_ok=True)\n"
        "with open(os.path.join(media_dir, out_file), 'wb') as f:\n"
        "    f.write(b'MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_' * 5)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )

    script_payload = {
        "slug": "partial-cleanup-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_ok",
                    "animation_type": "array_highlight",
                    "description": "First cue ok",
                    "timestamp_seconds": 0.0,
                    "parameters": {"key": "val1"},
                },
                {
                    "cue_id": "cue_fail",
                    "animation_type": "tree_traversal",
                    "description": "Second cue fail",
                    "timestamp_seconds": 5.0,
                    "parameters": {"key": "val2"},
                },
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    out_dir = tmp_path / "renders"
    cache_dir = tmp_path / "cache"
    node = AnimationGeneratorNode(
        manim_binary=str(cond_script),
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    with pytest.raises(AnimationError):
        node.execute(run_id=run_id, ledger=temp_ledger)

    run_out_path = out_dir / run_id
    assert not run_out_path.exists(), "Run output directory should be deleted when empty after partial failure"

    # Verify rendered clip for succeeded cue_ok remains intact in cache_dir
    cache_files = list(cache_dir.glob("*.mp4"))
    assert len(cache_files) == 1, "Cache directory should retain rendered clip from successful cue 1"


def test_subprocess_close_fds_verified(temp_ledger, mock_manim_script, tmp_path, monkeypatch):
    """Verify subprocess.run is executed with close_fds=True."""
    run_id = temp_ledger.create_run(slug="close-fds-test")
    script_payload = {
        "slug": "close-fds-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_fds",
                    "animation_type": "array_highlight",
                    "description": "FD test cue",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    original_run = subprocess.run
    captured_kwargs = {}

    def mock_run(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"
    assert captured_kwargs.get("close_fds") is True


def test_no_file_descriptor_leak_on_execution(temp_ledger, mock_manim_script, tmp_path):
    """Verify system open file descriptors remain constant before vs after node execution."""
    run_id = temp_ledger.create_run(slug="fd-leak-test")
    script_payload = {
        "slug": "fd-leak-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_fd",
                    "animation_type": "array_highlight",
                    "description": "FD check",
                    "timestamp_seconds": 0.0,
                    "parameters": {"array": [1, 2]},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    fds_before = len(os.listdir("/proc/self/fd"))
    node.execute(run_id=run_id, ledger=temp_ledger)
    fds_after = len(os.listdir("/proc/self/fd"))

    assert fds_after == fds_before, f"FD leak detected: before={fds_before}, after={fds_after}"


def test_zero_byte_mp4_artifact_raises_animation_error(temp_ledger, tmp_path):
    """Verify 0-byte MP4 artifact produced by subprocess raises AnimationError."""
    run_id = temp_ledger.create_run(slug="zero-byte-artifact-test")

    zero_byte_script = tmp_path / "zero_byte_manim.py"
    zero_byte_script.write_text(
        "import sys, os\n"
        "media_dir = None\n"
        "out_arg = 'output.mp4'\n"
        "for i, arg in enumerate(sys.argv):\n"
        "    if arg == '--media_dir' and i + 1 < len(sys.argv):\n"
        "        media_dir = sys.argv[i + 1]\n"
        "    if arg == '-o' and i + 1 < len(sys.argv):\n"
        "        out_arg = sys.argv[i + 1]\n"
        "if media_dir:\n"
        "    os.makedirs(media_dir, exist_ok=True)\n"
        "    with open(os.path.join(media_dir, out_arg), 'wb') as f:\n"
        "        pass\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )

    script_payload = {
        "slug": "zero-byte-artifact-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_zero_byte",
                    "animation_type": "array_highlight",
                    "description": "Zero byte artifact test",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    node = AnimationGeneratorNode(
        manim_binary=str(zero_byte_script),
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    with pytest.raises(AnimationError) as exc_info:
        node.execute(run_id=run_id, ledger=temp_ledger)

    assert "no valid video artifact" in str(exc_info.value) or "empty file" in str(exc_info.value)


def test_invalid_binary_path_raises_animation_error(temp_ledger, tmp_path):
    """Verify non-existent binary path raises AnimationError wrapping FileNotFoundError as __cause__."""
    run_id = temp_ledger.create_run(slug="invalid-bin-test")

    script_payload = {
        "slug": "invalid-bin-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_invalid_bin",
                    "animation_type": "array_highlight",
                    "description": "Invalid binary test",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    invalid_bin_path = "/nonexistent/path/to/manim_binary_99999"
    node = AnimationGeneratorNode(
        manim_binary=invalid_bin_path,
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )

    with pytest.raises(AnimationError) as exc_info:
        node.execute(run_id=run_id, ledger=temp_ledger)

    assert "Failed to execute Manim subprocess" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, FileNotFoundError)


def test_cli_flags_and_command_array_construction(temp_ledger, mock_manim_script, tmp_path, monkeypatch):
    """Verify command array construction across quality flags, binary paths, and default manim_binary=None."""
    qualities_and_expected_flags = [
        ("low", "-ql"),
        ("480p", "-ql"),
        ("medium", "-qm"),
        ("720p", "-qm"),
        ("high", "-qh"),
        ("1080p", "-qh"),
        ("fourk", "-qk"),
        ("4k", "-qk"),
    ]

    for quality_name, expected_flag in qualities_and_expected_flags:
        captured_cmds = []

        def mock_run(cmd, *args, **kwargs):
            captured_cmds.append(cmd)
            out_idx = cmd.index("-o") + 1
            media_idx = cmd.index("--media_dir") + 1
            out_path = Path(cmd[media_idx]) / cmd[out_idx]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b"MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        run_id = temp_ledger.create_run(slug=f"cli-test-{quality_name}")
        script_payload = {
            "slug": f"cli-test-{quality_name}",
            "script": {
                "visual_cues": [
                    {
                        "cue_id": "cue_cli",
                        "animation_type": "array_highlight",
                        "timestamp_seconds": 0.0,
                        "parameters": {},
                    }
                ]
            },
        }
        step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
        temp_ledger.record_step_completion(step_id, output_payload=script_payload)

        node = AnimationGeneratorNode(
            manim_binary=mock_manim_script,
            quality=quality_name,
            output_dir=tmp_path / f"renders_{quality_name}",
            cache_dir=tmp_path / f"cache_{quality_name}",
        )

        node.execute(run_id=run_id, ledger=temp_ledger)

        assert len(captured_cmds) == 1
        cmd = captured_cmds[0]

        assert cmd[0] == sys.executable
        assert cmd[1] == mock_manim_script
        assert cmd[2] == "render"
        assert cmd[3] == expected_flag
        assert cmd[4] == "--format=mp4"
        assert cmd[5] == "--media_dir"
        assert cmd[7] == "-o"
        assert cmd[8] == "cue_cli.mp4"
        assert cmd[9].endswith("src/animation/scenes/array_scene.py")
        assert cmd[10] == "ArrayScene"

    # Test default manim_binary=None -> python -m manim
    captured_cmds_default = []

    def mock_run_default(cmd, *args, **kwargs):
        captured_cmds_default.append(cmd)
        out_idx = cmd.index("-o") + 1
        media_idx = cmd.index("--media_dir") + 1
        out_path = Path(cmd[media_idx]) / cmd[out_idx]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run_default)

    run_id_def = temp_ledger.create_run(slug="cli-test-default")
    step_id_def = temp_ledger.record_step_start(run_id_def, step_name="script_generator")
    temp_ledger.record_step_completion(
        step_id_def,
        output_payload={
            "slug": "cli-test-default",
            "script": {
                "visual_cues": [
                    {
                        "cue_id": "cue_def",
                        "animation_type": "array_highlight",
                        "timestamp_seconds": 0.0,
                        "parameters": {},
                    }
                ]
            },
        },
    )

    node_def = AnimationGeneratorNode(
        manim_binary=None,
        quality="medium",
        output_dir=tmp_path / "renders_def",
        cache_dir=tmp_path / "cache_def",
    )
    node_def.execute(run_id=run_id_def, ledger=temp_ledger)

    assert len(captured_cmds_default) == 1
    cmd_def = captured_cmds_default[0]
    assert cmd_def[0] == sys.executable
    assert cmd_def[1] == "-m"
    assert cmd_def[2] == "manim"
    assert cmd_def[3] == "render"


def test_subprocess_invocation_kwargs(temp_ledger, mock_manim_script, tmp_path, monkeypatch):
    """Verify subprocess invocation kwargs: cwd, timeout, capture_output, text, close_fds=True."""
    run_id = temp_ledger.create_run(slug="kwargs-test")
    script_payload = {
        "slug": "kwargs-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_kwargs",
                    "animation_type": "array_highlight",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    captured_kwargs = {}

    def mock_run(*args, **kwargs):
        captured_kwargs.update(kwargs)
        cmd = args[0]
        out_idx = cmd.index("-o") + 1
        media_idx = cmd.index("--media_dir") + 1
        out_path = Path(cmd[media_idx]) / cmd[out_idx]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    out_dir = tmp_path / "renders"
    cache_dir = tmp_path / "cache"

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
        timeout=45.0,
    )

    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"

    assert captured_kwargs.get("close_fds") is True
    assert captured_kwargs.get("capture_output") is True
    assert captured_kwargs.get("text") is True
    assert captured_kwargs.get("timeout") == 45.0
    assert captured_kwargs.get("cwd") is not None


@pytest.mark.parametrize("cue_type,expected_file,expected_class", [
    ("array_highlight", "src/animation/scenes/array_scene.py", "ArrayScene"),
    ("tree_traversal", "src/animation/scenes/tree_scene.py", "TreeScene"),
    ("code_highlight", "src/animation/scenes/code_scene.py", "CodeScene"),
    ("linkedlist_operation", "src/animation/scenes/linkedlist_scene.py", "LinkedListScene"),
    ("graph_traversal", "src/animation/scenes/graph_scene.py", "GraphScene"),
    ("hashmap_operation", "src/animation/scenes/hashmap_scene.py", "HashmapScene"),
    ("stack_queue_operation", "src/animation/scenes/stack_queue_scene.py", "StackQueueScene"),
    ("complexity_chart", "src/animation/scenes/complexity_scene.py", "ComplexityScene"),
])
def test_all_required_visual_cue_types_mapping_and_execution(
    temp_ledger, mock_manim_script, tmp_path, cue_type, expected_file, expected_class
):
    """Verify all 8 required visual cue types map to existing scene files/classes and execute successfully."""
    mapped = ANIMATION_TYPE_MAP.get(cue_type)
    assert mapped is not None, f"Missing mapping for '{cue_type}'"
    assert mapped[0] == expected_file
    assert mapped[1] == expected_class
    assert Path(expected_file).exists(), f"Scene file '{expected_file}' does not exist on disk"

    run_id = temp_ledger.create_run(slug=f"test-{cue_type}")
    script_payload = {
        "slug": f"test-{cue_type}",
        "script": {
            "visual_cues": [
                {
                    "cue_id": f"cue_{cue_type}",
                    "animation_type": cue_type,
                    "description": f"Test {cue_type}",
                    "timestamp_seconds": 0.0,
                    "parameters": {"duration": 3.0},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )
    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"
    assert result["render_count"] == 1


def test_unknown_animation_type_fallback(temp_ledger, mock_manim_script, tmp_path):
    """Verify unknown animation_type falls back gracefully to DEFAULT_SCENE (ArrayScene)."""
    run_id = temp_ledger.create_run(slug="unknown-anim-test")
    script_payload = {
        "slug": "unknown-anim-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_unknown",
                    "animation_type": "completely_unknown_type_xyz",
                    "description": "Unknown type test",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )
    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"
    assert result["segments"][0]["scene_type"] == "COMPLETELY_UNKNOWN_TYPE_XYZ"


def test_missing_or_none_parameters_and_defaults(temp_ledger, mock_manim_script, tmp_path):
    """Verify execution handles missing/None parameters, timestamp_seconds, and duration gracefully."""
    run_id = temp_ledger.create_run(slug="defaults-test")
    script_payload = {
        "slug": "defaults-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_no_params",
                    "animation_type": "array_highlight",
                    "timestamp_seconds": None,
                    "parameters": None,
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )
    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"
    seg = RenderSegment.model_validate(result["segments"][0])
    assert seg.start_time == 0.0
    assert seg.duration == 5.0
    assert seg.end_time == 5.0


def test_empty_visual_cues_list_returns_zero_segments(temp_ledger, tmp_path):
    """Verify script payload with 0 visual cues returns empty segments list and render_count=0."""
    run_id = temp_ledger.create_run(slug="empty-cues-test")
    script_payload = {
        "slug": "empty-cues-test",
        "script": {
            "visual_cues": []
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    node = AnimationGeneratorNode(
        output_dir=tmp_path / "renders",
        cache_dir=tmp_path / "cache",
    )
    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"
    assert result["render_count"] == 0
    assert len(result["segments"]) == 0


def test_cache_invalidation_on_parameter_change(temp_ledger, mock_manim_script, tmp_path):
    """Verify modifying parameters causes cache miss and invokes subprocess renderer."""
    out_dir = tmp_path / "renders"
    cache_dir = tmp_path / "cache"

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    # Initial render
    run_id1 = temp_ledger.create_run(slug="cache-miss-1")
    script_payload1 = {
        "slug": "cache-miss-1",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_param1",
                    "animation_type": "array_highlight",
                    "parameters": {"array": [1, 2, 3]},
                }
            ]
        },
    }
    s1 = temp_ledger.record_step_start(run_id1, step_name="script_generator")
    temp_ledger.record_step_completion(s1, output_payload=script_payload1)
    node.execute(run_id=run_id1, ledger=temp_ledger)

    # Render with different parameters -> Should trigger Cache MISS
    run_id2 = temp_ledger.create_run(slug="cache-miss-2")
    script_payload2 = {
        "slug": "cache-miss-2",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_param2",
                    "animation_type": "array_highlight",
                    "parameters": {"array": [9, 8, 7]},
                }
            ]
        },
    }
    s2 = temp_ledger.record_step_start(run_id2, step_name="script_generator")
    temp_ledger.record_step_completion(s2, output_payload=script_payload2)

    # Use failing mock binary to verify subprocess execution occurs on cache miss
    fail_node = AnimationGeneratorNode(
        manim_binary="/nonexistent/path/to/binary",
        output_dir=out_dir,
        cache_dir=cache_dir,
    )
    with pytest.raises(AnimationError):
        fail_node.execute(run_id=run_id2, ledger=temp_ledger)


def test_zero_byte_corrupt_cache_re_renders(temp_ledger, mock_manim_script, tmp_path):
    """Verify 0-byte corrupt cache file is ignored as cache miss, re-rendered, and overwritten."""
    out_dir = tmp_path / "renders"
    cache_dir = tmp_path / "cache"

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    cue_params = {"test": 123, "description": "Zero byte test cue", "duration": 5.0}
    cache_hash = node._compute_cache_hash("array_highlight", cue_params)
    cache_dir.mkdir(parents=True, exist_ok=True)
    corrupt_cache_file = cache_dir / f"{cache_hash}.mp4"
    corrupt_cache_file.write_bytes(b"")

    run_id = temp_ledger.create_run(slug="zero-byte-cache-test")
    script_payload = {
        "slug": "zero-byte-cache-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_corrupt",
                    "animation_type": "array_highlight",
                    "description": "Zero byte test cue",
                    "parameters": {"test": 123},
                }
            ]
        },
    }
    s1 = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(s1, output_payload=script_payload)

    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"
    assert corrupt_cache_file.stat().st_size > 0


def test_render_segment_schema_completeness(temp_ledger, mock_manim_script, tmp_path):
    """Verify RenderSegment schema fields (start_time, end_time, duration, asset_references, scene_type, visual_parameters, output_directory)."""
    run_id = temp_ledger.create_run(slug="schema-completeness-test")

    script_payload = {
        "slug": "schema-completeness-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_schema_01",
                    "animation_type": "array_highlight",
                    "description": "Schema test cue",
                    "timestamp_seconds": 12.5,
                    "parameters": {"array": [10, 20], "duration": 8.0},
                }
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    out_dir = tmp_path / "renders"
    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=out_dir,
        cache_dir=tmp_path / "cache",
    )

    result = node.execute(run_id=run_id, ledger=temp_ledger)

    assert "output_directory" in result
    assert result["output_directory"] == str(out_dir / run_id)

    seg_dict = result["segments"][0]
    seg = RenderSegment.model_validate(seg_dict)

    assert seg.segment_id == "seg_cue_schema_01"
    assert seg.segment_type == "visual_anim"
    assert seg.start_time == 12.5
    assert seg.duration == 8.0
    assert seg.end_time == 20.5
    assert seg.scene_type == "ARRAY_HIGHLIGHT"
    assert seg.visual_parameters["array"] == [10, 20]
    assert seg.visual_parameters["duration"] == 8.0
    assert seg.visual_path == str(out_dir / run_id / "segment_cue_schema_01.mp4")

    assert len(seg.asset_references) == 1
    asset_ref = seg.asset_references[0]
    assert asset_ref.asset_id == "asset_cue_schema_01"
    assert asset_ref.asset_type == "video"
    assert asset_ref.file_path == str(out_dir / run_id / "segment_cue_schema_01.mp4")
    assert asset_ref.duration == 8.0


def test_sub_100_byte_corrupt_cache_file_triggers_re_render(temp_ledger, mock_manim_script, tmp_path):
    """Verify sub-100 byte corrupt cache files are unlinked and re-rendered."""
    out_dir = tmp_path / "renders"
    cache_dir = tmp_path / "cache"

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    cue_params = {"test_key": "sub_100_corrupt_test", "description": "Sub 100 corrupt cue", "duration": 5.0}
    cache_hash = node._compute_cache_hash("array_highlight", cue_params)
    cache_dir.mkdir(parents=True, exist_ok=True)
    corrupt_cache_file = cache_dir / f"{cache_hash}.mp4"
    # Write a 50-byte partial/corrupt cache file (< 100 bytes)
    corrupt_cache_file.write_bytes(b"CORRUPT_PARTIAL_DATA_" * 2)
    assert corrupt_cache_file.stat().st_size < 100

    run_id = temp_ledger.create_run(slug="sub-100-cache-test")
    script_payload = {
        "slug": "sub-100-cache-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_sub100",
                    "animation_type": "array_highlight",
                    "description": "Sub 100 corrupt cue",
                    "parameters": {"test_key": "sub_100_corrupt_test"},
                }
            ]
        },
    }
    s1 = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(s1, output_payload=script_payload)

    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"
    assert corrupt_cache_file.stat().st_size >= 100, f"Cache file size should be >= 100 bytes, got {corrupt_cache_file.stat().st_size}"
    output_file = out_dir / run_id / "segment_cue_sub100.mp4"
    assert output_file.exists()
    assert output_file.stat().st_size >= 100


def test_cue_id_path_traversal_sanitization(temp_ledger, mock_manim_script, tmp_path):
    """Verify cue_ids with path traversal sequences ('../../etc/passwd', '..\\\\cue_1') are sanitized and remain inside run output dir."""
    run_id = temp_ledger.create_run(slug="path-traversal-test")
    
    script_payload = {
        "slug": "path-traversal-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "../../etc/passwd",
                    "animation_type": "array_highlight",
                    "timestamp_seconds": 0.0,
                    "parameters": {"array": [1, 2]},
                },
                {
                    "cue_id": "..\\cue_1",
                    "animation_type": "tree_traversal",
                    "timestamp_seconds": 5.0,
                    "parameters": {"root": 1},
                },
                {
                    "cue_id": "../escaped_segment",
                    "animation_type": "code_highlight",
                    "timestamp_seconds": 10.0,
                    "parameters": {"code": "x=1"},
                },
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    out_dir = tmp_path / "renders"
    cache_dir = tmp_path / "cache"

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"
    
    run_out_dir = out_dir / run_id
    assert (run_out_dir / "segment_passwd.mp4").exists()
    assert (run_out_dir / "segment_cue_1.mp4").exists()
    assert (run_out_dir / "segment_escaped_segment.mp4").exists()
    
    assert not (out_dir / "segment_escaped_segment.mp4").exists()
    assert not (out_dir / "segment_passwd.mp4").exists()
    assert not (out_dir / "segment_cue_1.mp4").exists()


def test_atomic_cache_write_mechanics(temp_ledger, mock_manim_script, tmp_path, monkeypatch):
    """Verify cache saving uses atomic file replacement via os.replace from a temporary file in cache_dir."""
    out_dir = tmp_path / "renders"
    cache_dir = tmp_path / "cache"

    replaced_files = []
    orig_replace = os.replace

    def mock_replace(src, dst):
        replaced_files.append((Path(src), Path(dst)))
        return orig_replace(src, dst)

    monkeypatch.setattr(os, "replace", mock_replace)

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    run_id = temp_ledger.create_run(slug="atomic-cache-test")
    script_payload = {
        "slug": "atomic-cache-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_atomic",
                    "animation_type": "array_highlight",
                    "parameters": {"key": "atomic_val"},
                }
            ]
        },
    }
    s1 = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(s1, output_payload=script_payload)

    node.execute(run_id=run_id, ledger=temp_ledger)

    cache_replaces = [r for r in replaced_files if r[1].parent == cache_dir and r[1].suffix == ".mp4"]
    assert len(cache_replaces) >= 1, "Cache write must execute atomic os.replace"
    src_file, dst_file = cache_replaces[0]
    assert src_file.suffix == ".tmp", "Source file for atomic replace must have .tmp suffix"
    assert src_file.parent == cache_dir, "Temporary file must reside in cache_dir for atomic replace"

