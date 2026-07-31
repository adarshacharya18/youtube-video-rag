"""
Unit and component tests for Master Operations CLI (src/cli/ops.py).
"""

import json
from pathlib import Path
from unittest.mock import patch
import pytest

from src.cli.ops import create_parser, main
from src.core.orchestrator.state_ledger import StateLedger, StepStatus


@pytest.fixture(autouse=True)
def mock_renderers(tmp_path_factory):
    """Autouse fixture to mock ManimRenderer.render, VideoAssembler.assemble, and VoiceGeneratorNode.execute for CLI testing."""
    render_dir = tmp_path_factory.mktemp("renders")
    audio_dir = tmp_path_factory.mktemp("audio")

    def mock_manim_render(scene_script, class_name, output_dir, output_filename="scene.mp4", parameters=None):
        out_path = Path(output_dir) / output_filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"MOCK_MANIM_VIDEO_SEGMENT_DATA_" * 10)
        return out_path

    def mock_ffmpeg_assemble(video_segments, audio_path=None, subtitle_path=None, subtitle_text=None, output_path=None, **kwargs):
        out_path = Path(output_path) if output_path else render_dir / "assembled.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"MOCK_ASSEMBLED_4K_VIDEO_STREAM_DATA_" * 10)
        return out_path

    def mock_voice_execute(run_id: str, ledger=None):
        if ledger is None:
            from src.core.exceptions import PipelineStageError
            raise PipelineStageError("Node 'voice_generator' requires a valid StateLedger instance.")
        run_record = ledger.get_run(run_id)
        slug = run_record.slug
        base_dir = audio_dir / slug
        base_dir.mkdir(parents=True, exist_ok=True)
        audio_file = base_dir / "master_audio.wav"
        sub_file = base_dir / "subtitles.srt"
        wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\x3e\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        audio_file.write_bytes(wav_header)
        srt_content = "1\n00:00:00,000 --> 00:00:05,000\nWelcome to our algorithm walkthrough.\n"
        sub_file.write_text(srt_content, encoding="utf-8")
        return {
            "slug": slug,
            "audio_path": str(audio_file.resolve()),
            "subtitle_path": str(sub_file.resolve()),
            "srt_content": srt_content,
            "duration_seconds": 10.0,
            "status": "completed",
        }

    with patch("src.animation.renderer.ManimRenderer.render", side_effect=mock_manim_render), \
         patch("src.assembly.assembler.VideoAssembler.assemble", side_effect=mock_ffmpeg_assemble), \
         patch("src.pipeline.nodes.voice_generator_node.VoiceGeneratorNode.execute", autospec=False, side_effect=mock_voice_execute):
        yield


