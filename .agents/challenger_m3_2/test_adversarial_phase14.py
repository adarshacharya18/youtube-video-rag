"""
Adversarial & Stress Verification Test Suite for Phase 14 (Milestone 3).

Authored by Challenger 2 (.agents/challenger_m3_2/test_adversarial_phase14.py).
Tests adversarial edge cases, partial failure resumption, corrupt state/db handling,
CLI exit code compliance, and system health error detection.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.cli.ops import (
    main,
    cmd_run,
    cmd_status,
    cmd_resume,
    cmd_health,
    cmd_diagnose,
    cmd_report,
    cmd_rollback,
    create_parser,
)
from src.core.events import EventBus
from src.core.exceptions import PipelineError, PipelineStageError
from src.core.orchestrator.pipeline_runner import PipelineRunner, _default_llm_provider
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.pipeline.nodes import (
    IngestionNode,
    PlanNode,
    ScriptGeneratorNode,
    VoiceGeneratorNode,
    AnimationGeneratorNode,
    VideoAssemblyNode,
)


@pytest.fixture
def mock_binaries(tmp_path):
    """Fixture providing mock python scripts for manim and ffmpeg binaries."""
    manim_script = tmp_path / "mock_manim.py"
    manim_script.write_text(
        """import sys, os
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
        f.write(b"MOCK_MANIM_DATA_" * 10)
sys.exit(0)
""",
        encoding="utf-8",
    )

    ffmpeg_script = tmp_path / "mock_ffmpeg.py"
    ffmpeg_script.write_text(
        """import sys, os
out_file = sys.argv[-1]
os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
with open(out_file, "wb") as f:
    f.write(b"MOCK_ASSEMBLED_4K_VIDEO_STREAM_DATA_" * 10)
