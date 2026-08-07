"""Unit and integration tests for VideoAssemblyNode and VideoAssembler (Phase 13).

Tests FFmpeg command generation, subprocess execution, error handling,
StateLedger integration, malformed inputs, schema validation, and temporary file cleanup.
"""

from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

pytest_plugins = []
import pytest

from src.assembly.assembler import VideoAssembler
from src.assembly.ffmpeg_commands import (
    build_4k_scale_filter,
    build_assembly_command,
    build_concat_filter_graph,
    build_demuxer_assembly_command,
    build_subtitle_filter,
    escape_ffmpeg_filter_path,
    write_concat_file,
)
from src.core.exceptions import AssemblyError, PipelineStageError
from src.core.models.assets import AssembledVideo, RenderSegment
from src.core.orchestrator.state_ledger import StateLedger
from src.pipeline.nodes.video_assembly_node import VideoAssemblyNode


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_ledger_db(temp_workspace):
    """Create a real SQLite StateLedger instance in a temporary file."""
    db_path = temp_workspace / "state_ledger.db"
    ledger = StateLedger(db_path=db_path)
    return ledger


@pytest.fixture
def create_dummy_video(temp_workspace):
    """Helper to create dummy video segment files."""
    def _create(filename="seg_0.mp4", size_bytes=200):
        filepath = temp_workspace / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(b"0" * size_bytes)
        return filepath
    return _create


@pytest.fixture
def create_dummy_audio(temp_workspace):
    """Helper to create dummy audio files."""
    def _create(filename="narration.wav", size_bytes=200):
        filepath = temp_workspace / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(b"0" * size_bytes)
        return filepath
    return _create


@pytest.fixture
def create_dummy_subtitle(temp_workspace):
    """Helper to create dummy subtitle SRT files."""
    def _create(filename="subtitles.srt"):
        filepath = temp_workspace / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        content = "1\n00:00:00,000 --> 00:00:05,000\nHello World\n\n"
        filepath.write_text(content, encoding="utf-8")
        return filepath
    return _create


# ============================================================================
# 1. FFmpeg Command Helper Tests
# ============================================================================

def test_escape_ffmpeg_filter_path():
    """Test path escaping for FFmpeg filter graph strings."""
    raw_path = "/tmp/path:with'quotes\\[and]colons.srt"
    escaped = escape_ffmpeg_filter_path(raw_path)
    assert "\\:" in escaped
    assert "\\'" in escaped
    assert "\\[" in escaped
    assert "\\]" in escaped


def test_write_concat_file(temp_workspace):
    """Test writing FFmpeg concat demuxer text manifest file."""
    f1 = temp_workspace / "seg1.mp4"
    f2 = temp_workspace / "seg2.mp4"
    manifest_p = temp_workspace / "concat.txt"

    result_p = write_concat_file([f1, f2], manifest_p)
    assert result_p.exists()
    content = result_p.read_text()
    assert f"file '{f1.resolve()}'" in content
    assert f"file '{f2.resolve()}'" in content


def test_build_4k_scale_filter():
    """Test 4K scaling filter string construction."""
    filter_str = build_4k_scale_filter("0:v", "v0", 3840, 2160)
    assert "[0:v]scale=3840:2160" in filter_str
    assert "pad=3840:2160" in filter_str
    assert "[v0]" in filter_str


def test_build_subtitle_filter():
    """Test subtitle filter string construction."""
    sub_filter = build_subtitle_filter("/path/to/sub.srt", input_label="v_in", output_label="v_out")
    assert "[v_in]subtitles=" in sub_filter
    assert "[v_out]" in sub_filter


def test_build_concat_filter_graph_single_video():
    """Test filter graph for a single video input without audio."""
    graph, v_map, a_map = build_concat_filter_graph(num_video_inputs=1, num_audio_inputs=0)
    assert "[0:v]scale=1920:1080" in graph
    assert v_map == "v0"
    assert a_map is None


def test_build_concat_filter_graph_multi_video_audio():
    """Test filter graph for multiple video inputs and an audio input."""
    graph, v_map, a_map = build_concat_filter_graph(
        num_video_inputs=2, num_audio_inputs=1, subtitle_path="/tmp/sub.srt"
    )
    assert "concat=n=2:v=1:a=0[v_concat]" in graph
    assert "subtitles=" in graph
    assert v_map == "v_out"
    assert a_map == "a_out"
    assert "aresample=48000" in graph


