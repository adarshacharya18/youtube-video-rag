"""
Adversarial Stress Test Suite for Voice Production Subsystem (Phase 13 / Milestone 1).

Tests src/core/media/voice.py and src/voice/synthesizer.py against edge cases,
pronunciation boundary conditions, hardware retry scenarios, audio formatting,
and exception handling.
"""

import hashlib
import math
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dataclasses import FrozenInstanceError

from src.core.exceptions import VoiceGenerationError
from src.core.media.voice import (
    AudioSegment,
    VoiceConfig,
    VoiceProviderProtocol,
    KokoroVoiceProvider,
    ManualVoiceProvider,
    _calculate_audio_duration,
    _compute_checksum,
)
import src.voice.synthesizer as synth_reexport


class TestAdversarialPronunciation:
    """Stress tests for pronunciation dictionary replacement."""

    def test_complex_technical_string_dijkstra_and_complexity(self):
        provider = KokoroVoiceProvider()
        text = "O(N log N) using Dijkstra's algorithm"
        fixed = provider._apply_pronunciation_fixes(text)
        
        # Verify Dijkstra's -> dike-struh's
        assert "dike-struh's" in fixed
        assert "Dijkstra" not in fixed

    def test_pronunciation_dict_case_sensitivity(self):
        """Document case sensitivity behavior of replacement dict."""
        provider = KokoroVoiceProvider()
        text = "dijkstra algorithm with O(N) complexity"
        fixed = provider._apply_pronunciation_fixes(text)
        
        # 'dijkstra' (lowercase) is NOT replaced unless specified in dict
        assert "dijkstra" in fixed
        # 'O(N)' is replaced
        assert "O of N" in fixed

    def test_pronunciation_with_custom_dictionary_expansion(self):
        custom_dict = {
            "Dijkstra": "dike-struh",
            "O(N)": "O of N",
            "O(N log N)": "O of N log N",
            "O(N^2)": "O of N squared",
        }
        provider = KokoroVoiceProvider(pronunciation_dict=custom_dict)
        text = "O(N log N) using Dijkstra's algorithm"
        fixed = provider._apply_pronunciation_fixes(text)
        
        assert fixed == "O of N log N using dike-struh's algorithm"

    def test_pronunciation_fixes_empty_and_whitespace(self):
        provider = KokoroVoiceProvider()
        assert provider._apply_pronunciation_fixes("") == ""
        assert provider._apply_pronunciation_fixes("   ") == "   "