def parse_json_from_output(text: str) -> dict:
    """Extract JSON object from stdout text, skipping any preceding log prefix lines."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    for idx in range(len(lines)):
        candidate = "\n".join(lines[idx:])
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return json.loads(lines[-1])


def test_cli_parser_creation():
    """Verify create_parser initializes all subcommands."""
    parser = create_parser()
    assert parser.prog == "ops"


def test_cli_run_command_success(tmp_path, capsys):
    """Verify ops run command starts a new run and outputs execution report."""
    db_file = tmp_path / "test_ops.db"
    exit_code = main(["run", "--slug", "two-sum", "--db", str(db_file)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "PIPELINE EXECUTION REPORT: two-sum" in captured.out
    assert "Outcome:        SUCCESS (COMPLETED)" in captured.out


def test_cli_run_command_json_output(tmp_path, capsys):
    """Verify ops run --json command outputs valid JSON payload."""
    db_file = tmp_path / "test_ops_json.db"
    exit_code = main(["run", "--slug", "three-sum", "--json", "--db", str(db_file)])

    assert exit_code == 0
    captured = capsys.readouterr()
    data = parse_json_from_output(captured.out)

    assert data["success"] is True
    assert "run_id" in data
    assert data["status"] == "COMPLETED"
    assert len(data["completed_steps"]) == 6


def test_cli_run_command_missing_slug(capsys):
    """Verify ops run without --slug returns exit code 1."""
    exit_code = main(["run"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: Must specify --slug" in captured.err


def test_cli_status_command(tmp_path, capsys):
    """Verify ops status command queries run details by slug."""
    db_file = tmp_path / "test_status.db"

    # First execute a run
    main(["run", "--slug", "lru-cache", "--db", str(db_file)])
    capsys.readouterr()

    # Query status
    exit_code = main(["status", "--slug", "lru-cache", "--db", str(db_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "PIPELINE RUN STATUS" in captured.out
    assert "Slug:           lru-cache" in captured.out
    assert "Overall Status: COMPLETED" in captured.out


def test_cli_status_command_json(tmp_path, capsys):
    """Verify ops status --json command returns structured JSON."""
    db_file = tmp_path / "test_status_json.db"

    main(["run", "--slug", "valid-palindrome", "--db", str(db_file)])
    capsys.readouterr()

    exit_code = main(["status", "--slug", "valid-palindrome", "--json", "--db", str(db_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    data = parse_json_from_output(captured.out)
    assert data["found"] is True
    assert data["slug"] == "valid-palindrome"
    assert data["status"] == "COMPLETED"


def test_cli_status_non_existent(tmp_path, capsys):
    """Verify ops status for missing run returns exit code 1."""
    db_file = tmp_path / "test_status_missing.db"

    exit_code = main(["status", "--slug", "unknown-slug", "--db", str(db_file)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "No pipeline run found" in captured.err


def test_cli_resume_command(tmp_path, capsys):
    """Verify ops resume command resumes an existing run."""
    db_file = tmp_path / "test_resume.db"

    # Create run first
    main(["run", "--slug", "merge-k-lists", "--db", str(db_file)])
    capsys.readouterr()

    # Resume run
    exit_code = main(["resume", "--slug", "merge-k-lists", "--db", str(db_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "PIPELINE RESUMPTION REPORT: merge-k-lists" in captured.out
    assert "Outcome:        SUCCESS (COMPLETED)" in captured.out


def test_cli_health_command(tmp_path, capsys):
    """Verify ops health command returns system health report."""
    db_file = tmp_path / "test_health.db"

    exit_code = main(["health", "--db", str(db_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "SYSTEM HEALTH DIAGNOSTIC REPORT" in captured.out
    assert "StateLedger Database:  [OK] Connected" in captured.out


def test_cli_health_command_json(tmp_path, capsys):
    """Verify ops health --json outputs structured diagnostic JSON."""
    db_file = tmp_path / "test_health_json.db"

    exit_code = main(["health", "--json", "--db", str(db_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    data = parse_json_from_output(captured.out)
    assert "status" in data
    assert data["database"]["connected"] is True
    assert "storage" in data
    assert "binaries" in data


def test_cli_health_command_json_strict_stdout(tmp_path, capsys):
    """Verify ops health --json outputs strictly valid JSON on stdout without log preambles."""
    db_file = tmp_path / "test_health_strict.db"

    exit_code = main(["health", "--json", "--db", str(db_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    # json.loads directly on captured.out must succeed without stripping prefix lines
    data = json.loads(captured.out.strip())
    assert "status" in data
    assert data["database"]["connected"] is True


def test_cli_benchmark_command(capsys):
    """Verify ops benchmark subcommand."""
    exit_code = main(["benchmark"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[BENCHMARK] Executed." in captured.out


def test_cli_benchmark_json_strict_stdout(capsys):
    """Verify ops benchmark --json outputs strictly valid JSON on stdout."""
    exit_code = main(["benchmark", "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["status"] == "completed"


def test_cli_diagnose_clean_dlq(tmp_path, capsys):
    """Verify ops diagnose reports clean DLQ when missing."""
    dlq_file = tmp_path / "non_existent_dlq.jsonl"
    exit_code = main(["diagnose", "--dlq-path", str(dlq_file)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "DLQ is clean" in captured.out

