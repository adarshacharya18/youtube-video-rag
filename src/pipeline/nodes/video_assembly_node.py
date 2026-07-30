"""Video Assembly Workflow Node for Phase 13 Media Production (FFmpeg).

Retrieves visual segments from animation_generator step output and audio/subtitle artifacts
from voice_generator/script_generator prior steps in the StateLedger. Invokes VideoAssembler
to compile them into a 4K video with burned-in subtitles, validates output against AssembledVideo
model, and guarantees explicit cleanup of temporary files.
"""

from datetime import datetime
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

from src.assembly.assembler import VideoAssembler
from src.core.exceptions import AssemblyError, PipelineStageError
from src.core.models.assets import AssetReference, AssembledVideo, RenderSegment
from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node

logger = logging.getLogger(__name__)


class VideoAssemblyNode(Node):
    """Workflow Engine Node for Phase 13 FFmpeg Video Assembly."""

    def __init__(
        self,
        ffmpeg_binary: Optional[str] = None,
        resolution: str = "3840x2160",
        fps: int = 30,
        crf: int = 18,
        preset: str = "medium",
        output_dir: Optional[Union[str, Path]] = None,
        timeout: float = 300.0,
        temp_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        """Initialize VideoAssemblyNode.

        Args:
            ffmpeg_binary: Optional path or binary name for FFmpeg binary or mock script.
            resolution: Target video resolution string (default: '3840x2160').
            fps: Video framerate (default: 30).
            crf: Constant Rate Factor quality setting (default: 18).
            preset: H.264 encoding preset (default: 'medium').
            output_dir: Destination directory for assembled video artifacts.
            timeout: Wall-clock timeout limit for FFmpeg execution in seconds.
            temp_dir: Custom parent directory for temporary file creation.
        """
        self.ffmpeg_binary = ffmpeg_binary
        self.resolution = resolution
        self.fps = fps
        self.crf = crf
        self.preset = preset
        self.timeout = timeout

        base_dir = Path.cwd()
        self.output_dir = (
            Path(output_dir) if output_dir else base_dir / "data" / "assets" / "assembled"
        )
        self.temp_dir = Path(temp_dir) if temp_dir else None

    @property
    def name(self) -> str:
        """Unique step name identifier in StateLedger."""
        return "video_assembly"

    def execute(self, run_id: str, ledger: Optional[StateLedger] = None) -> Dict[str, Any]:
        """Execute video assembly workflow step for the specified run_id.

        Args:
            run_id: Unique pipeline run identifier.
            ledger: Active StateLedger instance for step input retrieval.

        Returns:
            Dict[str, Any]: Output payload dictionary matching AssembledVideo schema.

        Raises:
            PipelineStageError: If ledger or required input step outputs are missing.
            AssemblyError: If FFmpeg assembly fails, times out, or output artifact is invalid.
        """
        logger.info("Executing VideoAssemblyNode for run_id=%s", run_id)

        if ledger is None:
            raise PipelineStageError(
                f"Node '{self.name}' requires an active StateLedger instance."
            )

        # 1. Retrieve animation_generator output step payload
        anim_output = self.get_step_output(run_id, ledger, "animation_generator")
        raw_slug = anim_output.get("slug", "unknown-slug")
        # Sanitize slug for AssembledVideo Pydantic schema validation (pattern: ^[a-z0-9-]+$)
        slug = re.sub(r"[^a-z0-9-]", "-", str(raw_slug).lower()).strip("-") or "video"

        raw_segments = anim_output.get("segments", [])

        if not raw_segments or not isinstance(raw_segments, list):
            raise PipelineStageError(
                f"Node '{self.name}' found no visual segments in 'animation_generator' output for run '{run_id}'."
            )

        # Extract segment video paths and validated RenderSegment objects
        video_segment_paths: List[Path] = []
        render_segments: List[RenderSegment] = []
        total_duration = 0.0

        for idx, seg_data in enumerate(raw_segments):
            if isinstance(seg_data, dict):
                visual_path = seg_data.get("visual_path")
                if not visual_path and "asset_references" in seg_data:
                    for ref in seg_data["asset_references"]:
                        if isinstance(ref, dict) and ref.get("asset_type") == "video":
                            visual_path = ref.get("file_path")
                            break

                if not visual_path:
                    raise PipelineStageError(
                        f"Segment at index {idx} in 'animation_generator' payload lacks a valid video visual_path."
                    )

                v_path = Path(visual_path)
                if not v_path.exists():
                    raise PipelineStageError(
                        f"Video segment file referenced at index {idx} does not exist: {v_path}"
                    )
                video_segment_paths.append(v_path)

                # Duration calculation
                start_t = float(seg_data.get("start_time", 0.0))
                end_t = float(seg_data.get("end_time") or (start_t + float(seg_data.get("duration") or 5.0)))
                duration = max(end_t - start_t, float(seg_data.get("duration") or 5.0))
                total_duration += duration

                try:
                    seg_model = RenderSegment.model_validate(seg_data)
                    render_segments.append(seg_model)
                except Exception:
                    # Construct fallback compliant RenderSegment
                    valid_seg_type = seg_data.get("segment_type")
                    allowed_types = {"intro", "code_walkthrough", "visual_anim", "outro", "narration"}
                    if valid_seg_type not in allowed_types:
                        valid_seg_type = "visual_anim"

                    asset_ref = AssetReference(
                        asset_id=f"anim_{idx}",
                        asset_type="video",
                        file_path=str(v_path),
                        duration=duration,
                    )
                    seg_model = RenderSegment(
                        segment_id=str(seg_data.get("segment_id") or f"seg_{idx}"),
                        segment_type=valid_seg_type,
                        start_time=start_t,
                        end_time=start_t + duration,
                        duration=duration,
                        visual_path=str(v_path),
                        asset_references=[asset_ref],
                    )
                    render_segments.append(seg_model)

        if not video_segment_paths:
            raise PipelineStageError(
                f"No valid existing video segment files found in 'animation_generator' output for run '{run_id}'."
            )

        # 2. Retrieve audio and subtitle artifacts (from voice_generator or script_generator)
        audio_path: Optional[Path] = None
        subtitle_path: Optional[Path] = None
        subtitle_text: Optional[str] = None

        completed_steps = ledger.get_completed_steps(run_id)

        # Check voice_generator step if available
        if "voice_generator" in completed_steps:
            voice_output = completed_steps["voice_generator"].output_payload or {}
            raw_audio = voice_output.get("audio_path")
            if raw_audio and Path(raw_audio).exists():
                audio_path = Path(raw_audio)
            raw_sub = voice_output.get("subtitle_path")
            if raw_sub and Path(raw_sub).exists():
                subtitle_path = Path(raw_sub)

        # Fallback to script_generator step
        if "script_generator" in completed_steps:
            script_output = completed_steps["script_generator"].output_payload or {}
            if not audio_path:
                raw_audio = script_output.get("audio_path") or script_output.get("script", {}).get("audio_path")
                if raw_audio and Path(raw_audio).exists():
                    audio_path = Path(raw_audio)
            if not subtitle_path:
                raw_sub = script_output.get("subtitle_path") or script_output.get("script", {}).get("subtitle_path")
                if raw_sub and Path(raw_sub).exists():
                    subtitle_path = Path(raw_sub)
            if not subtitle_path and not subtitle_text:
                srt_str = script_output.get("srt_content") or script_output.get("script", {}).get("srt_content")
                if srt_str and isinstance(srt_str, str):
                    subtitle_text = srt_str

        # 3. Setup output directory & target output video path
        run_output_dir = self.output_dir / run_id
        run_output_dir.mkdir(parents=True, exist_ok=True)
        final_video_path = run_output_dir / f"{slug}_assembled.mp4"

        # 4. Instantiate VideoAssembler & Execute Assembly
        assembler = VideoAssembler(
            ffmpeg_binary=self.ffmpeg_binary,
            timeout=self.timeout,
            temp_dir=self.temp_dir,
        )

        try:
            assembled_file = assembler.assemble(
                video_segments=video_segment_paths,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                subtitle_text=subtitle_text,
                output_path=final_video_path,
                resolution=self.resolution,
                fps=self.fps,
                crf=self.crf,
                preset=self.preset,
            )
        except AssemblyError:
            raise
        except Exception as e:
            logger.error("Unexpected error during video assembly for run_id=%s: %s", run_id, e)
            raise AssemblyError(f"Video assembly failed unexpectedly: {e}") from e

        # 5. Validate Output & Hydrate AssembledVideo Pydantic Model
        if not assembled_file.exists() or assembled_file.stat().st_size < 100:
            raise AssemblyError(
                f"Assembled video artifact missing or corrupted (< 100 bytes) at {assembled_file}"
            )

        file_size = assembled_file.stat().st_size
        assembled_at_str = datetime.utcnow().isoformat()

        try:
            assembled_model = AssembledVideo(
                slug=slug,
                final_video_path=str(assembled_file),
                total_duration_seconds=max(total_duration, 0.1),
                file_size_bytes=file_size,
                segments=render_segments,
                assembled_at=assembled_at_str,
            )
        except Exception as e:
            logger.error("AssembledVideo Pydantic model validation failed: %s", e)
            raise AssemblyError(f"Failed to validate AssembledVideo output schema: {e}") from e

        output_payload = assembled_model.model_dump()
        logger.info(
            "VideoAssemblyNode completed successfully for run_id=%s (file=%s, size=%d bytes)",
            run_id,
            assembled_file,
            file_size,
        )
        return output_payload