def test_build_assembly_command():
    """Test building complete assembly command list."""
    cmd = build_assembly_command(
        video_inputs=["/tmp/v1.mp4", "/tmp/v2.mp4"],
        audio_inputs=["/tmp/a1.wav"],
        output_path="/tmp/out.mp4",
        subtitle_path="/tmp/s1.srt",
        resolution="3840x2160",
        fps=30,
    )
    assert cmd[0] == "ffmpeg"
    assert "-y" in cmd
    assert "-i" in cmd
    assert "/tmp/v1.mp4" in cmd
    assert "/tmp/v2.mp4" in cmd
    assert "/tmp/a1.wav" in cmd
    assert "-filter_complex" in cmd
    assert "-c:v" in cmd
    assert "libx264" in cmd
    assert "/tmp/out.mp4" in cmd


def test_build_assembly_command_empty_inputs():
    """Test error raised when video inputs list is empty."""
    with pytest.raises(ValueError, match="video_inputs"):
        build_assembly_command(video_inputs=[], output_path="/tmp/out.mp4")


def test_build_demuxer_assembly_command():
    """Test building assembly command using demuxer manifest."""
    cmd = build_demuxer_assembly_command(
        video_manifest_path="/tmp/concat.txt",
        audio_manifest_path="/tmp/audio.wav",
        output_path="/tmp/out.mp4",
        subtitle_path="/tmp/sub.srt",
    )
    assert cmd[0] == "ffmpeg"
    assert "-f" in cmd
    assert "concat" in cmd
    assert "/tmp/concat.txt" in cmd
    assert "/tmp/out.mp4" in cmd


# ============================================================================
# 2. VideoAssembler Core Subprocess Execution Tests
# ============================================================================

def test_assembler_init():
    """Test VideoAssembler initialization with defaults."""
    assembler = VideoAssembler()
    assert assembler.ffmpeg_binary is None
    assert assembler.timeout == 300.0


def test_assembler_empty_segments():
    """Test VideoAssembler error when video_segments is empty."""
    assembler = VideoAssembler()
    with pytest.raises(AssemblyError, match="video_segments list is empty"):
        assembler.assemble(video_segments=[], output_path="/tmp/out.mp4")


def test_assembler_missing_input_file(temp_workspace):
    """Test VideoAssembler error when input segment file does not exist."""
    assembler = VideoAssembler()
    with pytest.raises(AssemblyError, match="Input video segment does not exist"):
        assembler.assemble(
            video_segments=[temp_workspace / "non_existent.mp4"],
            output_path=temp_workspace / "out.mp4",
        )


def test_assembler_missing_audio_or_sub_file(temp_workspace, create_dummy_video):
    """Test VideoAssembler error when audio or subtitle file path is specified but missing."""
    v1 = create_dummy_video("v1.mp4")
    assembler = VideoAssembler()

    with pytest.raises(AssemblyError, match="Input audio file does not exist"):
        assembler.assemble(video_segments=[v1], audio_path=temp_workspace / "missing.wav", output_path=temp_workspace / "out.mp4")

    with pytest.raises(AssemblyError, match="Input subtitle file does not exist"):
        assembler.assemble(video_segments=[v1], subtitle_path=temp_workspace / "missing.srt", output_path=temp_workspace / "out.mp4")


def test_assembler_subprocess_timeout(temp_workspace, create_dummy_video):
    """Test VideoAssembler handling of subprocess.TimeoutExpired."""
    v1 = create_dummy_video("v1.mp4")
    assembler = VideoAssembler()

    def mock_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=5.0, output="out", stderr="err")

    with patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(AssemblyError, match="timed out after"):
            assembler.assemble(video_segments=[v1], output_path=temp_workspace / "out.mp4", timeout=5.0)


def test_assembler_subprocess_failure(temp_workspace, create_dummy_video):
    """Test VideoAssembler error mapping on non-zero exit code."""
    v1 = create_dummy_video("v1.mp4")
    out = temp_workspace / "out.mp4"

    assembler = VideoAssembler(ffmpeg_binary="false")
    with patch.object(assembler, "run_command", side_effect=AssemblyError("FFmpeg assembly failed with exit code 1")):
        with pytest.raises(AssemblyError, match="FFmpeg assembly failed"):
            assembler.assemble(video_segments=[v1], output_path=out)


def test_assembler_successful_mock_execution(temp_workspace, create_dummy_video):
    """Test successful VideoAssembler execution with mocked subprocess."""
    v1 = create_dummy_video("v1.mp4")
    out = temp_workspace / "out.mp4"

    assembler = VideoAssembler()

    def mock_run_command(args, timeout=None, cwd=None):
        out_tmp = [a for a in args if a.endswith(".mp4") or "out.mp4" in a][-1]
        Path(out_tmp).write_bytes(b"0" * 200)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch.object(assembler, "run_command", side_effect=mock_run_command):
        result_path = assembler.assemble(video_segments=[v1], output_path=out)
        assert result_path.exists()
        assert result_path == out.resolve()
        assert result_path.stat().st_size >= 100


