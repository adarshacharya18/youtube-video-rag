"""
Unit tests for Voice Core Module (Milestone 1).

Tests src.core.media.voice and src.voice.synthesizer re-exports.
"""

import pytest
import wave
from pathlib import Path
from dataclasses import FrozenInstanceError

from src.core.exceptions import VoiceGenerationError
from src.core.media.voice import (
    AudioSegment,
    VoiceConfig,
    VoiceProviderProtocol,
    KokoroVoiceProvider,
    ManualVoiceProvider,
)
import src.voice.synthesizer as synth_reexport


class TestAudioSegment:
    def test_audio_segment_fields_and_immutability(self):
        segment = AudioSegment(
            file_path="/tmp/audio.wav",
            duration_sec=3.5,
            voice_id="af_sky",
            checksum="abc123hash"
        )
        assert segment.file_path == "/tmp/audio.wav"
        assert segment.duration_sec == 3.5
        assert segment.voice_id == "af_sky"
        assert segment.checksum == "abc123hash"

        with pytest.raises(FrozenInstanceError):
            segment.duration_sec = 4.0  # type: ignore


class TestVoiceConfig:
    def test_voice_config_defaults(self):
        config = VoiceConfig()
        assert config.voice_id == "af_sky"
        assert config.sample_rate == 24000
        assert config.speed == 1.0
        assert config.pitch == 1.0

    def test_voice_config_custom_values(self):
        config = VoiceConfig(speed=1.5, pitch=0.8)
        assert config.speed == 1.5
        assert config.pitch == 0.8
        assert config.voice_id == "af_sky"


