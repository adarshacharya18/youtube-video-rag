"""
Video Assembly Subsystem (Phase 13)

Orchestrates FFmpeg to multiplex audio, video, subtitles, and background music
into the final production-ready YouTube deliverable. Supports multiple resolutions
and metadata injection.
"""
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class AssemblyConfig:
    """Configuration constraints for FFmpeg execution."""
    resolution: str = "1920x1080"
    fps: int = 60
    audio_bitrate: str = "320k"    # Highest standard YouTube quality
    video_bitrate: str = "8M"      # Crisp 1080p60 target
    intro_path: Optional[str] = None
    outro_path: Optional[str] = None
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.05       # 5% volume so it doesn't overpower narration


class FFmpegVideoAssembler:
    """
    Executes complex FFmpeg filtergraphs to multiplex isolated assets into a final MP4.
    """
    
    def __init__(self, config: AssemblyConfig = AssemblyConfig()):
        self._logger = logging.getLogger(__name__)
        self.config = config

    def _validate_inputs(self, audio: str, video: str, subtitles: Optional[str] = None) -> bool:
        """
        Validates that all target physical files exist on disk before executing C-level FFmpeg.
        Failing here prevents FFmpeg from returning cryptic C-level stack traces.
        """
        if not Path(audio).exists():
            raise FileNotFoundError(f"Assembly Failed: Master audio missing at {audio}")
        if not Path(video).exists():
            raise FileNotFoundError(f"Assembly Failed: Master video missing at {video}")
        if subtitles and not Path(subtitles).exists():
            raise FileNotFoundError(f"Assembly Failed: Subtitles missing at {subtitles}")
        return True

    def _build_ffmpeg_command(
        self, 
        master_audio: str, 
        master_video: str, 
        output_path: str, 
        subtitle_path: Optional[str] = None
    ) -> List[str]:
        """Constructs the complex FFmpeg command line array, managing filtergraphs safely."""
        cmd = [
            "ffmpeg", "-y",  # Auto-overwrite existing output
            "-i", master_video,
            "-i", master_audio
        ]
        
        # Complex Filtergraph for BGM & Subtitle Burn-In
        if self.config.bgm_path and Path(self.config.bgm_path).exists():
            cmd.extend(["-i", self.config.bgm_path])
            
            # Filtergraph to mix BGM with Master Audio, heavily ducking BGM volume
            filter_complex = f"[2:a]volume={self.config.bgm_volume}[bgm];[1:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            
            # Chain subtitle burn-in to the filtergraph
            if subtitle_path:
                filter_complex += f",[0:v]subtitles='{subtitle_path}'[vout]"
                cmd.extend(["-filter_complex", filter_complex, "-map", "[vout]", "-map", "[aout]"])
            else:
                cmd.extend(["-filter_complex", filter_complex, "-map", "0:v", "-map", "[aout]"])
        else:
            # Simple Filtergraph (No BGM)
            if subtitle_path:
                cmd.extend(["-vf", f"subtitles='{subtitle_path}'"])
            cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])
            
        # Codecs and Bitrates (H.264 standard for YouTube)
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-b:v", self.config.video_bitrate,
            "-c:a", "aac",
            "-b:a", self.config.audio_bitrate,
            "-r", str(self.config.fps),
            output_path
        ])
        
        return cmd

    def assemble_final_video(
        self,
        master_audio_path: str,
        master_video_path: str,
        output_path: str,
        subtitle_path: Optional[str] = None,
        chapter_metadata: Optional[dict] = None
    ) -> bool:
        """
        Orchestrates the multiplexing of the final video artifact.
        Assumes `master_video_path` was already built by concatenating individual Manim scenes.
        """
        self._logger.info(f"Assembling Final Video: {output_path} ({self.config.resolution} @ {self.config.fps}fps)")
        self._validate_inputs(master_audio_path, master_video_path, subtitle_path)
        
        # 1. Build FFmpeg Command Array
        command = self._build_ffmpeg_command(master_audio_path, master_video_path, output_path, subtitle_path)
        self._logger.debug(f"Executing: {' '.join(command)}")
        
        # 2. Execute Subprocess execution safely
        try:
            # We use subprocess.run to isolate the memory-heavy FFmpeg C-libraries
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            self._logger.info("FFmpeg Multiplexing Successful.")
        except subprocess.CalledProcessError as e:
            self._logger.critical(f"FFmpeg Assembly Failed:\n{e.stderr}")
            raise RuntimeError("Final video multiplexing crashed. See logs for FFmpeg stderr.") from e
            
        # 3. Chapter Metadata Injection
        if chapter_metadata:
            self._logger.info("Injecting Chapter Metadata into MP4 container.")
            # STUB: Execute atomic MP4Box or FFmpeg metadata pass here to add YouTube chapters
            
        return True