# ============================================================================
# 3. VideoAssemblyNode Integration & StateLedger Tests
# ============================================================================

def test_node_name():
    """Test VideoAssemblyNode step name."""
    node = VideoAssemblyNode()
    assert node.name == "video_assembly"


def test_execute_missing_ledger():
    """Test execution without StateLedger instance raises PipelineStageError."""
    node = VideoAssemblyNode()
    with pytest.raises(PipelineStageError, match="requires an active StateLedger"):
        node.execute("run-101", ledger=None)


def test_execute_missing_animation_step(mock_ledger_db):
    """Test execution when animation_generator step is missing from ledger."""
    run_id = mock_ledger_db.create_run("two-sum")
    node = VideoAssemblyNode()
    with pytest.raises(PipelineStageError, match="animation_generator"):
        node.execute(run_id, ledger=mock_ledger_db)


def test_execute_empty_animation_segments(mock_ledger_db):
    """Test execution when animation_generator output contains no segments."""
    run_id = mock_ledger_db.create_run("two-sum")
    exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        exec_id, output_payload={"slug": "two-sum", "segments": []}
    )

    node = VideoAssemblyNode()
    with pytest.raises(PipelineStageError, match="found no visual segments"):
        node.execute(run_id, ledger=mock_ledger_db)


def test_execute_non_dict_segments_list(mock_ledger_db):
    """Test execution when segments list contains non-dict elements."""
    run_id = mock_ledger_db.create_run("two-sum")
    exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        exec_id, output_payload={"slug": "two-sum", "segments": ["string_segment"]}
    )

    node = VideoAssemblyNode()
    with pytest.raises(PipelineStageError, match="No valid existing video segment files found"):
        node.execute(run_id, ledger=mock_ledger_db)


def test_execute_segment_missing_visual_path(mock_ledger_db):
    """Test execution when segment dict has neither visual_path nor video asset reference."""
    run_id = mock_ledger_db.create_run("two-sum")
    exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        exec_id,
        output_payload={"slug": "two-sum", "segments": [{"duration": 5.0}]},
    )

    node = VideoAssemblyNode()
    with pytest.raises(PipelineStageError, match="lacks a valid video visual_path"):
        node.execute(run_id, ledger=mock_ledger_db)


def test_execute_segment_file_not_found(mock_ledger_db):
    """Test execution when referenced segment file does not exist on disk."""
    run_id = mock_ledger_db.create_run("two-sum")
    exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        exec_id,
        output_payload={
            "slug": "two-sum",
            "segments": [{"visual_path": "/tmp/non_existent_video_segment_999.mp4", "duration": 5.0}],
        },
    )

    node = VideoAssemblyNode()
    with pytest.raises(PipelineStageError, match="does not exist"):
        node.execute(run_id, ledger=mock_ledger_db)


def test_execute_visual_path_from_asset_references(mock_ledger_db, create_dummy_video, temp_workspace):
    """Test extraction of visual_path from asset_references list when top-level visual_path is absent."""
    run_id = mock_ledger_db.create_run("asset-ref-test")
    v1 = create_dummy_video("ref_v1.mp4")

    exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        exec_id,
        output_payload={
            "slug": "asset-ref-test",
            "segments": [
                {
                    "asset_references": [
                        {"asset_type": "video", "file_path": str(v1)}
                    ],
                    "duration": 5.0,
                }
            ],
        },
    )

    node = VideoAssemblyNode(output_dir=temp_workspace)

    def mock_assemble(video_segments, output_path, **kwargs):
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(b"0" * 500)
        return out_p

    with patch.object(VideoAssembler, "assemble", side_effect=mock_assemble):
        payload = node.execute(run_id, ledger=mock_ledger_db)

    assert payload["slug"] == "asset-ref-test"
    assert len(payload["segments"]) == 1


def test_execute_unexpected_assembly_error(mock_ledger_db, create_dummy_video, temp_workspace):
    """Test catching unexpected non-AssemblyError exception during assembly."""
    run_id = mock_ledger_db.create_run("unexpected-err")
    v1 = create_dummy_video("v1.mp4")

    exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        exec_id,
        output_payload={"slug": "unexpected-err", "segments": [{"visual_path": str(v1)}]},
    )

    node = VideoAssemblyNode(output_dir=temp_workspace)

    with patch.object(VideoAssembler, "assemble", side_effect=RuntimeError("Disk full")):
        with pytest.raises(AssemblyError, match="Video assembly failed unexpectedly"):
            node.execute(run_id, ledger=mock_ledger_db)


