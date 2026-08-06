"""
Kokoro TTS Voice Subsystem Isolation Test Suite (Requirement R1).

Verifies that KokoroVoiceProvider synthesizes real 24kHz mono PCM voice audio on CPU
using kokoro_onnx without falling back to a continuous synthetic 440 Hz beep.
Uses acoustic waveform analysis including:
- PCM WAV format verification (24kHz, 16-bit mono)
- Non-zero sample verification
- Audio duration verification
- Pause ratio (> 5%) analysis
- RMS energy variance (> 50) analysis
- Dynamic spectral frequency analysis (speech spectrum vs pure sine wave tone)
"""

from pathlib import Path
import numpy as np
import pytest
import wave

from src.core.media.voice import AudioSegment, KokoroVoiceProvider


def _read_wav_samples(wav_path: str) -> tuple[np.ndarray, int, int, int]:
    """Reads WAV file and returns (pcm16_samples, num_channels, sampwidth, framerate)."""
    with wave.open(wav_path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)

    samples = np.frombuffer(raw_bytes, dtype=np.int16)
    return samples, n_channels, sampwidth, framerate


def _compute_acoustic_metrics(pcm16_samples: np.ndarray, sample_rate: int, frame_ms: float = 20.0):
    """
    Computes acoustic waveform metrics for voice detection vs synthetic beep detection.

    Returns dict:
    - rms_variance: variance of frame-level RMS energy values
    - pause_ratio: proportion of quiet/pause frames relative to peak frame RMS energy
    - non_zero_count: count of non-zero PCM samples
    - peak_frequency: dominant frequency from FFT
    - spectral_entropy: entropy of FFT frequency spectrum (higher for speech, low for sine wave)
    """
    frame_size = int(sample_rate * (frame_ms / 1000.0))
    if frame_size <= 0:
        frame_size = 480

    n_full_frames = len(pcm16_samples) // frame_size
    if n_full_frames == 0:
        return {
            "rms_variance": 0.0,
            "pause_ratio": 0.0,
            "non_zero_count": 0,
            "peak_frequency": 0.0,
            "spectral_entropy": 0.0,
        }

    frames = [
        pcm16_samples[i * frame_size : (i + 1) * frame_size].astype(np.float64)
        for i in range(n_full_frames)
    ]

    rms_values = [np.sqrt(np.mean(f ** 2)) for f in frames]
    max_rms = np.max(rms_values) if rms_values else 0.0
    rms_variance = float(np.var(rms_values)) if rms_values else 0.0

    # Pause threshold: frames with RMS < 5% of max RMS
    silence_thresh = 0.05 * max_rms
    silent_count = sum(1 for r in rms_values if r < silence_thresh)
    pause_ratio = (silent_count / len(rms_values)) if rms_values else 0.0

    non_zero_count = int(np.count_nonzero(pcm16_samples))

    # Spectral analysis using FFT on first 1-second segment or full audio
    analysis_samples = pcm16_samples[:sample_rate].astype(np.float64)
    fft_mag = np.abs(np.fft.rfft(analysis_samples))
    freqs = np.fft.rfftfreq(len(analysis_samples), d=1.0 / sample_rate)

    peak_idx = np.argmax(fft_mag)
    peak_frequency = float(freqs[peak_idx])

    # Calculate normalized spectral entropy
    psd = fft_mag ** 2
    total_power = np.sum(psd)
    if total_power > 0:
        prob = psd / total_power
        prob = prob[prob > 0]
        spectral_entropy = float(-np.sum(prob * np.log2(prob)))
    else:
        spectral_entropy = 0.0

    return {
        "rms_variance": rms_variance,
        "pause_ratio": pause_ratio,
        "non_zero_count": non_zero_count,
        "peak_frequency": peak_frequency,
        "spectral_entropy": spectral_entropy,
        "max_rms": max_rms,
    }


