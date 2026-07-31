"""
Unit and component tests for PipelineRunner in src/core/orchestrator/pipeline_runner.py.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
import pytest

from src.core.events import EventBus, NodeCompleted, NodeFailed, NodeStarted
from src.core.exceptions import PipelineError
from src.core.orchestrator.pipeline_runner import PipelineRunner
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow import Node


@pytest.fixture(autouse=True)
def mock_renderers(tmp_path_factory):
    """Autouse fixture to mock ManimRenderer.render, VideoAssembler.assemble, and VoiceGeneratorNode.execute for component testing."""
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


class MockFailingStepNode(Node):
    """Mock node that fails on the first execution attempt and succeeds thereafter."""

    def __init__(self, fail_on_first_try: bool = True):
        self.fail_on_first_try = fail_on_first_try
        self.call_count = 0

    @property
    def name(self) -> str:
        return "voice_generator"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        self.call_count += 1
        if self.fail_on_first_try and self.call_count == 1:
            raise RuntimeError("Simulated TTS synthesis failure")
        return {
            "slug": "test-slug",
            "audio_path": "/tmp/test.wav",
            "subtitle_path": "/tmp/test.srt",
            "status": "completed",
        }


def test_pipeline_runner_default_initialization():
    """Verify default node sequence and dependencies in PipelineRunner."""
    ledger = StateLedger(":memory:")
    runner = PipelineRunner(ledger=ledger)

    assert len(runner.nodes) == 6
    node_names = [n.name for n in runner.nodes]
    assert node_names == [
        "ingest",
        "plan",
        "script_generator",
        "voice_generator",
        "animation_generator",
        "video_assembly",
    ]


def test_pipeline_runner_successful_run_problem():
    """Verify successful end-to-end execution of run_problem."""
    ledger = StateLedger(":memory:")
    runner = PipelineRunner(ledger=ledger)

    result = runner.run_problem(slug="two-sum", metadata={"topic": "Arrays"})

    assert result.success is True
    assert result.status == StepStatus.COMPLETED
    assert result.completed_steps == [
        "ingest",
        "plan",
        "script_generator",
        "voice_generator",
        "animation_generator",
        "video_assembly",
    ]
    assert result.skipped_steps == []


def test_pipeline_runner_resumption_from_checkpoint():
    """Verify crash resumption from StateLedger checkpoint skipping completed steps."""
    ledger = StateLedger(":memory:")
    failing_tts = MockFailingStepNode(fail_on_first_try=True)

    default_runner = PipelineRunner(ledger=ledger)
    nodes = list(default_runner.nodes)
    nodes[3] = failing_tts  # Replace voice_generator with failing node

    runner = PipelineRunner(nodes=nodes, ledger=ledger)

    # First attempt: fails at step 4 (voice_generator)
    res1 = runner.run_problem("binary-search")
    assert res1.success is False
    assert res1.failed_step == "voice_generator"
    assert res1.completed_steps == ["ingest", "plan", "script_generator"]

    # Resume attempt: re-uses same ledger run_id, voice_generator now succeeds
    res2 = runner.resume_run("binary-search")
    assert res2.success is True
    assert res2.completed_steps == [
        "ingest",
        "plan",
        "script_generator",
        "voice_generator",
        "animation_generator",
        "video_assembly",
    ]
    assert res2.skipped_steps == ["ingest", "plan", "script_generator"]


def test_pipeline_runner_get_status():
    """Verify get_status returns detailed run status and step details."""
    ledger = StateLedger(":memory:")
    runner = PipelineRunner(ledger=ledger)

    res = runner.run_problem("lru-cache")
    assert res.success is True

    status_info = runner.get_status(res.run_id)
    assert status_info["found"] is True
    assert status_info["slug"] == "lru-cache"
    assert status_info["status"] == "COMPLETED"
    assert len(status_info["completed_steps"]) == 6
    assert status_info["total_nodes"] == 6

    # Query by slug
    slug_status = runner.get_status("lru-cache")
    assert slug_status["found"] is True
    assert slug_status["run_id"] == res.run_id

    # Non-existent query
    missing = runner.get_status("non-existent-slug")
    assert missing["found"] is False


def test_pipeline_runner_event_bus_subscription():
    """Verify subscribe_event registers event listeners on EventBus."""
    ledger = StateLedger(":memory:")
    event_bus = EventBus()
    runner = PipelineRunner(ledger=ledger, event_bus=event_bus)

    started_listener = MagicMock()
    completed_listener = MagicMock()

    runner.subscribe_event(NodeStarted, started_listener)
    runner.subscribe_event(NodeCompleted, completed_listener)

    result = runner.run_problem("reverse-linked-list")
    assert result.success is True

    assert started_listener.call_count == 6
    assert completed_listener.call_count == 6


def test_pipeline_runner_resume_non_existent_raises():
    """Verify resume_run raises PipelineError when given a non-existent run_id or slug."""
    ledger = StateLedger(":memory:")
    runner = PipelineRunner(ledger=ledger)

    with pytest.raises(PipelineError, match="Cannot resume"):
        runner.resume_run("invalid-run-id-999")
