"""Adversarial stress test suite for VoiceGeneratorNode.

Tests edge cases, invalid payloads, SRT accuracy, WAV header validity,
exception wrapping, and hardware handling.
"""

import os
import wave
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.exceptions import PipelineStageError, VoiceGenerationError
from src.core.media.voice import AudioSegment, KokoroVoiceProvider
from src.core.orchestrator.state_ledger import StateLedger
from src.models.script import YouTubeScript, HookSection, ContextSection, SolutionSection, ComplexitySection
from src.pipeline.nodes.voice_generator_node import VoiceGeneratorNode, format_srt_timestamp


# ============================================================================
# Category A: Script Payload Stress Tests & Edge Cases
# ============================================================================

def test_script_payload_youtube_script_pydantic_instance(tmp_path):
    """Verify script payload containing a YouTubeScript Pydantic model instance."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("pydantic-script")

    script_model = YouTubeScript(
        topic="Testing",
        slug="pydantic-script",
        total_duration=15.0,
        spoken_narration=["Line one of narration.", "Line two of narration."],
        hook=HookSection(narration="Line one of narration.", estimated_duration=5.0),
        context=ContextSection(narration="Line two of narration.", estimated_duration=4.0),
        solution=SolutionSection(narration="Solution line.", estimated_duration=4.0),
        complexity=ComplexitySection(narration="Complexity line.", estimated_duration=2.0)
    )

    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {"script": script_model.model_dump()})

    audio_dir = tmp_path / "audio" / "pydantic-script"
    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    assert result["status"] == "completed"
    assert "Line one of narration." in result["srt_content"]
    assert "Line two of narration." in result["srt_content"]


def test_script_payload_dict_sections_fallback_parsing(tmp_path):
    """Verify script payload dict with section objects (hook, context, etc.) when model_validate fails."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("dict-sections")

    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {
        "script": {
            "invalid_field": 123,  # will cause YouTubeScript.model_validate to fail
            "hook": {"narration": "Hook narration line."},
            "context": {"narration": "Context narration line."},
            "solution": {"narration": "Solution narration line."},
            "complexity": {"narration": "Complexity narration line."}
        }
    })

    audio_dir = tmp_path / "audio" / "dict-sections"
    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    assert result["status"] == "completed"
    assert "Hook narration line." in result["srt_content"]
    assert "Complexity narration line." in result["srt_content"]


def test_script_payload_malformed_dict_sections(tmp_path):
    """Verify behavior when section dicts are malformed (non-string narration or non-dict sections)."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("malformed-sections")

    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {
        "script": {
            "hook": "not a dict",
            "context": {"narration": 99999},  # not a string
            "solution": {"other_key": "no narration key"},
            "complexity": {"narration": "   Valid fallback complexity   "}
        }
    })

    audio_dir = tmp_path / "audio" / "malformed-sections"
    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    assert result["status"] == "completed"
    assert "Valid fallback complexity" in result["srt_content"]


def test_script_payload_spoken_narration_list_with_mixed_types(tmp_path):
    """Verify handling when spoken_narration list contains non-string types and empty strings."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("mixed-types")

    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {
        "spoken_narration": [100, None, "Valid narration item", "", "   ", True]
    })

    audio_dir = tmp_path / "audio" / "mixed-types"
    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    assert result["status"] == "completed"
    assert "Valid narration item" in result["srt_content"]
    assert "100" in result["srt_content"]
    assert "True" in result["srt_content"]


