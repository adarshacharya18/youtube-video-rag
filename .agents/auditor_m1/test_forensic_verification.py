import ast
import os
from pathlib import Path
import sys
import tempfile
import time

# Add project root to sys.path
PROJECT_ROOT = Path("/home/adarsh/Documents/Youtube-Channel")
sys.path.insert(0, str(PROJECT_ROOT))

from src.assembly.ffmpeg_commands import (
    escape_ffmpeg_filter_path,
    write_concat_file,
    build_4k_scale_filter,
    build_subtitle_filter,
    build_concat_filter_graph,
    build_assembly_command,
    build_demuxer_assembly_command,
)
from src.assembly.assembler import VideoAssembler
from src.pipeline.nodes.video_assembly_node import VideoAssemblyNode
from src.core.exceptions import AssemblyError, PipelineStageError
from src.core.orchestrator.state_ledger import StateLedger


def run_ast_analysis():
    print("--- Running AST Analysis ---")
    files_to_check = [
        PROJECT_ROOT / "src/assembly/ffmpeg_commands.py",
        PROJECT_ROOT / "src/assembly/assembler.py",
        PROJECT_ROOT / "src/pipeline/nodes/video_assembly_node.py",
    ]

    for file_path in files_to_check:
        print(f"Checking AST for {file_path.relative_to(PROJECT_ROOT)}...")
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        tree = ast.parse(code, filename=str(file_path))

        # Inspect function definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for empty or dummy functions
                if len(node.body) == 1 and isinstance(node.body[0], (ast.Pass, ast.Constant)):
                    print(f"  [WARNING] Suspicious single-statement body in function '{node.name}'")

                # Check for return constant without logic
                if len(node.body) == 1 and isinstance(node.body[0], ast.Return) and isinstance(node.body[0].value, ast.Constant):
                    print(f"  [WARNING] Constant return in function '{node.name}'")

    print("AST Analysis completed.\n")


def run_command_builder_tests():
    print("--- Running Command Builder Unit Verification ---")
    
    # 1. escape_ffmpeg_filter_path
    path_with_specials = "/tmp/dir with: colon/file's [1].srt"
    escaped = escape_ffmpeg_filter_path(path_with_specials)
    print(f"Escaped path: {escaped}")
    assert "\\:" in escaped
    assert "\\'" in escaped
    assert "\\[" in escaped
    assert "\\]" in escaped

    # 2. build_assembly_command
    cmd = build_assembly_command(
        video_inputs=["clip1.mp4", "clip2.mp4"],
        audio_inputs=["audio.wav"],
        subtitle_path="subs.srt",
        output_path="out.mp4",
        resolution="3840x2160",
        fps=30,
        crf=18,
    )
    print(f"Generated FFmpeg CLI: {' '.join(cmd)}")
    assert cmd[0] == "ffmpeg"
    assert "-y" in cmd
    assert "-i" in cmd
    assert "clip1.mp4" in cmd
    assert "clip2.mp4" in cmd
    assert "audio.wav" in cmd
    assert "-filter_complex" in cmd
    assert "subtitles=" in cmd[cmd.index("-filter_complex") + 1]
    assert "-c:v" in cmd
    assert "libx264" in cmd
    assert "out.mp4" == cmd[-1]

    # 3. demuxer command
    with tempfile.TemporaryDirectory() as td:
        manifest = write_concat_file(["/path/1.mp4", "/path/2.mp4"], Path(td) / "concat.txt")
        assert manifest.exists()
        content = manifest.read_text()
        assert "file '/path/1.mp4'" in content

        demux_cmd = build_demuxer_assembly_command(
            video_manifest_path=manifest,
            output_path=Path(td) / "out.mp4",
        )
        assert "-f" in demux_cmd
        assert "concat" in demux_cmd

    print("Command Builder Verification Passed.\n")