class TestKokoroVoiceProvider:
    def test_pronunciation_fixes_defaults(self):
        provider = KokoroVoiceProvider()
        text = "Using Dijkstra algorithm with O(N) space and O(N^2) time complexity."
        fixed = provider._apply_pronunciation_fixes(text)
        assert "dike-struh" in fixed
        assert "O of N" in fixed
        assert "O of N squared" in fixed
        assert "Dijkstra" not in fixed

    def test_pronunciation_fixes_custom_dict(self):
        custom_dict = {"BFS": "breadth first search"}
        provider = KokoroVoiceProvider(pronunciation_dict=custom_dict)
        fixed = provider._apply_pronunciation_fixes("Run BFS traversal")
        assert fixed == "Run breadth first search traversal"

    def test_generate_segment_creates_valid_wav(self, tmp_path):
        provider = KokoroVoiceProvider()
        out_file = tmp_path / "nested" / "output.wav"
        segment = provider.generate_segment(
            text="Testing Dijkstra algorithm.",
            voice_id="af_sky",
            speed=1.0,
            output_path=str(out_file)
        )

        assert Path(segment.file_path).exists()
        assert Path(segment.file_path).stat().st_size > 0
        assert segment.duration_sec > 0
        assert segment.voice_id == "af_sky"
        assert len(segment.checksum) == 64  # SHA-256 hex digest length

        # Verify WAV file attributes
        with wave.open(str(out_file), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 24000

    def test_generate_segment_empty_output_path_raises(self):
        provider = KokoroVoiceProvider()
        with pytest.raises(ValueError, match="output_path must be specified"):
            provider.generate_segment("Hello", "af_sky", output_path="")

    def test_generate_segment_retries_on_failure(self, tmp_path):
        provider = KokoroVoiceProvider()
        # Invalid directory path on unix (directory treated as file or invalid permission)
        invalid_path = "/proc/invalid_path/test.wav"
        with pytest.raises(VoiceGenerationError, match="permanently failed after 3 attempts"):
            provider.generate_segment("Test retry", "af_sky", output_path=invalid_path)

    def test_empty_and_whitespace_input_text(self, tmp_path):
        provider = KokoroVoiceProvider()
        for text_input in ["", "   ", "\n\t  "]:
            out_file = tmp_path / "whitespace.wav"
            segment = provider.generate_segment(
                text=text_input,
                voice_id="af_sky",
                output_path=str(out_file)
            )
            assert Path(segment.file_path).exists()
            assert Path(segment.file_path).stat().st_size > 0
            assert segment.duration_sec >= 1.0
            assert len(segment.checksum) == 64

    def test_long_paragraph_input(self, tmp_path):
        provider = KokoroVoiceProvider()
        long_text = "Word " * 1500  # 1500 words
        out_file = tmp_path / "long_text.wav"
        segment = provider.generate_segment(
            text=long_text,
            voice_id="af_sky",
            output_path=str(out_file)
        )
        assert Path(segment.file_path).exists()
        assert segment.duration_sec > 500  # 1500 words / 2.5 = 600 seconds
        assert Path(segment.file_path).stat().st_size > 1000

    def test_nested_output_directory_creation(self, tmp_path):
        provider = KokoroVoiceProvider()
        nested_file = tmp_path / "data" / "audio" / "test_slug" / "sub_dir" / "level3" / "segment.wav"
        assert not nested_file.parent.exists()
        segment = provider.generate_segment(
            text="Nested directory test.",
            voice_id="af_sky",
            output_path=str(nested_file)
        )
        assert nested_file.exists()
        assert segment.file_path == str(nested_file.resolve())

    def test_proper_file_handle_closure_and_no_resource_leaks(self, tmp_path):
        provider = KokoroVoiceProvider()
        for i in range(25):
            out_file = tmp_path / f"leak_test_{i}.wav"
            segment = provider.generate_segment(
                text=f"Iteration {i}",
                voice_id="af_sky",
                output_path=str(out_file)
            )
            # File handle must be released immediately allowing deletion/unlinking
            out_path = Path(segment.file_path)
            assert out_path.exists()
            out_path.unlink()  # Will raise PermissionError/OSError if file handle is leaked

    def test_extreme_speed_parameters(self, tmp_path):
        provider = KokoroVoiceProvider()
        out_file_zero = tmp_path / "zero_speed.wav"
        segment_zero = provider.generate_segment("Speed test", "af_sky", speed=0.0, output_path=str(out_file_zero))
        assert segment_zero.duration_sec > 0

        out_file_neg = tmp_path / "neg_speed.wav"
        segment_neg = provider.generate_segment("Speed test", "af_sky", speed=-2.0, output_path=str(out_file_neg))
        assert segment_neg.duration_sec > 0

        out_file_fast = tmp_path / "fast_speed.wav"
        segment_fast = provider.generate_segment("Speed test", "af_sky", speed=100.0, output_path=str(out_file_fast))
        assert segment_fast.duration_sec > 0
        assert segment_fast.duration_sec < segment_zero.duration_sec

    def test_cpu_execution_without_cuda(self, tmp_path):
        provider = KokoroVoiceProvider()
        out_file = tmp_path / "cpu_test.wav"
        segment = provider.generate_segment("Pure CPU execution test.", "af_sky", output_path=str(out_file))
        assert Path(segment.file_path).exists()


class TestManualVoiceProvider:
    def test_generate_segment_raises_if_file_missing(self, tmp_path):
        provider = ManualVoiceProvider()
        missing_file = tmp_path / "missing.wav"
        with pytest.raises(FileNotFoundError, match="Manual audio file expected"):
            provider.generate_segment("Test prose", "human", output_path=str(missing_file))

    def test_generate_segment_raises_if_file_is_zero_bytes(self, tmp_path):
        provider = ManualVoiceProvider()
        zero_byte_file = tmp_path / "zero.wav"
        zero_byte_file.touch()  # Creates 0-byte file
        with pytest.raises(FileNotFoundError, match="Manual audio file expected"):
            provider.generate_segment("Test prose", "human", output_path=str(zero_byte_file))

    def test_generate_segment_success_when_file_exists(self, tmp_path):
        provider = ManualVoiceProvider()
        existing_file = tmp_path / "manual.wav"

        # Create dummy WAV file
        kokoro = KokoroVoiceProvider()
        kokoro.generate_segment("Manual test", "human", output_path=str(existing_file))

        segment = provider.generate_segment("Manual test", "human", output_path=str(existing_file))
        assert segment.file_path == str(existing_file.resolve())
        assert segment.duration_sec > 0
        assert segment.checksum != ""


class TestReExports:
    def test_synthesizer_reexports(self):
        assert synth_reexport.AudioSegment is AudioSegment
        assert synth_reexport.VoiceConfig is VoiceConfig
        assert synth_reexport.VoiceProviderProtocol is VoiceProviderProtocol
        assert synth_reexport.KokoroVoiceProvider is KokoroVoiceProvider
        assert synth_reexport.ManualVoiceProvider is ManualVoiceProvider