class TestAdversarialHardwareRetry:
    """Stress tests for hardware exception retry behavior in KokoroVoiceProvider."""

    def test_retry_succeeds_on_second_attempt(self, tmp_path):
        provider = KokoroVoiceProvider()
        out_file = tmp_path / "retry_success.wav"
        
        call_count = 0
        original_synthesize = provider._synthesize_pcm_wave

        def mock_synthesize(text, speed, output_path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated GPU hardware OOM / transient error")
            return original_synthesize(text, speed, output_path)

        with patch.object(provider, "_synthesize_pcm_wave", side_effect=mock_synthesize):
            segment = provider.generate_segment("Test retry recovery", "af_sky", output_path=str(out_file))

        assert call_count == 2
        assert Path(segment.file_path).exists()
        assert segment.duration_sec > 0

    def test_retry_fails_persistently_raises_voice_generation_error(self, tmp_path):
        provider = KokoroVoiceProvider()
        out_file = tmp_path / "retry_fail.wav"

        call_count = 0

        def mock_synthesize_fail(text, speed, output_path):
            nonlocal call_count
            call_count += 1
            raise RuntimeError(f"Persistent hardware failure #{call_count}")

        with patch.object(provider, "_synthesize_pcm_wave", side_effect=mock_synthesize_fail):
            with pytest.raises(VoiceGenerationError) as exc_info:
                provider.generate_segment("Test retry failure", "af_sky", output_path=str(out_file))

        assert call_count == 3
        assert "Voice generation permanently failed after 3 attempts" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert "Persistent hardware failure #3" in str(exc_info.value.__cause__)

    def test_retry_triggers_on_zero_byte_file_creation(self, tmp_path):
        provider = KokoroVoiceProvider()
        out_file = tmp_path / "zero_byte.wav"

        call_count = 0

        def mock_synthesize_zero_byte(text, speed, output_path):
            nonlocal call_count
            call_count += 1
            # Create a zero-byte file
            Path(output_path).touch()
            return 0.0

        with patch.object(provider, "_synthesize_pcm_wave", side_effect=mock_synthesize_zero_byte):
            with pytest.raises(VoiceGenerationError) as exc_info:
                provider.generate_segment("Zero byte test", "af_sky", output_path=str(out_file))

        assert call_count == 3
        assert "Voice generation permanently failed after 3 attempts" in str(exc_info.value)


class TestAudioStructureAndPCM:
    """Stress tests for audio PCM structure, rate, duration scaling, and checksums."""

    def test_pcm_wav_header_and_specifications(self, tmp_path):
        provider = KokoroVoiceProvider()
        out_file = tmp_path / "spec_test.wav"
        segment = provider.generate_segment("Valid PCM WAV synthesis check.", "af_sky", speed=1.0, output_path=str(out_file))

        assert Path(out_file).exists()
        file_size = Path(out_file).stat().st_size
        assert file_size > 44  # Valid WAV header is 44 bytes

        with wave.open(str(out_file), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()

            assert channels == 1, "Must be mono (1 channel)"
            assert sampwidth == 2, "Must be 16-bit PCM (2 bytes per sample)"
            assert framerate == 24000, "Must be 24kHz sample rate"
            assert nframes > 0, "Frames count must be > 0"

            expected_duration = round(nframes / float(framerate), 2)
            assert segment.duration_sec == expected_duration

    def test_speed_multiplier_affects_duration(self, tmp_path):
        provider = KokoroVoiceProvider()
        normal_file = tmp_path / "normal.wav"
        fast_file = tmp_path / "fast.wav"
        slow_file = tmp_path / "slow.wav"

        text = "This is a longer test sentence designed to measure playback rate scaling accurately."

        seg_normal = provider.generate_segment(text, "af_sky", speed=1.0, output_path=str(normal_file))
        seg_fast = provider.generate_segment(text, "af_sky", speed=2.0, output_path=str(fast_file))
        seg_slow = provider.generate_segment(text, "af_sky", speed=0.5, output_path=str(slow_file))

        # Fast speed should be approximately half normal duration
        assert seg_fast.duration_sec < seg_normal.duration_sec
        # Slow speed should be approximately double normal duration
        assert seg_slow.duration_sec > seg_normal.duration_sec
        assert pytest.approx(seg_fast.duration_sec * 2, abs=0.2) == seg_normal.duration_sec
        assert pytest.approx(seg_slow.duration_sec / 2, abs=0.2) == seg_normal.duration_sec

    def test_sha256_checksum_validity(self, tmp_path):
        provider = KokoroVoiceProvider()
        out_file = tmp_path / "checksum.wav"
        segment = provider.generate_segment("Checksum verification.", "af_sky", output_path=str(out_file))

        file_bytes = Path(out_file).read_bytes()
        expected_hash = hashlib.sha256(file_bytes).hexdigest()

        assert segment.checksum == expected_hash
        assert len(segment.checksum) == 64

    def test_helper_calculate_audio_duration_nonexistent_file(self):
        assert _calculate_audio_duration("/path/does/not/exist.wav") == 0.0

    def test_helper_compute_checksum_nonexistent_file(self):
        assert _compute_checksum("/path/does/not/exist.wav") == ""


class TestAdversarialManualVoiceProvider:
    """Stress tests for ManualVoiceProvider edge cases."""

    def test_nonexistent_path_raises_file_not_found(self):
        provider = ManualVoiceProvider()
        with pytest.raises(FileNotFoundError, match="Manual audio file expected"):
            provider.generate_segment("Text", "human", output_path="/nonexistent/path/file.wav")

    def test_empty_output_path_raises_value_error(self):
        provider = ManualVoiceProvider()
        with pytest.raises(ValueError, match="output_path must be specified"):
            provider.generate_segment("Text", "human", output_path="")

    def test_zero_byte_existing_file_raises_file_not_found(self, tmp_path):
        provider = ManualVoiceProvider()
        empty_file = tmp_path / "empty_manual.wav"
        empty_file.touch()  # Creates 0-byte file

        with pytest.raises(FileNotFoundError, match="Manual audio file expected"):
            provider.generate_segment("Text", "human", output_path=str(empty_file))

    def test_valid_manual_file_success(self, tmp_path):
        provider = ManualVoiceProvider()
        manual_file = tmp_path / "valid_manual.wav"

        # Generate actual WAV file
        kokoro = KokoroVoiceProvider()
        kokoro.generate_segment("Manual content", "af_sky", output_path=str(manual_file))

        segment = provider.generate_segment("Manual content", voice_id="", output_path=str(manual_file))

        assert segment.file_path == str(manual_file.resolve())
        assert segment.voice_id == "human_override"  # Default when empty voice_id passed
        assert segment.duration_sec > 0.0
        assert len(segment.checksum) == 64


class TestDataclassAndProtocolContracts:
    """Stress tests for data structures immutability and protocol re-exports."""

    def test_audio_segment_immutability(self):
        seg = AudioSegment("/path/a.wav", 2.5, "af_sky", "hash123")
        with pytest.raises(FrozenInstanceError):
            seg.file_path = "/path/b.wav"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            seg.checksum = "newhash"  # type: ignore

    def test_reexports_exact_reference_matching(self):
        assert synth_reexport.AudioSegment is AudioSegment
        assert synth_reexport.VoiceConfig is VoiceConfig
        assert synth_reexport.VoiceProviderProtocol is VoiceProviderProtocol
        assert synth_reexport.KokoroVoiceProvider is KokoroVoiceProvider
        assert synth_reexport.ManualVoiceProvider is ManualVoiceProvider
        assert synth_reexport.__all__ == [
            "AudioSegment",
            "VoiceConfig",
            "VoiceProviderProtocol",
            "KokoroVoiceProvider",
            "ManualVoiceProvider",
        ]
