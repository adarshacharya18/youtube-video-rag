"""
Voice Production Subsystem (Phase 13 / Milestone 1).

Defines core voice data structures, strategy protocol, and concrete providers
(KokoroVoiceProvider with CPU wave synthesis, ManualVoiceProvider).
"""

import hashlib
import logging
import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Protocol

from src.core.exceptions import VoiceGenerationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioSegment:
    """Immutable metadata tracking a generated physical audio file."""
    file_path: str
    duration_sec: float
    voice_id: str
    checksum: str


@dataclass
class VoiceConfig:
    """Configuration settings for voice synthesis."""
    voice_id: str = "af_sky"
    sample_rate: int = 24000
    speed: float = 1.0
    pitch: float = 1.0


class VoiceProviderProtocol(Protocol):
    """Abstract interface for all Voice TTS engines (Strategy Pattern)."""

    def generate_segment(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        output_path: str = ""
    ) -> AudioSegment:
        """Generates an audio file from text."""
        ...


def _compute_checksum(file_path: str) -> str:
    """Calculates SHA-256 checksum of a file."""
    path = Path(file_path)
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _calculate_audio_duration(file_path: str) -> float:
    """Calculates duration in seconds from a WAV file header."""
    path = Path(file_path)
    if not path.exists():
        return 0.0
    try:
        with wave.open(str(path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return round(frames / float(rate), 2)
    except Exception:
        pass
    return 0.0


class KokoroVoiceProvider:
    """
    Concrete implementation of Kokoro TTS.
    Converts text to speech, applying pronunciation dictionaries, retry logic,
    and CPU audio synthesis generating valid 16-bit PCM WAV (24000 Hz, mono).
    """
    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        model_path: str = "",
        pronunciation_dict: Optional[Dict[str, str]] = None
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self.model_path = model_path
        self.pronunciation_dict = pronunciation_dict if pronunciation_dict is not None else {
            "Dijkstra": "dike-struh",
            "O(N)": "O of N",
            "O(N^2)": "O of N squared",
        }
        if model_path:
            self._logger.info(f"Initialized Kokoro Engine with model_path at {model_path}")
        else:
            self._logger.info("Initialized Kokoro Engine with CPU audio synthesis mode")

    def _apply_pronunciation_fixes(self, text: str) -> str:
        """Sanitizes technical jargon into phonetic equivalents for TTS."""
        if not text:
            return ""
        for technical_word, phonetic_replacement in self.pronunciation_dict.items():
            text = text.replace(technical_word, phonetic_replacement)
        return text

    def _synthesize_pcm_wave(self, text: str, speed: float, output_path: str, voice_id: str) -> float:
        """
        CPU audio synthesis producing a valid PCM WAV (24000 Hz, mono).
        Uses kokoro-onnx for real voice if models are downloaded, else falls back to a beep.
        Ensures parent directories exist before writing.
        """
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            from kokoro_onnx import Kokoro
            import soundfile as sf

            project_root = Path(__file__).resolve().parents[3]

            model_candidates = []
            if self.model_path:
                model_candidates.extend([
                    Path(self.model_path),
                    project_root / self.model_path,
                    Path.cwd() / self.model_path,
                ])
            model_candidates.extend([
                project_root / "models" / "kokoro-v1.0.onnx",
                project_root / "models" / "kokoro" / "kokoro-v0_19.onnx",
                Path.cwd() / "models" / "kokoro-v1.0.onnx",
                Path.cwd() / "models" / "kokoro" / "kokoro-v0_19.onnx",
            ])

            voices_candidates = [
                project_root / "models" / "voices-v1.0.bin",
                project_root / "models" / "voices.bin",
                project_root / "models" / "kokoro" / "voices-v1.0.bin",
                Path.cwd() / "models" / "voices-v1.0.bin",
                Path.cwd() / "models" / "voices.bin",
            ]

            resolved_model_path = next((p for p in model_candidates if p.exists() and p.is_file()), None)
            resolved_voices_path = next((p for p in voices_candidates if p.exists() and p.is_file()), None)

            if resolved_voices_path is None:
                for search_dir in [project_root / "models", Path.cwd() / "models"]:
                    if search_dir.exists():
                        bin_files = list(search_dir.glob("*.bin"))
                        if bin_files:
                            resolved_voices_path = bin_files[0]
                            break

            if resolved_model_path and resolved_voices_path:
                self._logger.info(
                    f"Using Kokoro ONNX CPU inference for TTS (model={resolved_model_path.name}, voices={resolved_voices_path.name}) with voice: {voice_id}"
                )
                kokoro = Kokoro(str(resolved_model_path), str(resolved_voices_path))

                try:
                    samples, sample_rate = kokoro.create(text, voice=voice_id, speed=speed, lang="en-us")
                except Exception as e:
                    self._logger.warning(f"Voice {voice_id} failed, falling back to af_sky: {e}")
                    samples, sample_rate = kokoro.create(text, voice="af_sky", speed=speed, lang="en-us")

                sf.write(str(out_path), samples, sample_rate)
                return _calculate_audio_duration(str(out_path))
            else:
                self._logger.warning("Kokoro ONNX models missing. Falling back to synthetic beep.")
        except ImportError:
            self._logger.warning("kokoro-onnx not installed. Falling back to synthetic beep.")
        except Exception as e:
            self._logger.error(f"Kokoro ONNX inference failed: {e}. Falling back to beep.")

        # Fallback Beep Synthesis
        sample_rate = 24000
        words = len(text.split()) if text else 1
        base_duration = max(1.0, words / 2.5)  # ~150 words per minute
        effective_speed = max(0.1, speed)
        duration_sec = base_duration / effective_speed

        num_samples = int(sample_rate * duration_sec)
        frequency = 440.0
        amplitude = 1000

        with wave.open(str(out_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            packed_data = bytearray()
            for i in range(num_samples):
                sample = int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
                packed_data.extend(struct.pack("<h", sample))

            wav_file.writeframes(packed_data)

        return duration_sec

    def generate_segment(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        output_path: str = ""
    ) -> AudioSegment:
        if not output_path:
            raise ValueError("output_path must be specified.")

        cleaned_text = self._apply_pronunciation_fixes(text)
        out_path = Path(output_path)

        max_retries = 3
        last_exception = None

        for attempt in range(max_retries):
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                self._logger.info(
                    f"Kokoro generating audio (Attempt {attempt+1}/{max_retries}) to {output_path}"
                )
                self._synthesize_pcm_wave(cleaned_text, speed, str(out_path), voice_id)

                if not out_path.exists() or out_path.stat().st_size == 0:
                    raise VoiceGenerationError(f"Generated audio file missing or empty at {output_path}")

                duration_sec = _calculate_audio_duration(str(out_path))
                checksum = _compute_checksum(str(out_path))

                return AudioSegment(
                    file_path=str(out_path.resolve()),
                    duration_sec=duration_sec,
                    voice_id=voice_id,
                    checksum=checksum,
                )
            except Exception as e:
                last_exception = e
                self._logger.warning(f"Audio hardware generation attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    raise VoiceGenerationError(
                        f"Voice generation permanently failed after {max_retries} attempts."
                    ) from last_exception


class ManualVoiceProvider:
    """
    Fallback provider for Manual narration.
    Requires a human to record and place a physical audio file at output_path.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def generate_segment(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        output_path: str = ""
    ) -> AudioSegment:
        self._logger.info(f"Manual Voice Provider triggered. Awaiting human audio file at: {output_path}")

        if not output_path:
            raise ValueError("output_path must be specified.")

        path = Path(output_path)
        if not path.exists() or path.stat().st_size == 0:
            raise FileNotFoundError(
                f"Manual audio file expected at {output_path} but not found. "
                "Did the human voice actor forget to record and place the file?"
            )

        duration_sec = _calculate_audio_duration(str(path))
        checksum = _compute_checksum(str(path))

        return AudioSegment(
            file_path=str(path.resolve()),
            duration_sec=duration_sec,
            voice_id=voice_id or "human_override",
            checksum=checksum,
        )