def test_script_payload_whitespace_only_triggers_fallback(tmp_path):
    """Verify whitespace-only narration triggers fallback narration synthesis."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("whitespace-fallback")

    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {
        "spoken_narration": ["   ", "\t\n", ""]
    })

    audio_dir = tmp_path / "audio" / "whitespace-fallback"
    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    assert result["status"] == "completed"
    assert "Welcome to the video for whitespace-fallback." in result["srt_content"]


def test_script_payload_special_unicode_and_jargon(tmp_path):
    """Verify TTS synthesis handles special characters, unicode, DSA math notation, and Dijkstra jargon."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("unicode-dsa")

    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {
        "spoken_narration": [
            "Dijkstra algorithm takes O(N) or O(N^2) time complexity! 🚀",
            "Special characters & formatting: <code_block> x = y & 5; </code_block>",
            "Unicode characters: alpha α, beta β, gamma γ."
        ]
    })

    audio_dir = tmp_path / "audio" / "unicode-dsa"
    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    assert result["status"] == "completed"
    assert Path(result["audio_path"]).exists()
    assert Path(result["audio_path"]).stat().st_size > 0
    assert "Dijkstra algorithm" in result["srt_content"]


def test_script_payload_extremely_long_text(tmp_path):
    """Verify performance and audio output for a large script payload (5,000 words)."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("long-script")

    long_paragraph = "This is sentence " + " ".join([f"number {i} with some algorithm text." for i in range(500)])
    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {
        "spoken_narration": [long_paragraph, "Final concluding sentence."]
    })

    audio_dir = tmp_path / "audio" / "long-script"
    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    assert result["status"] == "completed"
    assert result["duration_seconds"] > 10.0
    assert Path(result["audio_path"]).stat().st_size > 10000


# ============================================================================
# Category B: Master Audio WAV Creation & Integrity Tests
# ============================================================================

def test_wav_header_integrity(tmp_path):
    """Verify that generated master_audio.wav is a valid 16-bit PCM WAV at 24000 Hz, mono."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("wav-header-test")

    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {
        "spoken_narration": ["Testing WAV file header compliance and valid sample rates."]
    })

    audio_dir = tmp_path / "audio" / "wav-header-test"
    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    wav_path = Path(result["audio_path"])
    assert wav_path.exists()

    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == 1  # Mono
        assert wf.getsampwidth() == 2  # 16-bit PCM (2 bytes/sample)
        assert wf.getframerate() == 24000  # 24kHz
        frames = wf.getnframes()
        assert frames > 0
        calculated_duration = frames / 24000.0
        assert abs(calculated_duration - result["duration_seconds"]) < 0.1


def test_custom_output_dir_creation(tmp_path):
    """Verify output directory creation when path has nested non-existent folders."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("nested-dir")

    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {"spoken_narration": ["Test nested output directory creation."]})

    nested_dir = tmp_path / "deep" / "nested" / "audio" / "dir"
    node = VoiceGeneratorNode(output_dir=nested_dir)
    result = node.execute(run_id, ledger=ledger)

    assert nested_dir.exists()
    assert (nested_dir / "master_audio.wav").exists()
    assert (nested_dir / "subtitles.srt").exists()


# ============================================================================
# Category C: Subtitle SRT Formatting & Timestamp Accuracy Tests
# ============================================================================

def test_srt_timestamp_continuity_and_format(tmp_path):
    """Verify SRT timestamps start at 00:00:00,000, are strictly monotonic, and cover total duration."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("srt-continuity")

    segments = [
        "First segment of the speech.",
        "Second segment explaining the algorithm step by step.",
        "Third segment covering time and space complexity.",
        "Final conclusion segment."
    ]

    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {"spoken_narration": segments})

    audio_dir = tmp_path / "audio" / "srt-continuity"
    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    srt_lines = result["srt_content"].strip().split("\n\n")
    assert len(srt_lines) == len(segments)

    prev_end_ms = 0
    for idx, block in enumerate(srt_lines, start=1):
        lines = block.split("\n")
        assert lines[0] == str(idx)
        time_range = lines[1]
        assert " --> " in time_range
        start_str, end_str = time_range.split(" --> ")

        # Parse start timestamp
        h, m, s_ms = start_str.split(":")
        s, ms = s_ms.split(",")
        start_ms = (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)

        # Parse end timestamp
        h, m, s_ms = end_str.split(":")
        s, ms = s_ms.split(",")
        end_ms = (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)

        if idx == 1:
            assert start_ms == 0
        else:
            assert start_ms == prev_end_ms

        assert end_ms > start_ms
        prev_end_ms = end_ms


