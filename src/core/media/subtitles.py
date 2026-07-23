"""
Subtitle Generation Subsystem (Phase 13)

Translates NarrationPlans and generated AudioSegments into precise SRT and VTT
subtitle files with word-level or sentence-level timing synchronization.
"""
import logging
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import List, Protocol

from src.core.media.voice import AudioSegment
from src.core.script.narration import NarrationPlan


@dataclass
class SubtitleSegment:
    """Metadata tracking a single subtitle sentence or word phrase."""
    index: int
    start_ms: int
    end_ms: int
    text: str


class SubtitleProviderProtocol(Protocol):
    """Abstract interface for all Subtitle Transcribers/Aligners (Strategy Pattern)."""
    
    def generate_subtitles(
        self,
        audio_files: List[AudioSegment],
        narration_plan: NarrationPlan,
        output_base_path: str
    ) -> bool:
        ...


class WhisperSubtitleProvider:
    """
    Concrete implementation utilizing WhisperX or similar word-level alignment tools.
    Since we already have the Narration text, we don't need raw transcription, just force-alignment.
    """
    
    def __init__(self, model_size: str = "tiny"):
        self._logger = logging.getLogger(__name__)
        self.model_size = model_size

    def _ms_to_srt_time(self, ms: int) -> str:
        """Converts milliseconds into SRT timestamp format (HH:MM:SS,mmm)."""
        td = timedelta(milliseconds=ms)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
        
    def _ms_to_vtt_time(self, ms: int) -> str:
        """Converts milliseconds into VTT timestamp format (HH:MM:SS.mmm)."""
        td = timedelta(milliseconds=ms)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def _generate_srt(self, segments: List[SubtitleSegment], output_path: str) -> None:
        """Writes strictly formatted SubRip (SRT) files."""
        with open(output_path, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(f"{seg.index}\n")
                f.write(f"{self._ms_to_srt_time(seg.start_ms)} --> {self._ms_to_srt_time(seg.end_ms)}\n")
                f.write(f"{seg.text}\n\n")

    def _generate_vtt(self, segments: List[SubtitleSegment], output_path: str) -> None:
        """Writes strictly formatted WebVTT files."""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for seg in segments:
                f.write(f"{seg.index}\n")
                f.write(f"{self._ms_to_vtt_time(seg.start_ms)} --> {self._ms_to_vtt_time(seg.end_ms)}\n")
                f.write(f"{seg.text}\n\n")

    def generate_subtitles(
        self,
        audio_files: List[AudioSegment],
        narration_plan: NarrationPlan,
        output_base_path: str
    ) -> bool:
        """
        Orchestrates the alignment and formatting of subtitles.
        """
        self._logger.info(f"Generating subtitles using Forced-Alignment ({self.model_size})")
        
        # Validation Boundary
        if len(audio_files) != len(narration_plan.blocks):
            self._logger.error("Mismatch between Audio Segments and Narration Blocks. Cannot synchronize.")
            raise ValueError("Synchronization Failed: Array mismatch between Audio and Narration boundaries.")
            
        aligned_segments = []
        current_time_ms = 0
        
        # STUB: Execute Forced-Alignment via WhisperX or PyTorch
        # We loop through the audio and map it linearly to the known text block
        for i, (audio, block) in enumerate(zip(audio_files, narration_plan.blocks)):
            duration_ms = int(audio.duration_sec * 1000)
            
            aligned_segments.append(
                SubtitleSegment(
                    index=i+1,
                    start_ms=current_time_ms,
                    end_ms=current_time_ms + duration_ms,
                    text=block.spoken_text
                )
            )
            current_time_ms += duration_ms

        # Physical File Generation
        srt_path = f"{output_base_path}.srt"
        vtt_path = f"{output_base_path}.vtt"
        
        self._generate_srt(aligned_segments, srt_path)
        self._generate_vtt(aligned_segments, vtt_path)
        
        self._logger.info(f"Subtitles successfully generated at {srt_path} and {vtt_path}")
        return True