def test_execute_corrupted_assembled_artifact(mock_ledger_db, create_dummy_video, temp_workspace):
    """Test AssemblyError raised when assembled video artifact size is < 100 bytes."""
    run_id = mock_ledger_db.create_run("corrupt-artifact")
    v1 = create_dummy_video("v1.mp4")

    exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        exec_id,
        output_payload={"slug": "corrupt-artifact", "segments": [{"visual_path": str(v1)}]},
    )

    node = VideoAssemblyNode(output_dir=temp_workspace)

    def mock_assemble_corrupt(video_segments, output_path, **kwargs):
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(b"0" * 20)  # Only 20 bytes (< 100)
        return out_p

    with patch.object(VideoAssembler, "assemble", side_effect=mock_assemble_corrupt):
        with pytest.raises(AssemblyError, match="Assembled video artifact missing or corrupted"):
            node.execute(run_id, ledger=mock_ledger_db)


def test_execute_assembled_video_validation_failure(mock_ledger_db, create_dummy_video, temp_workspace):
    """Test AssemblyError raised when AssembledVideo Pydantic validation fails."""
    run_id = mock_ledger_db.create_run("schema-fail")
    v1 = create_dummy_video("v1.mp4")

    exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        exec_id,
        output_payload={"slug": "schema-fail", "segments": [{"visual_path": str(v1)}]},
    )

    node = VideoAssemblyNode(output_dir=temp_workspace)

    def mock_assemble(video_segments, output_path, **kwargs):
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(b"0" * 500)
        return out_p

    with patch.object(VideoAssembler, "assemble", side_effect=mock_assemble):
        with patch.object(AssembledVideo, "__init__", side_effect=ValueError("Invalid model")):
            with pytest.raises(AssemblyError, match="Failed to validate AssembledVideo output schema"):
                node.execute(run_id, ledger=mock_ledger_db)


def test_execute_success_end_to_end(
    mock_ledger_db, temp_workspace, create_dummy_video, create_dummy_audio, create_dummy_subtitle
):
    """Test end-to-end execution of VideoAssemblyNode with real StateLedger and mocked FFmpeg execution."""
    run_id = mock_ledger_db.create_run("two-sum")

    v1 = create_dummy_video("anim_0.mp4")
    v2 = create_dummy_video("anim_1.mp4")
    audio = create_dummy_audio("narration.wav")
    sub = create_dummy_subtitle("subtitles.srt")

    anim_exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        anim_exec_id,
        output_payload={
            "slug": "Two Sum Problem",
            "segments": [
                {
                    "segment_id": "seg_0",
                    "segment_type": "intro",
                    "start_time": 0.0,
                    "end_time": 5.0,
                    "duration": 5.0,
                    "visual_path": str(v1),
                },
                {
                    "segment_id": "seg_1",
                    "segment_type": "code_walkthrough",
                    "start_time": 5.0,
                    "end_time": 10.0,
                    "duration": 5.0,
                    "visual_path": str(v2),
                },
            ],
        },
    )

    voice_exec_id = mock_ledger_db.record_step_start(run_id, "voice_generator")
    mock_ledger_db.record_step_completion(
        voice_exec_id,
        output_payload={
            "audio_path": str(audio),
            "subtitle_path": str(sub),
        },
    )

    out_dir = temp_workspace / "assembled_output"
    node = VideoAssemblyNode(output_dir=out_dir)

    def mock_assemble(video_segments, output_path, **kwargs):
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(b"0" * 500)
        return out_p

    with patch.object(VideoAssembler, "assemble", side_effect=mock_assemble):
        payload = node.execute(run_id, ledger=mock_ledger_db)

    model = AssembledVideo.model_validate(payload)
    assert model.slug == "two-sum-problem"
    assert model.file_size_bytes == 500
    assert model.total_duration_seconds == 10.0
    assert len(model.segments) == 2
    assert Path(model.final_video_path).exists()


