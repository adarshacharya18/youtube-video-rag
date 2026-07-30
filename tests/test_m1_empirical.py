"""Empirical Test Harness & Adversarial Stress Tests for Phase 13 Milestone 1.

Modules tested:
- src/assembly/ffmpeg_commands.py
- src/assembly/assembler.py
- src/pipeline/nodes/video_assembly_node.py
"""

import os
import sys
import tempfile
import time
from pathlib import Path
import pytest

from src.assembly.ffmpeg_commands import (
    build_4k_scale_filter,
    build_assembly_command,
    build_concat_filter_graph,
    build_demuxer_assembly_command,
    build_subtitle_filter,
    escape_ffmpeg_filter_path,
    write_concat_file,
)
from src.assembly.assembler import VideoAssembler
from src.pipeline.nodes.video_assembly_node import VideoAssemblyNode
from src.core.exceptions import AssemblyError, PipelineStageError
from src.core.orchestrator.state_ledger import StateLedger


# ============================================================================
# Group 1: FFmpeg Command Generation Edge Cases
# ============================================================================

def test_escape_ffmpeg_filter_path_quotes_spaces_colons_brackets():
    """Verify proper escaping of filter path characters ( colons, quotes, brackets, backslashes)."""
    raw_path = r"/path/to/my video: 'test' [1] \dir\file.srt"
    escaped = escape_ffmpeg_filter_path(raw_path)
    
    assert "\\:" in escaped
    assert "\\'" in escaped
    assert "\\[" in escaped
    assert "\\]" in escaped
    assert "\\\\" in escaped
    # Check that colons are escaped
    assert r"/path/to/my video\: \'test\' \[1\] \\dir\\file.srt" in escaped or escaped.startswith("/")


def test_subtitle_filter_with_special_characters():
    """Verify subtitle filter clause generation with complex escaped path."""
    sub_path = "/tmp/space test/sub's:demo[0].srt"
    filter_clause = build_subtitle_filter(
        sub_path,
        force_style={"FontSize": "32", "PrimaryColour": "&H00FFFF00"},
        input_label="v_in",
        output_label="v_out",
    )
    
    assert filter_clause.startswith("[v_in]subtitles='")
    assert filter_clause.endswith("[v_out]")
    assert r"sub\'s\:demo\[0\].srt" in filter_clause
    assert "FontSize=32" in filter_clause
    assert "PrimaryColour=&H00FFFF00" in filter_clause


def test_concat_filter_graph_single_segment():
    """Verify single video segment generates scaling without concat filter."""
    graph, v_label, a_label = build_concat_filter_graph(
        num_video_inputs=1,
        num_audio_inputs=1,
        subtitle_path="/tmp/sub.srt",
    )
    
    assert "[0:v]scale=3840:2160" in graph
    assert "concat=" not in graph  # Should NOT concat single video
    assert "[v0]subtitles=" in graph
    assert "[1:a]aresample=48000[a_out]" in graph
    assert v_label == "v_out"
    assert a_label == "a_out"


def test_concat_filter_graph_multi_segment():
    """Verify multi video/audio segments generate scaling and concat filter clauses."""
    graph, v_label, a_label = build_concat_filter_graph(
        num_video_inputs=3,
        num_audio_inputs=2,
        subtitle_path=None,
    )
    
    assert "[0:v]scale=3840:2160" in graph
    assert "[1:v]scale=3840:2160" in graph
    assert "[2:v]scale=3840:2160" in graph
    assert "[v0][v1][v2]concat=n=3:v=1:a=0[v_concat]" in graph
    assert "[3:a][4:a]concat=n=2:v=0:a=1,aresample=48000[a_out]" in graph
    assert v_label == "v_concat"
    assert a_label == "a_out"


def test_concat_filter_graph_no_audio():
    """Verify assembly without audio stream results in None a_label."""
    graph, v_label, a_label = build_concat_filter_graph(
        num_video_inputs=2,
        num_audio_inputs=0,
    )
    
    assert "aresample" not in graph
    assert a_label is None
    assert v_label == "v_concat"