def test_format_srt_timestamp_boundary_values():
    """Verify format_srt_timestamp helper on edge case durations."""
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(-10.5) == "00:00:00,000"  # Clamped to 0
    assert format_srt_timestamp(59.999) == "00:00:59,999"
    assert format_srt_timestamp(60.0) == "00:01:00,000"
    assert format_srt_timestamp(3599.999) == "00:59:59,999"
    assert format_srt_timestamp(3600.0) == "01:00:00,000"
    assert format_srt_timestamp(3661.123) == "01:01:01,123"
    # Rounding edge case when ms round up to 1000
    assert format_srt_timestamp(0.9999) == "00:00:01,000"


# ============================================================================
# Category D: Exception & Failure Mode Stress Tests
# ============================================================================

def test_missing_ledger_raises_pipeline_stage_error():
    """Verify executing node without StateLedger raises PipelineStageError."""
    node = VoiceGeneratorNode()
    with pytest.raises(PipelineStageError, match="requires a valid StateLedger instance"):
        node.execute("run-123", ledger=None)


def test_missing_audio_and_no_script_raises_voice_generation_error(tmp_path):
    """Verify VoiceGenerationError when audio missing and script_generator not completed."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("no-script-run")

    audio_dir = tmp_path / "audio" / "no-script-run"
    node = VoiceGeneratorNode(output_dir=audio_dir)

    with pytest.raises(VoiceGenerationError, match="master audio file was not found"):
        node.execute(run_id, ledger=ledger)


def test_provider_returns_zero_byte_file_raises_error(tmp_path):
    """Verify VoiceGenerationError raised if provider writes a 0-byte WAV file."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("zero-byte-run")

    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {"spoken_narration": ["Test 0 byte output"]})

    audio_dir = tmp_path / "audio" / "zero-byte-run"

    # Mock provider that writes 0 bytes
    failing_provider = MagicMock()
    def write_zero_bytes(text, voice_id, speed, output_path):
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        return AudioSegment(file_path=str(p), duration_sec=0.0, voice_id=voice_id, checksum="")

    failing_provider.generate_segment.side_effect = write_zero_bytes

    node = VoiceGeneratorNode(provider=failing_provider, output_dir=audio_dir)
    with pytest.raises(VoiceGenerationError, match="zero-byte"):
        node.execute(run_id, ledger=ledger)


def test_provider_unexpected_exception_wrapped_in_voice_generation_error(tmp_path):
    """Verify any unexpected provider exception is caught and wrapped in VoiceGenerationError."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("exception-wrap-run")

    step_id = ledger.record_step_start(run_id, "script_generator")
    ledger.record_step_completion(step_id, {"spoken_narration": ["Unexpected failure test"]})

    audio_dir = tmp_path / "audio" / "exception-wrap-run"

    failing_provider = MagicMock()
    failing_provider.generate_segment.side_effect = MemoryError("Out of memory during synthesis")

    node = VoiceGeneratorNode(provider=failing_provider, output_dir=audio_dir)
    with pytest.raises(VoiceGenerationError, match="TTS audio synthesis failed"):
        node.execute(run_id, ledger=ledger)


def test_existing_audio_file_reuse_when_no_script_output(tmp_path):
    """Verify existing master_audio.wav is preserved when no script_generator output is in ledger."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("existing-file-run")

    audio_dir = tmp_path / "audio" / "existing-file-run"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_file = audio_dir / "master_audio.wav"
    audio_file.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00")

    node = VoiceGeneratorNode(output_dir=audio_dir)
    result = node.execute(run_id, ledger=ledger)

    assert result["status"] == "completed"
    assert result["audio_path"] == str(audio_file.resolve())