def run_assembler_behavior_tests():
    print("--- Running VideoAssembler Subprocess & Cleanup Verification ---")

    # Create dummy video file
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        v1 = tdp / "v1.mp4"
        v1.write_bytes(b"0" * 500)

        out = tdp / "final.mp4"

        # Mock FFmpeg script that succeeds
        mock_script = tdp / "mock_ffmpeg.py"
        mock_script.write_text(
            "import sys, os, time\n"
            "output_file = sys.argv[-1]\n"
            "with open(output_file, 'wb') as f:\n"
            "    f.write(b'A' * 2000)\n"
            "sys.exit(0)\n"
        )

        assembler = VideoAssembler(ffmpeg_binary=str(mock_script), temp_dir=tdp / "tmp_parent")

        result_path = assembler.assemble(
            video_segments=[v1],
            output_path=out,
            resolution="3840x2160",
        )
        assert result_path.exists()
        assert result_path.stat().st_size == 2000
        print("Successful mock assembly verified.")

        # Test failure scenario: non-zero exit code
        mock_fail_script = tdp / "mock_ffmpeg_fail.py"
        mock_fail_script.write_text(
            "import sys\n"
            "sys.stderr.write('FFmpeg encoder error: invalid codec\\n')\n"
            "sys.exit(1)\n"
        )
        assembler_fail = VideoAssembler(ffmpeg_binary=str(mock_fail_script), temp_dir=tdp / "tmp_parent")

        out_fail = tdp / "final_fail.mp4"
        try:
            assembler_fail.assemble(
                video_segments=[v1],
                output_path=out_fail,
            )
            assert False, "Should have raised AssemblyError"
        except AssemblyError as e:
            print(f"Caught expected AssemblyError on exit code 1: {e}")
            assert "FFmpeg encoder error" in str(e)
            assert not out_fail.exists()
            assert not (tdp / f"{out_fail.name}.tmp_{os.getpid()}").exists()

        # Test failure scenario: timeout
        mock_slow_script = tdp / "mock_ffmpeg_slow.py"
        mock_slow_script.write_text(
            "import time\n"
            "time.sleep(5)\n"
        )
        assembler_slow = VideoAssembler(ffmpeg_binary=str(mock_slow_script), timeout=0.2)
        out_slow = tdp / "final_slow.mp4"
        try:
            assembler_slow.assemble(
                video_segments=[v1],
                output_path=out_slow,
            )
            assert False, "Should have raised timeout AssemblyError"
        except AssemblyError as e:
            print(f"Caught expected AssemblyError on timeout: {e}")
            assert "timed out" in str(e)

        # Test cleanup verification: check no dangling assembly_ directories in tmp_parent
        tmp_parent = tdp / "tmp_parent"
        dangling = list(tmp_parent.glob("assembly_*"))
        print(f"Dangling temp dirs in parent: {dangling}")
        assert len(dangling) == 0

    print("VideoAssembler Subprocess & Cleanup Verification Passed.\n")


def run_node_integration_tests():
    print("--- Running VideoAssemblyNode Integration & Ledger Verification ---")

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        db_path = tdp / "ledger.db"
        ledger = StateLedger(str(db_path))

        run_id = ledger.create_run("two-sum")

        v1 = tdp / "segment_0.mp4"
        v1.write_bytes(b"V" * 500)
        audio = tdp / "narration.wav"
        audio.write_bytes(b"A" * 300)

        # Record animation_generator step
        step_id_anim = ledger.record_step_start(run_id, "animation_generator")
        ledger.record_step_completion(
            step_id_anim,
            output_payload={
                "slug": "two-sum",
                "segments": [
                    {
                        "segment_id": "seg_0",
                        "segment_type": "intro",
                        "start_time": 0.0,
                        "end_time": 5.0,
                        "duration": 5.0,
                        "visual_path": str(v1),
                    }
                ]
            }
        )

        # Record voice_generator step
        step_id_voice = ledger.record_step_start(run_id, "voice_generator")
        ledger.record_step_completion(
            step_id_voice,
            output_payload={
                "audio_path": str(audio),
                "srt_content": "1\n00:00:00,000 --> 00:00:05,000\nHello World\n",
            }
        )

        # Mock FFmpeg script
        mock_script = tdp / "mock_ffmpeg.py"
        mock_script.write_text(
            "import sys\n"
            "out = sys.argv[-1]\n"
            "with open(out, 'wb') as f:\n"
            "    f.write(b'FINAL' * 1000)\n"
            "sys.exit(0)\n"
        )

        node = VideoAssemblyNode(
            ffmpeg_binary=str(mock_script),
            output_dir=tdp / "assembled",
            temp_dir=tdp / "temp",
        )

        assert node.name == "video_assembly"

        payload = node.execute(run_id, ledger)
        print("Node execution payload:", payload)

        assert payload["slug"] == "two-sum"
        assert payload["file_size_bytes"] == 5000
        assert payload["total_duration_seconds"] == 5.0
        assert Path(payload["final_video_path"]).exists()

    print("VideoAssemblyNode Integration Verification Passed.\n")


if __name__ == "__main__":
    run_ast_analysis()
    run_command_builder_tests()
    run_assembler_behavior_tests()
    run_node_integration_tests()
    print("ALL FORENSIC CHECKS PASSED SUCCESSFULLY!")