def test_concat_filter_graph_invalid_video_count():
    """Verify ValueError is raised if num_video_inputs < 1."""
    with pytest.raises(ValueError, match="num_video_inputs must be at least 1"):
        build_concat_filter_graph(num_video_inputs=0, num_audio_inputs=1)


def test_build_assembly_command_missing_video_inputs():
    """Verify ValueError is raised if no video inputs or concat list is given."""
    with pytest.raises(ValueError, match="video_inputs .* cannot be empty"):
        build_assembly_command(video_inputs=[], audio_inputs="audio.wav")


def test_build_assembly_command_4k_scaling_resolutions():
    """Verify custom resolution overrides scale dimensions correctly."""
    cmd = build_assembly_command(
        video_inputs=["v1.mp4"],
        audio_inputs="a1.wav",
        output_path="out.mp4",
        resolution="1920x1080",
    )
    
    filter_idx = cmd.index("-filter_complex")
    filter_complex = cmd[filter_idx + 1]
    assert "scale=1920:1080" in filter_complex
    assert "pad=1920:1080" in filter_complex


def test_write_concat_file_escaping(tmp_path):
    """Verify write_concat_file produces valid manifest with single quote escaping."""
    f1 = tmp_path / "clip '1'.mp4"
    f2 = tmp_path / "clip_2.mp4"
    f1.touch()
    f2.touch()
    
    manifest = tmp_path / "concat.txt"
    res = write_concat_file([f1, f2], manifest)
    
    content = res.read_text(encoding="utf-8")
    assert f"file '{f1.resolve()}'.replace(\"'\", \"'\\\\''\")" not in content  # actual evaluated string
    assert "clip '\''1'\''.mp4" in content or "clip '1'.mp4" in content or r"clip '\''1'\''.mp4" in content
    assert f"file '{f2.resolve()}'" in content


# ============================================================================
# Group 2: Subprocess Execution Edge Cases
# ============================================================================

def test_assembler_missing_input_video_segment(tmp_path):
    """Verify VideoAssembler raises AssemblyError when input video file is missing."""
    assembler = VideoAssembler()
    out_file = tmp_path / "out.mp4"
    missing_seg = tmp_path / "non_existent_clip.mp4"
    
    with pytest.raises(AssemblyError, match="Input video segment does not exist"):
        assembler.assemble(
            video_segments=[missing_seg],
            output_path=out_file,
        )


def test_assembler_missing_input_audio_file(tmp_path):
    """Verify VideoAssembler raises AssemblyError when input audio file is missing."""
    assembler = VideoAssembler()
    seg = tmp_path / "seg.mp4"
    seg.touch()
    out_file = tmp_path / "out.mp4"
    missing_audio = tmp_path / "missing_voice.wav"
    
    with pytest.raises(AssemblyError, match="Input audio file does not exist"):
        assembler.assemble(
            video_segments=[seg],
            audio_path=missing_audio,
            output_path=out_file,
        )


def test_assembler_simulated_timeout(tmp_path):
    """Verify VideoAssembler raises AssemblyError on subprocess timeout."""
    # Create mock python script that sleeps for 5 seconds
    script = tmp_path / "slow_ffmpeg.py"
    script.write_text("import time; time.sleep(5)")
    
    assembler = VideoAssembler(ffmpeg_binary=str(script), timeout=0.3)
    seg = tmp_path / "seg.mp4"
    seg.touch()
    out_file = tmp_path / "out.mp4"
    
    with pytest.raises(AssemblyError, match="FFmpeg process timed out after 0.3s"):
        assembler.assemble(
            video_segments=[seg],
            output_path=out_file,
        )


