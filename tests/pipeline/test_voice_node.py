"""Unit tests for VoiceGeneratorNode in src/pipeline/nodes/voice_generator_node.py.
"""

from pathlib import Path
import pytest

from src.core.exceptions import PipelineStageError, VoiceGenerationError
from src.core.orchestrator.state_ledger import StateLedger
from src.pipeline.nodes.voice_generator_node import VoiceGeneratorNode


def test_voice_generator_node_name():
    """Verify name property returns 'voice_generator'."""
    node = VoiceGeneratorNode()
    assert node.name == "voice_generator"


def test_voice_generator_node_missing_ledger():
    """Verify execute raises PipelineStageError when ledger is None."""
    node = VoiceGeneratorNode()
    with pytest.raises(PipelineStageError, match="requires a valid StateLedger instance"):
        node.execute("test-run-id", ledger=None)


def test_voice_generator_node_missing_audio_file(tmp_path):
    """Verify execute raises VoiceGenerationError when audio output file is missing."""
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