def test_execute_fallback_segment_repair(mock_ledger_db, create_dummy_video, temp_workspace):
    """Test fallback mechanism when raw segment dictionary is malformed for RenderSegment validation."""
    run_id = mock_ledger_db.create_run("binary-search")

    v1 = create_dummy_video("anim_0.mp4")

    anim_exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        anim_exec_id,
        output_payload={
            "slug": "binary-search",
            "segments": [
                {
                    "segment_id": "custom_seg_1",
                    "segment_type": "INVALID_TYPE_ENUM",
                    "start_time": 0.0,
                    "visual_path": str(v1),
                }
            ],
        },
    )

    out_dir = temp_workspace / "assembled_output"
    node = VideoAssemblyNode(output_dir=out_dir)

    def mock_assemble(video_segments, output_path, **kwargs):
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(b"0" * 500)
        return out_p

    with patch.object(VideoAssembler, "assemble", side_effect=mock_assemble):
        payload = node.execute(run_id, ledger=mock_ledger_db)

    model = AssembledVideo.model_validate(payload)
    assert len(model.segments) == 1
    assert model.segments[0].segment_type == "visual_anim"
    assert model.segments[0].segment_id == "custom_seg_1"
    assert model.segments[0].duration == 5.0


def test_execute_fallback_script_generator_artifacts(
    mock_ledger_db, temp_workspace, create_dummy_video, create_dummy_audio
):
    """Test retrieval of audio/subtitle artifacts from script_generator when voice_generator is absent."""
    run_id = mock_ledger_db.create_run("graph-dfs")

    v1 = create_dummy_video("anim_0.mp4")
    audio = create_dummy_audio("script_audio.wav")

    anim_exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        anim_exec_id,
        output_payload={
            "slug": "graph-dfs",
            "segments": [{"visual_path": str(v1), "duration": 5.0}],
        },
    )

    script_exec_id = mock_ledger_db.record_step_start(run_id, "script_generator")
    mock_ledger_db.record_step_completion(
        script_exec_id,
        output_payload={
            "script": {
                "audio_path": str(audio),
                "srt_content": "1\n00:00:00,000 --> 00:00:05,000\nGraph DFS\n\n",
            }
        },
    )

    out_dir = temp_workspace / "assembled_output"
    node = VideoAssemblyNode(output_dir=out_dir)

    captured_kwargs = {}

    def mock_assemble(video_segments, output_path, **kwargs):
        captured_kwargs.update(kwargs)
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(b"0" * 500)
        return out_p

    with patch.object(VideoAssembler, "assemble", side_effect=mock_assemble):
        payload = node.execute(run_id, ledger=mock_ledger_db)

    assert captured_kwargs.get("audio_path") == audio
    assert captured_kwargs.get("subtitle_text") == "1\n00:00:00,000 --> 00:00:05,000\nGraph DFS\n\n"


def test_execute_malformed_start_time_type(mock_ledger_db, create_dummy_video, temp_workspace):
    """Test behavior when raw segment has start_time key set to None or invalid string."""
    run_id = mock_ledger_db.create_run("malformed-start-time")

    v1 = create_dummy_video("anim_0.mp4")

    anim_exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        anim_exec_id,
        output_payload={
            "slug": "malformed-start-time",
            "segments": [
                {
                    "segment_id": "seg_0",
                    "start_time": None,
                    "visual_path": str(v1),
                }
            ],
        },
    )

    node = VideoAssemblyNode(output_dir=temp_workspace)
    with pytest.raises((TypeError, ValueError, PipelineStageError, AssemblyError)):
        node.execute(run_id, ledger=mock_ledger_db)


# ============================================================================
# 4. Extended Coverage, Edge Cases, Security & Resource Sanitation Tests
# ============================================================================

def test_resolve_binary_command_python_script():
    """Test _resolve_binary_command when ffmpeg_binary is a python script."""
    assembler = VideoAssembler(ffmpeg_binary="/path/to/script.py")
    prefix = assembler._resolve_binary_command()
    assert prefix == [sys.executable, "/path/to/script.py"]


def test_resolve_command_variations():
    """Test _resolve_command argument array resolution logic."""
    assembler = VideoAssembler(ffmpeg_binary="/path/to/mock_ffmpeg.py")

    # Empty args
    res = assembler._resolve_command([])
    assert res == [sys.executable, "/path/to/mock_ffmpeg.py"]

    # Args already matching prefix
    args = [sys.executable, "/path/to/mock_ffmpeg.py", "-y"]
    assert assembler._resolve_command(args) == args

    # Args starting with 'ffmpeg' or custom binary string
    args2 = ["ffmpeg", "-y", "out.mp4"]
    assert assembler._resolve_command(args2) == [sys.executable, "/path/to/mock_ffmpeg.py", "-y", "out.mp4"]

    # Single binary string match
    assembler_binary = VideoAssembler(ffmpeg_binary="my_ffmpeg")
    assert assembler_binary._resolve_command(["my_ffmpeg", "-y"]) == ["my_ffmpeg", "-y"]
    assert assembler_binary._resolve_command(["ffmpeg", "-y"]) == ["my_ffmpeg", "-y"]
    assert assembler_binary._resolve_command(["other_cmd"]) == ["my_ffmpeg", "other_cmd"]