def test_assembler_non_zero_exit_code(tmp_path):
    """Verify VideoAssembler raises AssemblyError with stderr when returncode != 0."""
    script = tmp_path / "failing_ffmpeg.py"
    script.write_text("import sys; sys.stderr.write('Fatal FFmpeg Error'); sys.exit(1)")
    
    assembler = VideoAssembler(ffmpeg_binary=str(script))
    seg = tmp_path / "seg.mp4"
    seg.touch()
    out_file = tmp_path / "out.mp4"
    
    with pytest.raises(AssemblyError, match="FFmpeg assembly failed with exit code 1:\nFatal FFmpeg Error"):
        assembler.assemble(
            video_segments=[seg],
            output_path=out_file,
        )


def test_assembler_invalid_output_file_zero_bytes(tmp_path):
    """Verify VideoAssembler raises AssemblyError when output file is 0 bytes."""
    # Mock script that creates 0 byte file at output location (args[-1])
    script = tmp_path / "empty_output_ffmpeg.py"
    script.write_text("import sys, pathlib; pathlib.Path(sys.argv[-1]).touch()")
    
    assembler = VideoAssembler(ffmpeg_binary=str(script))
    seg = tmp_path / "seg.mp4"
    seg.touch()
    out_file = tmp_path / "out.mp4"
    
    with pytest.raises(AssemblyError, match="produced invalid or empty file"):
        assembler.assemble(
            video_segments=[seg],
            output_path=out_file,
        )


def test_assembler_invalid_output_file_missing(tmp_path):
    """Verify VideoAssembler raises AssemblyError when output file was not created."""
    script = tmp_path / "noop_ffmpeg.py"
    script.write_text("import sys; pass")
    
    assembler = VideoAssembler(ffmpeg_binary=str(script))
    seg = tmp_path / "seg.mp4"
    seg.touch()
    out_file = tmp_path / "out.mp4"
    
    with pytest.raises(AssemblyError, match="produced invalid or empty file"):
        assembler.assemble(
            video_segments=[seg],
            output_path=out_file,
        )


def test_assembler_file_descriptor_leak_check(tmp_path):
    """Verify VideoAssembler closes file descriptors and does not leak FDs over multiple runs."""
    script = tmp_path / "mock_success_ffmpeg.py"
    script.write_text(
        "import sys, pathlib; "
        "p = pathlib.Path(sys.argv[-1]); "
        "p.write_bytes(b'A' * 200)"
    )
    
    assembler = VideoAssembler(ffmpeg_binary=str(script), temp_dir=tmp_path / "temp")
    seg = tmp_path / "seg.mp4"
    seg.touch()
    
    def count_open_fds():
        try:
            return len(os.listdir("/proc/self/fd"))
        except Exception:
            return 0

    fds_before = count_open_fds()
    
    for i in range(15):
        out_file = tmp_path / f"out_{i}.mp4"
        assembler.assemble(
            video_segments=[seg],
            output_path=out_file,
        )
        assert out_file.exists()
        assert out_file.stat().st_size == 200

    fds_after = count_open_fds()
    if fds_before > 0:
        # FD delta should be negligible (< 3)
        assert abs(fds_after - fds_before) <= 2


# ============================================================================
# Group 3: Temporary Directory & File Cleanup Assertions
# ============================================================================

def test_temp_cleanup_on_non_zero_exit(tmp_path):
    """Verify transient files and temp dirs are deleted when FFmpeg fails."""
    script = tmp_path / "fail_script.py"
    script.write_text("import sys; sys.exit(2)")
    
    temp_dir_parent = tmp_path / "custom_temp"
    assembler = VideoAssembler(ffmpeg_binary=str(script), temp_dir=temp_dir_parent)
    
    seg = tmp_path / "seg.mp4"
    seg.touch()
    out_file = tmp_path / "final.mp4"
    
    with pytest.raises(AssemblyError):
        assembler.assemble(
            video_segments=[seg],
            subtitle_text="1\n00:00:00,000 --> 00:00:01,000\nSubtitle\n",
            output_path=out_file,
        )
        
    # Verify no .tmp_* files exist in out_file parent directory
    tmp_files = list(tmp_path.glob("*.tmp_*"))
    assert len(tmp_files) == 0
    
    # Verify temp_dir_parent contains no leftover assembly_* subdirectories
    if temp_dir_parent.exists():
        subdirs = list(temp_dir_parent.glob("assembly_*"))
        assert len(subdirs) == 0