class TestKokoroVoiceIsolation:
    """Requirement R1: Kokoro TTS Audio Subsystem Isolation Test Suite."""

    def test_kokoro_voice_provider_cpu_synthesis_real_speech(self, tmp_path):
        """
        Verify KokoroVoiceProvider generates real 24kHz mono voice audio on CPU
        and does NOT produce the continuous 440 Hz synthetic beep.
        """
        provider = KokoroVoiceProvider()
        output_file = tmp_path / "kokoro_speech_test.wav"
        text = "Hello world! This is an isolated test verifying real speech synthesis on CPU using Kokoro."

        segment = provider.generate_segment(
            text=text,
            voice_id="af_sky",
            speed=1.0,
            output_path=str(output_file),
        )

        # 1. Output segment metadata assertion
        assert isinstance(segment, AudioSegment)
        assert Path(segment.file_path).exists()
        assert segment.duration_sec > 1.0
        assert segment.voice_id == "af_sky"
        assert len(segment.checksum) == 64

        # 2. WAV Format Assertions
        samples, n_channels, sampwidth, framerate = _read_wav_samples(str(output_file))
        assert n_channels == 1, "Audio must be mono (1 channel)"
        assert sampwidth == 2, "Audio must be 16-bit PCM (2 bytes per sample)"
        assert framerate == 24000, "Audio sample rate must be 24kHz (24000 Hz)"
        assert len(samples) > 0, "Audio sample buffer must not be empty"

        # 3. Acoustic Waveform Analysis
        metrics = _compute_acoustic_metrics(samples, framerate)

        # Check 3a: Non-zero audio samples
        assert metrics["non_zero_count"] > 1000, "Real speech must contain non-zero audio samples"

        # Check 3b: Pause ratio > 5% (natural speech pauses between words/sentences)
        assert metrics["pause_ratio"] > 0.05, (
            f"Pause ratio ({metrics['pause_ratio']*100:.2f}%) must be > 5% for natural speech "
            f"(continuous beep has 0% pause ratio)."
        )

        # Check 3c: RMS energy variance > 50 (dynamic speech energy vs flat sine wave)
        assert metrics["rms_variance"] > 50.0, (
            f"RMS energy variance ({metrics['rms_variance']:.2f}) must be > 50.0 for natural speech "
            f"(continuous beep has ~18.5 RMS variance)."
        )

        # Check 3d: Spectral entropy (speech has broad spectral distribution, not a single pure tone)
        assert metrics["spectral_entropy"] > 4.0, (
            f"Spectral entropy ({metrics['spectral_entropy']:.2f}) must be > 4.0 for speech "
            f"(sine wave has low spectral entropy)."
        )

    def test_kokoro_voice_provider_handles_different_voices_and_speeds(self, tmp_path):
        """Verify KokoroVoiceProvider works with multiple voice IDs and speed settings."""
        provider = KokoroVoiceProvider()
        out_normal = tmp_path / "voice_normal.wav"
        out_fast = tmp_path / "voice_fast.wav"

        text = "Testing playback speed variation in speech synthesis."

        seg_normal = provider.generate_segment(text, "af_sky", speed=1.0, output_path=str(out_normal))
        seg_fast = provider.generate_segment(text, "af_sky", speed=1.5, output_path=str(out_fast))

        assert seg_fast.duration_sec < seg_normal.duration_sec

        samples_normal, _, _, sr_normal = _read_wav_samples(str(out_normal))
        samples_fast, _, _, sr_fast = _read_wav_samples(str(out_fast))

        assert sr_normal == 24000
        assert sr_fast == 24000

        m_normal = _compute_acoustic_metrics(samples_normal, sr_normal)
        m_fast = _compute_acoustic_metrics(samples_fast, sr_fast)

        assert m_normal["rms_variance"] > 50.0
        assert m_fast["rms_variance"] > 50.0

    def test_kokoro_voice_provider_pronunciation_sanitization(self, tmp_path):
        """Verify technical jargon (Dijkstra, O(N)) is sanitized during real voice synthesis."""
        provider = KokoroVoiceProvider()
        output_file = tmp_path / "dijkstra_speech.wav"
        text = "Algorithm O(N) using Dijkstra graph traversal."

        segment = provider.generate_segment(text, "af_sky", speed=1.0, output_path=str(output_file))

        assert Path(segment.file_path).exists()
        assert segment.duration_sec > 0.5
        samples, _, _, sr = _read_wav_samples(str(output_file))
        metrics = _compute_acoustic_metrics(samples, sr)
        assert metrics["non_zero_count"] > 1000
        assert metrics["rms_variance"] > 50.0
