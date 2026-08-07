"""Voice Generator / TTS Workflow Node (Phase 08 / Phase 13).

Synthesizes audio narration and generates subtitle alignment artifacts.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.core.exceptions import PipelineStageError, VoiceGenerationError
from src.core.media.voice import AudioSegment, KokoroVoiceProvider, VoiceProviderProtocol
from src.core.media.gemini_providers import GeminiVoiceProvider
from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node
from src.models.script import YouTubeScript
import os

logger = logging.getLogger(__name__)


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp format (HH:MM:SS,mmm)."""
    seconds = max(0.0, seconds)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        total_seconds = int(seconds) + 1
        millis = 0
    else:
        total_seconds = int(seconds)
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    mins = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"


class VoiceGeneratorNode(Node):
    """Workflow Engine Node for Phase 08 / Phase 13 TTS & Voice Synthesis."""

    def __init__(
        self,
        provider: Optional[VoiceProviderProtocol] = None,
        output_dir: Optional[Union[str, Path]] = None,
        voice_id: str = "af_sky",
        speed: float = 0.75,
    ) -> None:
        """Initialize VoiceGeneratorNode.

        Args:
            provider: Optional voice provider strategy (defaults to KokoroVoiceProvider).
            output_dir: Optional custom output directory path.
            voice_id: Voice identifier string (defaults to 'af_sky').
            speed: Playback / speech speed modifier (defaults to 0.85).
        """
        if provider is not None:
            self.provider: VoiceProviderProtocol = provider
        elif os.getenv("GEMINI_AUDIO_MODEL"):
            self.provider = GeminiVoiceProvider(model_name=os.getenv("GEMINI_AUDIO_MODEL"))
        else:
            self.provider = KokoroVoiceProvider()
            
        self.output_dir = Path(output_dir) if output_dir else None
        self.voice_id = voice_id
        self.speed = speed

    @property
    def name(self) -> str:
        """Unique step name identifier in StateLedger."""
        return "voice_generator"

    def execute(self, run_id: str, ledger: Optional[StateLedger] = None) -> Dict[str, Any]:
        """Execute voice generation TTS step for the specified run_id.

        Args:
            run_id: Unique pipeline run identifier.
            ledger: Active StateLedger instance.

        Returns:
            Dict[str, Any]: Audio and subtitle artifact payload recorded in StateLedger.

        Raises:
            PipelineStageError: If ledger is missing.
            VoiceGenerationError: If audio synthesis fails or output is missing.
        """
        if ledger is None:
            raise PipelineStageError(f"Node '{self.name}' requires a valid StateLedger instance.")

        run_record = self.get_run_record(run_id, ledger)
        slug = run_record.slug

        logger.info("Executing VoiceGeneratorNode for slug=%s (run_id=%s)", slug, run_id)

        base_dir = self.output_dir if self.output_dir is not None else Path("data/audio") / slug
        base_dir.mkdir(parents=True, exist_ok=True)

        audio_file = base_dir / "master_audio.wav"
        sub_file = base_dir / "subtitles.srt"

        # 1. Retrieve script_generator step output from ledger if available
        completed_steps = ledger.get_completed_steps(run_id)
        script_payload: Optional[Dict[str, Any]] = None
        if "script_generator" in completed_steps:
            script_payload = self.get_step_output(run_id, ledger, "script_generator")

        narration_segments: List[str] = []
        if script_payload:
            narration_segments = self._extract_narration_segments(script_payload)

        # 2. Execute Voice Synthesis if narration is available or if fallback narration is needed
        duration_sec = 10.0
        if narration_segments:
            combined_text = " ".join(narration_segments)
            try:
                segment: AudioSegment = self.provider.generate_segment(
                    text=combined_text,
                    voice_id=self.voice_id,
                    speed=self.speed,
                    output_path=str(audio_file),
                )
                duration_sec = segment.duration_sec
            except VoiceGenerationError:
                raise
            except Exception as e:
                logger.error("TTS synthesis error for slug '%s': %s", slug, e)
                raise VoiceGenerationError(f"TTS audio synthesis failed for slug '{slug}': {e}") from e
        elif script_payload:
            # Fallback narration if script payload is present but no explicit segments extracted
            fallback_text = f"Welcome to the video for {slug}."
            try:
                segment: AudioSegment = self.provider.generate_segment(
                    text=fallback_text,
                    voice_id=self.voice_id,
                    speed=self.speed,
                    output_path=str(audio_file),
                )
                duration_sec = segment.duration_sec
                narration_segments = [fallback_text]
            except VoiceGenerationError:
                raise
            except Exception as e:
                logger.error("TTS synthesis error for slug '%s': %s", slug, e)
                raise VoiceGenerationError(f"TTS audio synthesis failed for slug '{slug}': {e}") from e
        elif not audio_file.exists():
            raise VoiceGenerationError(
                f"TTS audio synthesis failed for slug '{slug}': master audio file was not found at {audio_file} "
                f"and no upstream script_generator output was present in StateLedger."
            )

        if not audio_file.exists() or audio_file.stat().st_size == 0:
            raise VoiceGenerationError(
                f"TTS audio synthesis failed for slug '{slug}': master audio file was not found or zero-byte at {audio_file}"
            )

        # 3. Subtitle / SRT Generation
        srt_content = ""
        if narration_segments:
            srt_content = self._generate_srt_content(narration_segments, duration_sec)
            sub_file.write_text(srt_content, encoding="utf-8")
        elif sub_file.exists():
            srt_content = sub_file.read_text(encoding="utf-8")

        return {
            "slug": slug,
            "audio_path": str(audio_file.resolve()),
            "subtitle_path": str(sub_file.resolve()) if sub_file.exists() else "",
            "srt_content": srt_content,
            "duration_seconds": duration_sec,
            "status": "completed",
        }

    def _extract_narration_segments(self, script_payload: Dict[str, Any]) -> List[str]:
        """Extract list of spoken narration text segments from script payload or YouTubeScript."""
        narration_list: List[str] = []
        script_data = script_payload.get("script")

        if isinstance(script_data, dict):
            try:
                script_model = YouTubeScript.model_validate(script_data)
                narration_list = [s for s in script_model.spoken_narration if s and s.strip()]
            except Exception:
                for key in ("hook", "context", "solution", "complexity"):
                    sec = script_data.get(key)
                    if isinstance(sec, dict) and "narration" in sec and isinstance(sec["narration"], str):
                        txt = sec["narration"].strip()
                        if txt:
                            narration_list.append(txt)
        elif isinstance(script_data, YouTubeScript):
            narration_list = [s for s in script_data.spoken_narration if s and s.strip()]
        elif isinstance(script_data, str) and script_data.strip():
            narration_list = [script_data.strip()]

        if not narration_list and "spoken_narration" in script_payload:
            raw_sp = script_payload["spoken_narration"]
            if isinstance(raw_sp, list):
                narration_list = [str(s).strip() for s in raw_sp if str(s).strip()]
            elif isinstance(raw_sp, str) and raw_sp.strip():
                narration_list = [raw_sp.strip()]

        return narration_list

    def _generate_srt_content(self, segments: List[str], total_duration: float) -> str:
        """Format list of narration segments into valid SRT subtitle string."""
        import re
        
        # Flatten and split massive paragraphs into bite-sized sentences for subtitles
        sentences = []
        for segment in segments:
            # Split by punctuation (period, exclamation, question mark) followed by whitespace
            parts = re.split(r'(?<=[.!?])\s+', segment.strip())
            sentences.extend([p.strip() for p in parts if p.strip()])
            
        if not sentences:
            return ""
        total_chars = sum(len(s) for s in sentences)
        if total_chars == 0:
            total_chars = 1

        current_time = 0.0
        srt_entries: List[str] = []

        for idx, text in enumerate(sentences, start=1):
            char_ratio = len(text) / total_chars
            seg_duration = char_ratio * total_duration
            start_t = current_time
            end_t = total_duration if idx == len(sentences) else start_t + seg_duration

            start_str = format_srt_timestamp(start_t)
            end_str = format_srt_timestamp(end_t)

            srt_entries.append(f"{idx}\n{start_str} --> {end_str}\n{text.strip()}")
            current_time = end_t

        return "\n\n".join(srt_entries) + "\n"