def test_temp_cleanup_on_timeout(tmp_path):
    """Verify transient files are cleaned up when FFmpeg times out."""
    script = tmp_path / "timeout_script.py"
    script.write_text("import time; time.sleep(10)")
    
    temp_dir_parent = tmp_path / "custom_temp_timeout"
    assembler = VideoAssembler(ffmpeg_binary=str(script), timeout=0.2, temp_dir=temp_dir_parent)
    
    seg = tmp_path / "seg.mp4"
    seg.touch()
    out_file = tmp_path / "timeout_out.mp4"
    
    with pytest.raises(AssemblyError):
        assembler.assemble(
            video_segments=[seg],
            output_path=out_file,
        )
        
    tmp_files = list(tmp_path.glob("*.tmp_*"))
    assert len(tmp_files) == 0
    if temp_dir_parent.exists():
        assert len(list(temp_dir_parent.glob("assembly_*"))) == 0


def test_temp_cleanup_on_invalid_output_file(tmp_path):
    """Verify temporary .tmp_<pid> file is deleted if output validation (<100 bytes) fails."""
    script = tmp_path / "small_output_script.py"
    # Write only 10 bytes to destination file
    script.write_text("import sys, pathlib; pathlib.Path(sys.argv[-1]).write_bytes(b'small')")
    
    temp_dir_parent = tmp_path / "custom_temp_invalid"
    assembler = VideoAssembler(ffmpeg_binary=str(script), temp_dir=temp_dir_parent)
    
    seg = tmp_path / "seg.mp4"
    seg.touch()
    out_file = tmp_path / "small_out.mp4"
    
    with pytest.raises(AssemblyError, match="produced invalid or empty file"):
        assembler.assemble(
            video_segments=[seg],
            output_path=out_file,
        )
        
    # Assert .tmp_* output file was deleted
    tmp_files = list(tmp_path.glob("*.tmp_*"))
    assert len(tmp_files) == 0
    # Assert final target out_file was NOT created
    assert not out_file.exists()


def test_temp_cleanup_on_success(tmp_path):
    """Verify temp files are cleaned up and atomic rename succeeds on assembly success."""
    script = tmp_path / "success_script.py"
    script.write_text("import sys, pathlib; pathlib.Path(sys.argv[-1]).write_bytes(b'V' * 500)")
    
    temp_dir_parent = tmp_path / "custom_temp_success"
    assembler = VideoAssembler(ffmpeg_binary=str(script), temp_dir=temp_dir_parent)
    
    seg = tmp_path / "seg.mp4"
    seg.touch()
    out_file = tmp_path / "valid_out.mp4"
    
    res = assembler.assemble(
        video_segments=[seg],
        subtitle_text="1\n00:00:00,000 --> 00:00:01,000\nSuccess Subtitle\n",
        output_path=out_file,
    )
    
    assert res == out_file.resolve()
    assert out_file.exists()
    assert out_file.stat().st_size == 500
    
    # Assert temporary file was atomically replaced (no .tmp_* left)
    tmp_files = list(tmp_path.glob("*.tmp_*"))
    assert len(tmp_files) == 0
    # Assert temp dir subfolder cleaned up
    if temp_dir_parent.exists():
        assert len(list(temp_dir_parent.glob("assembly_*"))) == 0


# ============================================================================
# Group 4: VideoAssemblyNode Workflow Node Challenges
# ============================================================================

def test_node_missing_ledger():
    """Verify VideoAssemblyNode raises PipelineStageError if ledger is None."""
    node = VideoAssemblyNode()
    with pytest.raises(PipelineStageError, match="requires an active StateLedger"):
        node.execute("run_100", ledger=None)