def test_is_valid_video_exception_handling(temp_workspace):
    """Test _is_valid_video handling when stat() throws an exception."""
    assembler = VideoAssembler()
    fake_file = temp_workspace / "fake.mp4"
    fake_file.write_bytes(b"1" * 200)

    with patch.object(Path, "exists", return_value=True):
        with patch.object(Path, "stat", side_effect=OSError("Permission denied")):
            assert assembler._is_valid_video(fake_file) is False


def test_run_command_generic_exception(temp_workspace):
    """Test run_command wrapping of generic unexpected subprocess exception into AssemblyError."""
    assembler = VideoAssembler()
    with patch("subprocess.run", side_effect=OSError("Execution failed")):
        with pytest.raises(AssemblyError, match="Failed to execute FFmpeg subprocess"):
            assembler.run_command(["ffmpeg", "-y"])


def test_run_command_nonzero_exit_stdout_fallback(temp_workspace):
    """Test run_command error output fallback to stdout when stderr is empty."""
    assembler = VideoAssembler()
    mock_res = MagicMock(returncode=1, stderr="", stdout="Fatal stdout error message")
    with patch("subprocess.run", return_value=mock_res):
        with pytest.raises(AssemblyError, match="Fatal stdout error message"):
            assembler.run_command(["ffmpeg", "-y"])


def test_assembler_assemble_empty_output_path(temp_workspace, create_dummy_video):
    """Test VideoAssembler error when output_path is empty or None."""
    v1 = create_dummy_video("v1.mp4")
    assembler = VideoAssembler()
    with pytest.raises(AssemblyError, match="output_path is required"):
        assembler.assemble(video_segments=[v1], output_path="")


def test_assembler_subtitle_text_temp_srt(temp_workspace, create_dummy_video):
    """Test VideoAssembler temp SRT file creation when subtitle_text is provided without subtitle_path."""
    v1 = create_dummy_video("v1.mp4")
    out = temp_workspace / "out.mp4"
    assembler = VideoAssembler(temp_dir=temp_workspace)

    captured_args = {}

    def mock_run_command(args, timeout=None, cwd=None):
        captured_args["args"] = args
        out_tmp = [a for a in args if a.endswith(".mp4") or "out.mp4" in a][-1]
        Path(out_tmp).write_bytes(b"0" * 200)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch.object(assembler, "run_command", side_effect=mock_run_command):
        res = assembler.assemble(
            video_segments=[v1],
            subtitle_text="1\n00:00:00,000 --> 00:00:02,000\nTemp Subtitle\n\n",
            output_path=out,
        )
        assert res.exists()
        arg_str = " ".join(captured_args["args"])
        assert "subtitles=" in arg_str or "subtitles.srt" in arg_str


def test_assembler_invalid_video_output_check(temp_workspace, create_dummy_video):
    """Test AssemblyError raised when FFmpeg completes but produces video < 100 bytes."""
    v1 = create_dummy_video("v1.mp4")
    out = temp_workspace / "out.mp4"
    assembler = VideoAssembler()

    def mock_run_small_file(args, timeout=None, cwd=None):
        out_tmp = [a for a in args if a.endswith(".mp4") or "out.mp4" in a][-1]
        Path(out_tmp).write_bytes(b"0" * 50)  # 50 bytes < 100
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch.object(assembler, "run_command", side_effect=mock_run_small_file):
        with pytest.raises(AssemblyError, match="produced invalid or empty file"):
            assembler.assemble(video_segments=[v1], output_path=out)


def test_assembler_cleanup_failure_resilience(temp_workspace, create_dummy_video):
    """Test exception path when temporary output file unlink fails in cleanup block."""
    v1 = create_dummy_video("v1.mp4")
    out = temp_workspace / "out.mp4"
    assembler = VideoAssembler()

    def mock_run_error(args, timeout=None, cwd=None):
        out_tmp = [a for a in args if a.endswith(".mp4") or "out.mp4" in a][-1]
        p = Path(out_tmp)
        p.write_bytes(b"partial data")
        raise AssemblyError("Simulated FFmpeg failure")

    with patch.object(assembler, "run_command", side_effect=mock_run_error):
        with patch.object(Path, "unlink", side_effect=OSError("Unlink failed")):
            with pytest.raises(AssemblyError, match="Simulated FFmpeg failure"):
                assembler.assemble(video_segments=[v1], output_path=out)


def test_build_subtitle_filter_custom_style():
    """Test build_subtitle_filter with force_style parameter dictionary."""
    sub_filter = build_subtitle_filter(
        "/path/to/sub.srt",
        force_style={"FontSize": "36", "PrimaryColour": "&H0000FFFF"},
        input_label="v_in",
        output_label="v_out",
    )
    assert "FontSize=36" in sub_filter
    assert "PrimaryColour=&H0000FFFF" in sub_filter


