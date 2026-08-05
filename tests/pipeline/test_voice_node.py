"""Unit tests for VoiceGeneratorNode in src/pipeline/nodes/voice_generator_node.py.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from src.core.exceptions import PipelineStageError, VoiceGenerationError
from src.core.media.voice import AudioSegment, KokoroVoiceProvider
from src.core.orchestrator.state_ledger import StateLedger
from src.pipeline.nodes.voice_generator_node import VoiceGeneratorNode, format_srt_timestamp


def test_voice_generator_node_name():
    """Verify name property returns 'voice_generator'."""
    node = VoiceGeneratorNode()
    assert node.name == "voice_generator"


def test_voice_generator_node_default_provider():
    """Verify default provider is KokoroVoiceProvider."""
    node = VoiceGeneratorNode()
    assert isinstance(node.provider, KokoroVoiceProvider)


def test_voice_generator_node_missing_ledger():
    """Verify execute raises PipelineStageError when ledger is None."""
    node = VoiceGeneratorNode()
    with pytest.raises(PipelineStageError, match="requires a valid StateLedger instance"):
        node.execute("test-run-id", ledger=None)


def test_voice_generator_node_missing_audio_file(tmp_path):
    """Verify execute raises VoiceGenerationError when audio output file is missing and no script output present."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("two-sum")

    node = VoiceGeneratorNode(output_dir=tmp_path / "data" / "audio" / "two-sum")
    with pytest.raises(VoiceGenerationError, match="TTS audio synthesis failed"):
        node.execute(run_id, ledger=ledger)


def test_voice_generator_node_successful_execution(tmp_path):
    """Verify execute returns payload dictionary when audio output file exists."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("two-sum")

    audio_dir = tmp_path / "data" / "audio" / "two-sum"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_file = audio_dir / "master_audio.wav"
    sub_file = audio_dir / "subtitles.srt"

    audio_file.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00")
    sub_file.write_text("1\n00:00:00,000 --> 00:00:05,000\nHello\n", encoding="utf-8")

    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    assert result["slug"] == "two-sum"
    assert result["audio_path"] == str(audio_file.resolve())
    assert result["subtitle_path"] == str(sub_file.resolve())
    assert "Hello" in result["srt_content"]
    assert result["status"] == "completed"


def test_voice_generator_node_synthesis_with_script_ledger(tmp_path):
    """Verify VoiceGeneratorNode synthesizes audio and subtitles using upstream script_generator output."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("reorder-list")

    # Record script_generator step
    script_payload = {
        "slug": "reorder-list",
        "topic": "Linked List",
        "status": "completed",
        "script": {
            "title": "Reorder List Solution",
            "slug": "reorder-list",
            "topic": "Linked List",
            "total_duration": 20.0,
            "spoken_narration": [
                "Welcome to the Reorder List tutorial.",
                "First, we find the middle of the linked list using slow and fast pointers.",
                "Next, we reverse the second half of the list.",
                "Finally, we merge the two halves in alternating order."
            ],
            "hook": {"narration": "Welcome to the Reorder List tutorial.", "estimated_duration": 5.0},
            "context": {"narration": "First, we find the middle of the linked list using slow and fast pointers.", "estimated_duration": 5.0},
            "solution": {"narration": "Next, we reverse the second half of the list.", "estimated_duration": 5.0},
            "complexity": {"narration": "Finally, we merge the two halves in alternating order.", "estimated_duration": 5.0},
        }
    }
    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, script_payload)

    audio_dir = tmp_path / "data" / "audio" / "reorder-list"
    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    assert result["slug"] == "reorder-list"
    assert result["status"] == "completed"
    assert Path(result["audio_path"]).exists()
    assert Path(result["audio_path"]).stat().st_size > 0
    assert result["duration_seconds"] > 0
    assert Path(result["subtitle_path"]).exists()
    assert "00:00:00,000" in result["srt_content"]
    assert "Reorder List tutorial" in result["srt_content"]


def test_voice_generator_node_provider_error(tmp_path):
    """Verify VoiceGenerationError is raised when TTS provider raises an exception."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("two-sum")
    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {
        "spoken_narration": ["Step 1", "Step 2"]
    })

    failing_provider = MagicMock()
    failing_provider.generate_segment.side_effect = RuntimeError("Synthesis engine error")

    audio_dir = tmp_path / "data" / "audio" / "two-sum"
    node = VoiceGeneratorNode(provider=failing_provider, output_dir=audio_dir)

    with pytest.raises(VoiceGenerationError, match="TTS audio synthesis failed"):
        node.execute(run_id, ledger=ledger)


def test_format_srt_timestamp():
    """Verify formatting of seconds into SRT timestamp string."""
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(5.25) == "00:00:05,250"
    assert format_srt_timestamp(65.123) == "00:01:05,123"