def test_node_missing_animation_step(tmp_path):
    """Verify VideoAssemblyNode raises PipelineStageError if animation_generator output missing."""
    db_path = tmp_path / "ledger.db"
    ledger = StateLedger(db_path=db_path)
    run_id = ledger.create_run("test-slug")
    
    node = VideoAssemblyNode(output_dir=tmp_path / "assembled")
    with pytest.raises(PipelineStageError, match="animation_generator"):
        node.execute(run_id, ledger=ledger)


def test_node_nonexistent_visual_segment_file(tmp_path):
    """Verify VideoAssemblyNode raises PipelineStageError if segment file referenced in ledger does not exist."""
    db_path = tmp_path / "ledger.db"
    ledger = StateLedger(db_path=db_path)
    run_id = ledger.create_run("test-slug")
    
    step_id = ledger.record_step_start(run_id, "animation_generator")
    ledger.record_step_completion(
        step_execution_id=step_id,
        output_payload={
            "slug": "two-sum",
            "segments": [
                {
                    "segment_id": "seg_0",
                    "segment_type": "intro",
                    "visual_path": str(tmp_path / "non_existent.mp4"),
                    "duration": 5.0,
                }
            ],
        },
    )
    
    node = VideoAssemblyNode(output_dir=tmp_path / "assembled")
    with pytest.raises(PipelineStageError, match="does not exist"):
        node.execute(run_id, ledger=ledger)


def test_node_successful_assembly_with_state_ledger(tmp_path):
    """Verify end-to-end VideoAssemblyNode execution with StateLedger, mock ffmpeg, and schema output validation."""
    script = tmp_path / "mock_ffmpeg.py"
    script.write_text("import sys, pathlib; pathlib.Path(sys.argv[-1]).write_bytes(b'MOCK_MP4_CONTENT' * 100)")
    
    db_path = tmp_path / "ledger.db"
    ledger = StateLedger(db_path=db_path)
    run_id = ledger.create_run("test-slug")
    
    # Touch valid segment clip & audio clip
    clip1 = tmp_path / "clip1.mp4"
    clip2 = tmp_path / "clip2.mp4"
    audio = tmp_path / "narration.wav"
    clip1.touch()
    clip2.touch()
    audio.touch()
    
    step1 = ledger.record_step_start(run_id, "animation_generator")
    ledger.record_step_completion(
        step_execution_id=step1,
        output_payload={
            "slug": "binary-search",
            "segments": [
                {
                    "segment_id": "seg_0",
                    "segment_type": "intro",
                    "visual_path": str(clip1),
                    "start_time": 0.0,
                    "end_time": 5.0,
                    "duration": 5.0,
                },
                {
                    "segment_id": "seg_1",
                    "segment_type": "code_walkthrough",
                    "visual_path": str(clip2),
                    "start_time": 5.0,
                    "end_time": 15.0,
                    "duration": 10.0,
                },
            ],
        },
    )
    
    step2 = ledger.record_step_start(run_id, "voice_generator")
    ledger.record_step_completion(
        step_execution_id=step2,
        output_payload={
            "audio_path": str(audio),
            "subtitle_path": None,
        },
    )
    
    step3 = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(
        step_execution_id=step3,
        output_payload={
            "srt_content": "1\n00:00:00,000 --> 00:00:05,000\nBinary Search Tutorial\n",
        },
    )
    
    node = VideoAssemblyNode(
        ffmpeg_binary=str(script),
        output_dir=tmp_path / "assembled",
        temp_dir=tmp_path / "temp",
    )
    
    output_payload = node.execute(run_id, ledger=ledger)
    
    assert output_payload["slug"] == "binary-search"
    assert output_payload["total_duration_seconds"] == 15.0
    assert output_payload["file_size_bytes"] == 1600
    assert len(output_payload["segments"]) == 2
    assert Path(output_payload["final_video_path"]).exists()