def test_build_concat_filter_graph_invalid_inputs():
    """Test build_concat_filter_graph raises ValueError when num_video_inputs < 1."""
    with pytest.raises(ValueError, match="num_video_inputs must be at least 1"):
        build_concat_filter_graph(num_video_inputs=0, num_audio_inputs=1)


def test_build_concat_filter_graph_single_audio():
    """Test build_concat_filter_graph handling of single audio input."""
    graph, v_map, a_map = build_concat_filter_graph(num_video_inputs=1, num_audio_inputs=1)
    assert "[1:a]aresample=48000[a_out]" in graph
    assert a_map == "a_out"


def test_build_assembly_command_resolution_string():
    """Test build_assembly_command resolution parsing and error handling."""
    cmd1 = build_assembly_command(
        video_inputs=["/tmp/v1.mp4"],
        output_path="/tmp/out.mp4",
        resolution="1920x1080",
    )
    assert "scale=1920:1080" in " ".join(cmd1)

    cmd2 = build_assembly_command(
        video_inputs=["/tmp/v1.mp4"],
        output_path="/tmp/out.mp4",
        resolution="invalid_res",
    )
    assert "scale=1920:1080" in " ".join(cmd2)


def test_build_assembly_command_via_demuxer_manifest():
    """Test build_assembly_command routing to build_demuxer_assembly_command when concat_list_path is set."""
    cmd = build_assembly_command(
        concat_list_path="/tmp/concat.txt",
        audio_path="/tmp/audio.wav",
        output_path="/tmp/out.mp4",
    )
    assert "-f" in cmd
    assert "concat" in cmd
    assert "/tmp/concat.txt" in cmd


def test_build_demuxer_assembly_command_txt_audio_manifest():
    """Test build_demuxer_assembly_command with text audio manifest file and subtitle style."""
    cmd = build_demuxer_assembly_command(
        video_manifest_path="/tmp/v_concat.txt",
        audio_manifest_path="/tmp/a_concat.txt",
        output_path="/tmp/out.mp4",
        subtitle_path="/tmp/sub.srt",
        subtitle_style={"FontSize": "40"},
    )
    cmd_str = " ".join(cmd)
    assert "-f concat -safe 0 -i /tmp/a_concat.txt" in cmd_str
    assert "FontSize=40" in cmd_str


def test_no_file_descriptor_leak_on_assembly(temp_workspace, create_dummy_video):
    """Verify open file descriptor count remains constant across assembly execution."""
    v1 = create_dummy_video("v1.mp4")
    out = temp_workspace / "out_fd_test.mp4"
    assembler = VideoAssembler()

    def mock_run_command(args, timeout=None, cwd=None):
        out_tmp = [a for a in args if a.endswith(".mp4") or "out_fd_test.mp4" in a][-1]
        Path(out_tmp).write_bytes(b"0" * 200)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch.object(assembler, "run_command", side_effect=mock_run_command):
        if os.path.exists("/proc/self/fd"):
            fds_before = len(os.listdir("/proc/self/fd"))
            assembler.assemble(video_segments=[v1], output_path=out)
            fds_after = len(os.listdir("/proc/self/fd"))
            assert fds_after == fds_before
        else:
            assembler.assemble(video_segments=[v1], output_path=out)


def test_explicit_temporary_directory_cleanup_on_success_and_failure(temp_workspace, create_dummy_video):
    """Verify context-managed temporary working directories are purged after execution."""
    v1 = create_dummy_video("v1.mp4")
    out_success = temp_workspace / "out_success.mp4"
    out_fail = temp_workspace / "out_fail.mp4"

    custom_temp = temp_workspace / "custom_temp"
    assembler = VideoAssembler(temp_dir=custom_temp)

    # 1. Success case
    def mock_run_success(args, timeout=None, cwd=None):
        assert cwd is not None and Path(cwd).exists()
        out_tmp = [a for a in args if a.endswith(".mp4") or "out_success.mp4" in a][-1]
        Path(out_tmp).write_bytes(b"0" * 200)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch.object(assembler, "run_command", side_effect=mock_run_success):
        assembler.assemble(video_segments=[v1], output_path=out_success)

    temp_subdirs = list(custom_temp.glob("assembly_*"))
    assert len(temp_subdirs) == 0

    # 2. Failure case
    def mock_run_fail(args, timeout=None, cwd=None):
        raise AssemblyError("Simulated FFmpeg failure")

    with patch.object(assembler, "run_command", side_effect=mock_run_fail):
        with pytest.raises(AssemblyError):
            assembler.assemble(video_segments=[v1], output_path=out_fail)

    temp_subdirs = list(custom_temp.glob("assembly_*"))
    assert len(temp_subdirs) == 0