sys.exit(0)
""",
        encoding="utf-8",
    )

    return str(manim_script), str(ffmpeg_script)


@pytest.fixture(autouse=True)
def mock_voice_synthesis(tmp_path_factory):
    """Mock VoiceGeneratorNode.execute to create valid dummy audio files."""
    audio_dir = tmp_path_factory.mktemp("adv_audio")

    def mock_voice_execute(run_id: str, ledger=None):
        if ledger is None:
            raise PipelineStageError("Node requires ledger")
        run_record = ledger.get_run(run_id)
        slug = run_record.slug
        base_dir = audio_dir / slug
        base_dir.mkdir(parents=True, exist_ok=True)
        audio_file = base_dir / "master_audio.wav"
        sub_file = base_dir / "subtitles.srt"
        wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\x3e\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        audio_file.write_bytes(wav_header)
        srt_content = "1\n00:00:00,000 --> 00:00:05,000\nTest Subtitle\n"
        sub_file.write_text(srt_content, encoding="utf-8")
        return {
            "slug": slug,
            "audio_path": str(audio_file.resolve()),
            "subtitle_path": str(sub_file.resolve()),
            "srt_content": srt_content,
            "duration_seconds": 5.0,
            "status": "completed",
        }

    with patch("src.pipeline.nodes.voice_generator_node.VoiceGeneratorNode.execute", side_effect=mock_voice_execute):
        yield


def _extract_json_from_output(output_text: str) -> dict:
    """Helper to extract JSON object block from CLI output that may contain log lines."""
    lines = output_text.strip().splitlines()
    json_lines = []
    in_json = False
    for line in lines:
        if line.strip().startswith("{"):
            in_json = True
        if in_json:
            json_lines.append(line)
    if not json_lines:
        raise ValueError(f"No JSON block found in output: {output_text}")
    return json.loads("\n".join(json_lines))


# ---------------------------------------------------------------------------
# 1. Invalid CLI Commands & Missing Arguments
# ---------------------------------------------------------------------------

def test_cli_invalid_subcommand():
    """Verify that an unknown subcommand returns exit code 2."""
    ret = main(["non_existent_subcommand"])
    assert ret != 0
    assert ret == 2


def test_cli_missing_required_flags():
    """Verify graceful failure (exit code 1) when required CLI flags are missing."""
    # cmd_run without --slug
    ret_run = main(["run"])
    assert ret_run == 1

    # cmd_status without --run-id or --slug
    ret_status = main(["status"])
    assert ret_status == 1

    # cmd_resume without --run-id or --slug
    ret_resume = main(["resume"])
    assert ret_resume == 1

    # cmd_rollback without --file
    ret_rollback = main(["rollback"])
    assert ret_rollback == 1

    # cmd_rollback with non-existent backup file
    ret_rollback_file = main(["rollback", "--file", "/tmp/non_existent_backup_file_999.sqlite"])
    assert ret_rollback_file == 1


def test_cli_status_nonexistent_query(tmp_path):
    """Verify status query for unknown run_id or slug returns exit code 1."""
    db_path = str(tmp_path / "empty_ledger.db")
    ledger = StateLedger(db_path)
    ledger.close()

    ret = main(["status", "--slug", "unknown-slug-12345", "--db", db_path])
    assert ret == 1

    ret_json = main(["status", "--run-id", "run_fake999", "--db", db_path, "--json"])
    assert ret_json == 1


# ---------------------------------------------------------------------------
# 2. Pipeline Resumption on Partial Failure
# ---------------------------------------------------------------------------

def test_pipeline_partial_failure_and_resume(tmp_path, mock_binaries):
    """
    Simulate a pipeline execution that fails at step 3 (ScriptGeneratorNode).
    Verify state ledger marks step and run as FAILED.
    Then resume the pipeline with a fixed step 3, verifying steps 1 & 2 are skipped
    and steps 3-6 complete successfully.
    """
    manim_bin, ffmpeg_bin = mock_binaries
    db_path = tmp_path / "partial_failure.db"

    attempts = {"count": 0}

    def failing_llm_provider(prompt: str) -> dict:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("LLM API connection timed out during generation")
        return _default_llm_provider(prompt)

    nodes = [
        IngestionNode(),
        PlanNode(),
        ScriptGeneratorNode(llm_provider=failing_llm_provider),
        VoiceGeneratorNode(),
        AnimationGeneratorNode(manim_binary=manim_bin),
        VideoAssemblyNode(ffmpeg_binary=ffmpeg_bin),
    ]

    runner = PipelineRunner(nodes=nodes, db_path=db_path)

    # 1st Run: Should fail at script_generator
    result1 = runner.run_problem(slug="two-sum-fail")
    assert result1.success is False
    assert result1.failed_step == "script_generator"
    assert "LLM API connection timed out" in result1.error
    assert result1.completed_steps == ["ingest", "plan"]

    # Verify StateLedger recorded run as FAILED
    status_info1 = runner.get_status("two-sum-fail")
    assert status_info1["found"] is True
    assert status_info1["status"].upper() == "FAILED"

    runner.close()

    # 2nd Run: Resume the failed pipeline (attempts["count"] is now 1, so 2nd call will succeed)
    runner2 = PipelineRunner(nodes=nodes, db_path=db_path)
    result2 = runner2.resume_run("two-sum-fail")

    assert result2.success is True
    assert result2.skipped_steps == ["ingest", "plan"]
    assert "script_generator" in result2.completed_steps
    assert "video_assembly" in result2.completed_steps
    assert result2.status == StepStatus.COMPLETED

    status_info2 = runner2.get_status("two-sum-fail")
    assert status_info2["status"].upper() == "COMPLETED"
    assert len(status_info2["completed_steps"]) == 6

    runner2.close()


# ---------------------------------------------------------------------------
# 3. Corrupt State Ledger & Corrupt DB Handling
# ---------------------------------------------------------------------------

def test_corrupt_database_file_handling(tmp_path):
    """
    Verify that providing a corrupt non-SQLite file as DB path causes CLI
    and PipelineRunner to return error status (exit code 1) gracefully without crashing.
    """
    corrupt_db = tmp_path / "corrupt.db"
    corrupt_db.write_bytes(b"THIS IS NOT A VALID SQLITE DATABASE FILE HEADER!!!")

    # CLI health command on corrupt DB
    ret_health = main(["health", "--db", str(corrupt_db)])
    assert ret_health == 1

    # CLI run command on corrupt DB
    ret_run = main(["run", "--slug", "two-sum", "--db", str(corrupt_db)])
    assert ret_run == 1

    # CLI status command on corrupt DB
    ret_status = main(["status", "--slug", "two-sum", "--db", str(corrupt_db)])
    assert ret_status == 1

    # CLI resume command on corrupt DB
    ret_resume = main(["resume", "--slug", "two-sum", "--db", str(corrupt_db)])
    assert ret_resume == 1


def test_corrupt_json_payload_in_ledger(tmp_path):
    """
    Adversarial injection: corrupt json string directly inserted into step_executions table.
    Verify that StateLedger catches JSONDecodeError and wraps it in a clean PipelineError.
    """
    db_path = tmp_path / "corrupt_json.db"
    ledger = StateLedger(db_path=db_path)
    run_id = ledger.create_run(slug="corrupt-json-test")
    step_id = ledger.record_step_start(run_id, "ingest")

    # Manually overwrite output_payload in SQLite with malformed JSON
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE step_executions SET status = 'COMPLETED', output_payload = '{INVALID_JSON...' WHERE step_execution_id = ?",
        (step_id,),
    )
    conn.commit()
    conn.close()

    # Querying completed steps will trigger json.loads on output_payload and wrap in PipelineError
    with pytest.raises(PipelineError) as exc_info:
        ledger.get_completed_steps(run_id)
    
    assert "Failed to get completed steps" in str(exc_info.value)
    ledger.close()


# ---------------------------------------------------------------------------
# 4. System Health Check Diagnostics Error Detection
# ---------------------------------------------------------------------------

def test_health_check_diagnostics(tmp_path):
    """Verify cmd_health returns exit status 0 for valid DB and 1 for DB failure."""
    valid_db = str(tmp_path / "valid_health.db")

    ret_valid = main(["health", "--db", valid_db])
    assert ret_valid == 0

    invalid_db = "/invalid_directory_path_9999/cannot_create.db"
    ret_invalid = main(["health", "--db", invalid_db])
    assert ret_invalid == 1


def test_health_check_json_output(tmp_path, capsys):
    """Verify cmd_health --json formats payload containing system diagnostics."""
    db_path = str(tmp_path / "health_json.db")
    ret = main(["health", "--db", db_path, "--json"])
    assert ret == 0

    captured = capsys.readouterr()
    data = _extract_json_from_output(captured.out)
    assert "status" in data
    assert "database" in data
    assert data["database"]["connected"] is True
    assert "binaries" in data
    assert "storage" in data
    assert "environment" in data


# ---------------------------------------------------------------------------
# 5. CLI JSON Mode Output Formatting
# ---------------------------------------------------------------------------

def test_cli_run_json_output(tmp_path, mock_binaries, capsys):
    """Verify ops run --json executes pipeline and formats JSON report."""
    manim_bin, ffmpeg_bin = mock_binaries
    db_path = tmp_path / "cli_json.db"

    nodes = [
        IngestionNode(),
        PlanNode(),
        ScriptGeneratorNode(llm_provider=_default_llm_provider),
        VoiceGeneratorNode(),
        AnimationGeneratorNode(manim_binary=manim_bin),
        VideoAssemblyNode(ffmpeg_binary=ffmpeg_bin),
    ]

    with patch("src.cli.ops.PipelineRunner") as mock_runner_cls:
        instance = PipelineRunner(nodes=nodes, db_path=db_path)
        mock_runner_cls.return_value = instance

        ret = main(["run", "--slug", "two-sum-json", "--db", str(db_path), "--json"])
        assert ret == 0

    captured = capsys.readouterr()
    json_out = _extract_json_from_output(captured.out)
    assert json_out["success"] is True
    assert json_out["status"].upper() == "COMPLETED"
    assert len(json_out["completed_steps"]) == 6


# ---------------------------------------------------------------------------
# 6. Advanced Utility Commands: Diagnose, Benchmark, Report, Rollback
# ---------------------------------------------------------------------------

def test_cmd_diagnose_dlq(tmp_path, capsys):
    """Verify cmd_diagnose parses JSONL dead letter queue entries correctly."""
    # Non-existent DLQ file
    ret_clean = main(["diagnose", "--dlq-path", str(tmp_path / "missing.jsonl")])
    assert ret_clean == 0

    # Valid DLQ JSONL file
    dlq_file = tmp_path / "dlq.jsonl"
    dlq_file.write_text(
        json.dumps({
            "run_id": "run_failed_123",
            "failed_step": "animation_generator",
            "error_message": "Manim Out of Memory",
            "traceback": "Traceback (most recent call last):\n  File 'main.py', line 1, in <module>\nMemoryError",
        }) + "\n",
        encoding="utf-8",
    )

    ret_diag = main(["diagnose", "--dlq-path", str(dlq_file)])
    assert ret_diag == 0

    captured = capsys.readouterr()
    assert "run_failed_123" in captured.out
    assert "animation_generator" in captured.out
    assert "Manim Out of Memory" in captured.out


def test_cmd_benchmark_and_report(tmp_path):
    """Verify cmd_benchmark and cmd_report execute successfully."""
    ret_bench = main(["benchmark", "--json"])
    assert ret_bench == 0

    report_path = tmp_path / "test_report.md"
    ret_rep = main(["report", "--output", str(report_path)])
    assert ret_rep == 0
    assert report_path.exists()
    assert "# Pipeline Batch Execution Metrics Report" in report_path.read_text(encoding="utf-8")


def test_cmd_rollback_success(tmp_path):
    """Verify cmd_rollback successfully restores target database from backup file."""
    backup_db = tmp_path / "backup.sqlite"
    target_db = tmp_path / "target.db"

    # Create backup database with sample table
    conn = sqlite3.connect(str(backup_db))
    conn.execute("CREATE TABLE test_table (id INT);")
    conn.commit()
    conn.close()

    ret = main(["rollback", "--file", str(backup_db), "--db", str(target_db)])
    assert ret == 0

    # Verify target DB now has test_table
    conn_t = sqlite3.connect(str(target_db))
    cursor = conn_t.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table';")
    assert cursor.fetchone() is not None
    conn_t.close()
