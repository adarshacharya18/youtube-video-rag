"""
End-to-End Pipeline Integration Tests (Phase 14).

Verifies end-to-end execution, node output chaining, state persistence, event emissions,
and operational CLI commands across the 6-stage pipeline.
"""
import sys
import pytest
from pathlib import Path

from unittest.mock import patch

from src.core.events import EventBus, NodeCompleted, NodeFailed, NodeStarted
from src.core.orchestrator.pipeline_runner import PipelineRunner, _default_llm_provider
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.pipeline.nodes import (
    AnimationGeneratorNode,
    IngestionNode,
    PlanNode,
    ScriptGeneratorNode,
    VideoAssemblyNode,
    VoiceGeneratorNode,
)


@pytest.fixture(autouse=True)
def mock_voice_synthesis(tmp_path_factory):
    """Autouse fixture providing mock voice execution and TTS media artifacts for E2E tests."""
    audio_dir = tmp_path_factory.mktemp("e2e_audio")

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

    with patch("src.pipeline.nodes.voice_generator_node.VoiceGeneratorNode.execute", autospec=False, side_effect=mock_voice_execute):
        yield


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
        f.write(b"MOCK_MANIM_VIDEO_SEGMENT_DATA_" * 10)
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


def _build_test_nodes(manim_bin: str, ffmpeg_bin: str):
    """Build production node sequence configured with mock binary paths."""
    return [
        IngestionNode(),
        PlanNode(),
        ScriptGeneratorNode(llm_provider=_default_llm_provider),
        VoiceGeneratorNode(),
        AnimationGeneratorNode(manim_binary=manim_bin),
        VideoAssemblyNode(ffmpeg_binary=ffmpeg_bin),
    ]


def test_pipeline_e2e_full_execution(tmp_path, mock_binaries):
    """Verify full end-to-end execution of the 6-stage pipeline via PipelineRunner."""
    manim_bin, ffmpeg_bin = mock_binaries
    db_path = tmp_path / "e2e_ledger.db"
    events_received = []

    def on_event(event):
        events_received.append(event)

    event_bus = EventBus()
    event_bus.subscribe(NodeStarted, on_event)
    event_bus.subscribe(NodeCompleted, on_event)

    nodes = _build_test_nodes(manim_bin, ffmpeg_bin)
    runner = PipelineRunner(nodes=nodes, db_path=db_path, event_bus=event_bus)
    result = runner.run_problem(slug="two-sum", metadata={"author": "devops"})

    assert result.success is True
    assert result.status == StepStatus.COMPLETED
    assert len(result.completed_steps) == 6
    assert result.completed_steps == [
        "ingest",
        "plan",
        "script_generator",
        "voice_generator",
        "animation_generator",
        "video_assembly",
    ]

    # Verify event bus received 6 NodeStarted and 6 NodeCompleted events
    started_events = [e for e in events_received if isinstance(e, NodeStarted)]
    completed_events = [e for e in events_received if isinstance(e, NodeCompleted)]
    assert len(started_events) == 6
    assert len(completed_events) == 6

    # Verify StateLedger status query
    status_info = runner.get_status("two-sum")
    assert status_info["found"] is True
    assert status_info["status"].lower() == "completed"
    assert status_info["total_nodes"] == 6

    runner.close()


def test_pipeline_e2e_resume_flow(tmp_path, mock_binaries):
    """Verify end-to-end run resumption after partial completion."""
    manim_bin, ffmpeg_bin = mock_binaries
    db_path = tmp_path / "e2e_resume.db"
    ledger = StateLedger(db_path=db_path)
    run_id = ledger.create_run(slug="three-sum")

    # Manually complete first 2 steps
    s1 = ledger.record_step_start(run_id, "ingest")
    ledger.record_step_completion(s1, {"slug": "three-sum", "title": "Three Sum"})
    s2 = ledger.record_step_start(run_id, "plan")
    ledger.record_step_completion(s2, {"topic": "Three Sum", "slug": "three-sum"})

    nodes = _build_test_nodes(manim_bin, ffmpeg_bin)
    runner = PipelineRunner(nodes=nodes, ledger=ledger)
    result = runner.resume_run("three-sum")

    assert result.success is True
    assert result.skipped_steps == ["ingest", "plan"]
    assert set(result.completed_steps) == {
        "ingest",
        "plan",
        "script_generator",
        "voice_generator",
        "animation_generator",
        "video_assembly",
    }
    runner.close()