def test_mock_python_binary_script_execution(temp_workspace, create_dummy_video):
    """Test full assembly execution using a mock Python binary script fixture."""
    v1 = create_dummy_video("seg1.mp4")
    out = temp_workspace / "final_mock_assembled.mp4"

    mock_script = temp_workspace / "mock_ffmpeg.py"
    mock_script_content = """import sys, os
out_file = sys.argv[-1]
if "--fail" in sys.argv:
    sys.stderr.write("Simulated CLI Error\\n")
    sys.exit(1)
os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
with open(out_file, "wb") as f:
    f.write(b"MOCK_4K_VIDEO_STREAM_DATA_" * 10)
sys.exit(0)
"""
    mock_script.write_text(mock_script_content, encoding="utf-8")

    assembler = VideoAssembler(ffmpeg_binary=str(mock_script))
    res = assembler.assemble(video_segments=[v1], output_path=out)
    assert res.exists()
    assert res.stat().st_size >= 100


def test_run_command_subprocess_security_flags(temp_workspace):
    """Verify run_command invokes subprocess.run with secure flags (close_fds=True, capture_output=True, text=True)."""
    assembler = VideoAssembler()
    captured_kwargs = {}

    def mock_subprocess_run(cmd, **kwargs):
        captured_kwargs.update(kwargs)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="OK", stderr="")

    with patch("subprocess.run", side_effect=mock_subprocess_run):
        res = assembler.run_command(["ffmpeg", "-version"])
        assert res.returncode == 0
        assert captured_kwargs.get("close_fds") is True
        assert captured_kwargs.get("capture_output") is True
        assert captured_kwargs.get("text") is True
        assert "shell" not in captured_kwargs or captured_kwargs["shell"] is False


def test_video_assembly_node_assembly_error_re_raised(mock_ledger_db, create_dummy_video, temp_workspace):
    """Test that VideoAssemblyNode re-raises AssemblyError without double-wrapping."""
    run_id = mock_ledger_db.create_run("re-raise-test")
    v1 = create_dummy_video("anim_0.mp4")

    anim_exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        anim_exec_id,
        output_payload={
            "slug": "re-raise-test",
            "segments": [{"visual_path": str(v1), "duration": 5.0}],
        },
    )

    node = VideoAssemblyNode(output_dir=temp_workspace)

    with patch.object(VideoAssembler, "assemble", side_effect=AssemblyError("Direct AssemblyError")):
        with pytest.raises(AssemblyError, match="Direct AssemblyError"):
            node.execute(run_id, ledger=mock_ledger_db)


def test_video_assembly_node_top_level_srt_content(mock_ledger_db, temp_workspace, create_dummy_video, create_dummy_audio):
    """Test retrieval of top-level srt_content string from script_generator output."""
    run_id = mock_ledger_db.create_run("top-level-srt")
    v1 = create_dummy_video("anim_0.mp4")
    audio = create_dummy_audio("narration.wav")

    anim_exec_id = mock_ledger_db.record_step_start(run_id, "animation_generator")
    mock_ledger_db.record_step_completion(
        anim_exec_id,
        output_payload={
            "slug": "top-level-srt",
            "segments": [{"visual_path": str(v1), "duration": 5.0}],
        },
    )

    script_exec_id = mock_ledger_db.record_step_start(run_id, "script_generator")
    mock_ledger_db.record_step_completion(
        script_exec_id,
        output_payload={
            "audio_path": str(audio),
            "srt_content": "1\n00:00:00,000 --> 00:00:03,000\nTop level SRT\n\n",
        },
    )

    node = VideoAssemblyNode(output_dir=temp_workspace)
    captured_kwargs = {}

    def mock_assemble(video_segments, output_path, **kwargs):
        captured_kwargs.update(kwargs)
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(b"0" * 500)
        return out_p

    with patch.object(VideoAssembler, "assemble", side_effect=mock_assemble):
        payload = node.execute(run_id, ledger=mock_ledger_db)

    assert captured_kwargs.get("subtitle_text") == "1\n00:00:00,000 --> 00:00:03,000\nTop level SRT\n\n"


def test_build_assembly_command_default_output_path():
    """Test build_assembly_command default output_path when output_path is None."""
    cmd = build_assembly_command(video_inputs=["/tmp/v1.mp4"], output_path=None)
    assert cmd[-1] == "output.mp4"


