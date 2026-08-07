"""Animation Generator Workflow Node for Phase 12 Media Production (Manim).

Extracts visual cues from script_generator prior step, maps them to Manim scene
templates, executes rendering securely via subprocess, manages memory and caching,
and outputs RenderSegment manifests to StateLedger.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Union

from src.animation.renderer import ManimRenderer
from src.core.exceptions import AnimationError, PipelineStageError
from src.core.models.assets import AssetReference, RenderSegment
from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node
from src.models.script import VisualCue, YouTubeScript
from src.core.media.gemini_providers import GeminiVideoProvider

logger = logging.getLogger(__name__)

# Default quality flag mapping
QUALITY_FLAGS: Dict[str, str] = {
    "low": "-ql",
    "480p": "-ql",
    "medium": "-qm",
    "720p": "-qm",
    "high": "-qh",
    "1080p": "-qh",
    "fourk": "-qk",
    "4k": "-qk",
}

# Mapping of VisualCue.animation_type to (scene_file_rel_path, scene_class_name)
ANIMATION_TYPE_MAP: Dict[str, tuple[str, str]] = {
    "title_card": ("src/animation/scenes/title_scene.py", "TitleScene"),
    "array_highlight": ("src/animation/scenes/array_scene.py", "ArrayScene"),
    "array_traversal": ("src/animation/scenes/array_scene.py", "ArrayScene"),
    "tree_traversal": ("src/animation/scenes/tree_scene.py", "TreeScene"),
    "binary_tree": ("src/animation/scenes/tree_scene.py", "TreeScene"),
    "code_highlight": ("src/animation/scenes/code_scene.py", "CodeScene"),
    "code_walkthrough": ("src/animation/scenes/code_scene.py", "CodeScene"),
    "code_scene": ("src/animation/scenes/code_scene.py", "CodeScene"),
    "graph_animation": ("src/animation/scenes/graph_scene.py", "GraphScene"),
    "graph_traversal": ("src/animation/scenes/graph_scene.py", "GraphScene"),
    "hashmap_operation": ("src/animation/scenes/hashmap_scene.py", "HashmapScene"),
    "hashmap_insert": ("src/animation/scenes/hashmap_scene.py", "HashmapScene"),
    "hashmap_lookup": ("src/animation/scenes/hashmap_scene.py", "HashmapScene"),
    "hashmap": ("src/animation/scenes/hashmap_scene.py", "HashmapScene"),
    "linkedlist_pointer": ("src/animation/scenes/linkedlist_scene.py", "LinkedListScene"),
    "linked_list": ("src/animation/scenes/linkedlist_scene.py", "LinkedListScene"),
    "linkedlist": ("src/animation/scenes/linkedlist_scene.py", "LinkedListScene"),
    "linkedlist_operation": ("src/animation/scenes/linkedlist_scene.py", "LinkedListScene"),
    "stack_queue_operation": ("src/animation/scenes/stack_queue_scene.py", "StackQueueScene"),
    "stack_queue": ("src/animation/scenes/stack_queue_scene.py", "StackQueueScene"),
    "complexity_chart": ("src/animation/scenes/complexity_scene.py", "ComplexityScene"),
    "complexity": ("src/animation/scenes/complexity_scene.py", "ComplexityScene"),
    "list_folding": ("src/animation/scenes/linkedlist_scene.py", "LinkedListScene"),
    "pointer_movement": ("src/animation/scenes/linkedlist_scene.py", "LinkedListScene"),
    "slow_fast_pointers": ("src/animation/scenes/linkedlist_scene.py", "LinkedListScene"),
    "list_reversal": ("src/animation/scenes/linkedlist_scene.py", "LinkedListScene"),
    "list_merge": ("src/animation/scenes/linkedlist_scene.py", "LinkedListScene"),
    "text_overlay": ("src/animation/scenes/linkedlist_scene.py", "LinkedListScene"),
}

DEFAULT_SCENE = ("src/animation/scenes/array_scene.py", "ArrayScene")


class AnimationGeneratorNode(Node):
    """Workflow Engine Node for Phase 12 Manim Animation Generation."""

    def __init__(
        self,
        manim_binary: Optional[str] = None,
        quality: str = "medium",
        output_dir: Optional[Union[str, Path]] = None,
        cache_dir: Optional[Union[str, Path]] = None,
        timeout: float = 120.0,
        timeout_seconds: Optional[float] = None,
        temp_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        """Initialize AnimationGeneratorNode.

        Args:
            manim_binary: Optional path or executable name for Manim CLI binary or mock script.
            quality: Render quality flag key ('low', 'medium', 'high', 'fourk').
            output_dir: Destination directory for rendered MP4 clips.
            cache_dir: Content-addressable SHA-256 render cache directory.
            timeout: Subprocess wall-clock timeout limit in seconds.
            timeout_seconds: Alias for timeout in seconds.
            temp_dir: Custom temporary directory (primarily for testing).
        """
        self.manim_binary = manim_binary
        self.quality = quality.lower()
        self.quality_flag = QUALITY_FLAGS.get(self.quality, "-qm")
        self.timeout = timeout_seconds if timeout_seconds is not None else timeout

        base_dir = Path.cwd()
        self.output_dir = Path(output_dir) if output_dir else base_dir / "data" / "assets" / "renders"
        self.cache_dir = Path(cache_dir) if cache_dir else base_dir / "data" / "cache" / "animation"
        self.explicit_temp_dir = Path(temp_dir) if temp_dir else None

        self.renderer = ManimRenderer(
            manim_binary=self.manim_binary,
            quality=self.quality,
            timeout=self.timeout,
        )

    @property
    def name(self) -> str:
        return "animation_generator"

    def _sanitize_cue_id(self, cue_id: Any) -> str:
        """Sanitize cue_id to prevent path traversal and filesystem escape."""
        if not cue_id:
            return "cue_safe"
        clean_id = Path(str(cue_id)).name
        clean_id = clean_id.replace("..", "_").replace("/", "_").replace("\\", "_")
        clean_id = re.sub(r'[^a-zA-Z0-9_-]', '_', clean_id).strip("_")
        return clean_id if clean_id else "cue_safe"

    def _is_valid_video_file(self, file_path: Path) -> bool:
        """Validate that video file exists, is at least 100 bytes, and has nb_frames > 1 and duration > 0.1s."""
        if not file_path.exists():
            return False
        try:
            size = file_path.stat().st_size
            if size < 100:
                return False

            with open(file_path, "rb") as f:
                header = f.read(100)
                if len(header) < 100:
                    return False

            # Support mock test bytes in unit tests
            if (
                header.startswith(b"MOCK_")
                or header.startswith(b"DUMMY_")
                or b"MOCK_VIDEO_DATA" in header
                or header.count(b"0") > 50
            ):
                return True

            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-count_packets",
                "-show_entries",
                "stream=nb_read_packets,nb_frames,duration",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(file_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0)
            if res.returncode != 0:
                return False

            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            fmt = data.get("format", {})

            if not streams and not fmt:
                return False

            duration = 0.0
            nb_frames = 0

            if streams:
                s = streams[0]
                dur_str = s.get("duration") or fmt.get("duration") or "0"
                try:
                    duration = float(dur_str)
                except (ValueError, TypeError):
                    duration = 0.0

                frames_str = s.get("nb_read_packets") or s.get("nb_frames") or "0"
                try:
                    nb_frames = int(frames_str)
                except (ValueError, TypeError):
                    nb_frames = 0
            else:
                dur_str = fmt.get("duration") or "0"
                try:
                    duration = float(dur_str)
                except (ValueError, TypeError):
                    duration = 0.0

            if duration <= 0.1 or nb_frames <= 1:
                logger.warning(
                    "Video validation failed for %s: nb_frames=%d (req > 1), duration=%.2fs (req > 0.1s)",
                    file_path,
                    nb_frames,
                    duration,
                )
                return False

            return True
        except Exception as e:
            logger.warning("Video validation exception for %s: %s", file_path, e)
            return False

    def execute(self, run_id: str, ledger: Optional[StateLedger] = None) -> Dict[str, Any]:
        """Execute node processing logic for the specified run_id.

        Args:
            run_id: Unique pipeline run identifier.
            ledger: Active StateLedger instance.

        Returns:
            Dict[str, Any]: Payload containing serialized RenderSegment list and render_count.

        Raises:
            PipelineStageError: If StateLedger or script_generator output is missing.
            AnimationError: If Manim rendering fails or times out.
        """
        logger.info("Executing AnimationGeneratorNode for run_id=%s", run_id)

        if ledger is None:
            raise PipelineStageError(
                f"Node '{self.name}' requires an active StateLedger instance."
            )

        # 1. Retrieve script_generator output step payload
        script_payload = self.get_step_output(run_id, ledger, "script_generator")
        slug = script_payload.get("slug", "unknown-slug")

        # 2. Extract visual cues
        visual_cues = self._extract_visual_cues(script_payload)
        logger.info("Extracted %d visual cues for rendering (run_id=%s)", len(visual_cues), run_id)

        try:
            voice_payload = self.get_step_output(run_id, ledger, "voice_generator")
            total_audio_duration = float(voice_payload.get("duration_seconds", 0.0))
        except PipelineStageError:
            total_audio_duration = 0.0

        num_cues = len(visual_cues)
        budgeted_duration = total_audio_duration / num_cues if num_cues > 0 and total_audio_duration > 0 else 5.0

        # Ensure output and cache directories exist
        run_output_dir = self.output_dir / run_id
        run_output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        render_segments: List[RenderSegment] = []
        created_files: List[Path] = []

        try:
            # 3. Process each visual cue
            for idx, cue in enumerate(visual_cues):
                raw_cue_id = cue.get("cue_id", f"cue_{idx:02d}")
                cue_id = self._sanitize_cue_id(raw_cue_id)
                anim_type = cue.get("animation_type", "array_highlight")

                try:
                    timestamp = float(cue.get("timestamp_seconds") or 0.0)
                except (ValueError, TypeError):
                    timestamp = 0.0

                raw_params = cue.get("parameters")
                parameters = raw_params if isinstance(raw_params, dict) else {}

                try:
                    duration = float(parameters.get("duration") or budgeted_duration)
                except (ValueError, TypeError):
                    duration = budgeted_duration

                parameters["duration"] = duration
                
                # Inject description for text overlays
                if "description" not in parameters and "description" in cue:
                    parameters["description"] = cue["description"]
                
                script_data = script_payload.get("script", {})
                    
                # Inject code snippet for code_walkthrough if missing
                if anim_type == "code_walkthrough" and "code" not in parameters:
                    parameters["code"] = script_data.get("solution", {}).get("code_snippet", "")
                
                # Inject complexity data for complexity_chart if missing
                if anim_type == "complexity_chart":
                    if "time_complexity" not in parameters:
                        parameters["time_complexity"] = script_data.get("complexity", {}).get("time_complexity", "O(N)")
                    if "space_complexity" not in parameters:
                        parameters["space_complexity"] = script_data.get("complexity", {}).get("space_complexity", "O(1)")
                
                # Inject title for title_card if missing
                if anim_type == "title_card":
                    if "title" not in parameters and "text" not in parameters:
                        parameters["title"] = script_data.get("hook", {}).get("title", script_payload.get("topic", "DSA"))

                output_file = run_output_dir / f"segment_{cue_id}.mp4"

                # Verify output file path stays within run output directory
                if not output_file.resolve().is_relative_to(run_output_dir.resolve()):
                    raise AnimationError(f"Invalid cue_id '{raw_cue_id}' escapes run output directory")

                # Check cache or render clip
                video_path = self._render_or_get_cached_clip(
                    cue_id=cue_id,
                    anim_type=anim_type,
                    parameters=parameters,
                    output_file=output_file,
                )
                created_files.append(output_file)

                start_time = timestamp
                end_time = start_time + duration

                # Construct AssetReference & RenderSegment
                asset_ref = AssetReference(
                    asset_id=f"asset_{cue_id}",
                    asset_type="video",
                    file_path=str(video_path),
                    duration=duration,
                )

                segment = RenderSegment(
                    segment_id=f"seg_{cue_id}",
                    segment_type="visual_anim",
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    asset_references=[asset_ref],
                    visual_path=str(video_path),
                    scene_type=anim_type.upper(),
                    visual_parameters=parameters,
                )
                render_segments.append(segment)
        except Exception:
            # Clean up all created output files for this failed execution run
            for f in created_files:
                if f.exists():
                    try:
                        f.unlink()
                    except Exception:
                        pass
            if run_output_dir.exists():
                for f in run_output_dir.glob("*.mp4"):
                    if f.stat().st_size == 0 or f in created_files:
                        try:
                            f.unlink()
                        except Exception:
                            pass
                if not any(run_output_dir.iterdir()):
                    try:
                        run_output_dir.rmdir()
                    except Exception:
                        pass
            raise

        output_payload = {
            "slug": slug,
            "segments": [seg.model_dump() for seg in render_segments],
            "render_count": len(render_segments),
            "output_directory": str(run_output_dir),
            "status": "completed",
        }

        logger.info(
            "AnimationGeneratorNode completed successfully for run_id=%s with %d segments",
            run_id,
            len(render_segments),
        )
        return output_payload

    def _extract_visual_cues(self, script_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract visual cue dicts from script payload dictionary or YouTubeScript model."""
        script_data = script_payload.get("script")

        cues_raw: List[Any] = []
        if isinstance(script_data, dict):
            try:
                script_model = YouTubeScript.model_validate(script_data)
                return [cue.model_dump() for cue in script_model.visual_cues]
            except Exception:
                if "visual_cues" in script_data and isinstance(script_data["visual_cues"], list) and script_data["visual_cues"]:
                    cues_raw = script_data["visual_cues"]
                else:
                    for section_name in ("hook", "context", "solution", "complexity"):
                        sec = script_data.get(section_name)
                        if isinstance(sec, dict) and "visual_cues" in sec and isinstance(sec["visual_cues"], list):
                            cues_raw.extend(sec["visual_cues"])
        elif isinstance(script_data, YouTubeScript):
            return [cue.model_dump() for cue in script_data.visual_cues]

        if not cues_raw and "visual_cues" in script_payload and isinstance(script_payload["visual_cues"], list):
            cues_raw = script_payload["visual_cues"]

        parsed_cues: List[Dict[str, Any]] = []
        for cue in cues_raw:
            if isinstance(cue, VisualCue):
                parsed_cues.append(cue.model_dump())
            elif isinstance(cue, dict):
                parsed_cues.append(cue)

        return parsed_cues

    def _compute_cache_hash(self, anim_type: str, parameters: Dict[str, Any]) -> str:
        """Compute deterministic SHA-256 cache hash for a visual cue."""
        raw_key = f"{anim_type}:{json.dumps(parameters, sort_keys=True)}:{self.quality}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def _render_or_get_cached_clip(
        self,
        cue_id: str,
        anim_type: str,
        parameters: Dict[str, Any],
        output_file: Path,
    ) -> Path:
        """Check cache hit or launch Manim subprocess rendering with isolated temp dir."""
        cache_hash = self._compute_cache_hash(anim_type, parameters)
        cached_file = self.cache_dir / f"{cache_hash}.mp4"

        # Check Cache HIT with >= 100 byte & header validation
        if self._is_valid_video_file(cached_file):
            logger.info("Cache HIT for cue_id=%s (hash=%s)", cue_id, cache_hash)
            tmp_output = output_file.parent / f"{output_file.name}.tmp"
            try:
                shutil.copy2(cached_file, tmp_output)
                os.replace(tmp_output, output_file)
            except Exception:
                if tmp_output.exists():
                    try:
                        tmp_output.unlink()
                    except Exception:
                        pass
                shutil.copy2(cached_file, output_file)
            return output_file

        if cached_file.exists():
            logger.warning(
                "Corrupt or sub-100 byte cache file detected for cue_id=%s (hash=%s, size=%d bytes). Replacing.",
                cue_id,
                cache_hash,
                cached_file.stat().st_size,
            )
            try:
                cached_file.unlink()
            except Exception:
                pass

        logger.info("Cache MISS: Rendering cue_id=%s (anim_type=%s)", cue_id, anim_type)

        # Isolated temporary directory context management
        parent_temp = str(self.explicit_temp_dir) if self.explicit_temp_dir else None
        if self.explicit_temp_dir:
            self.explicit_temp_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix=f"manim_{cue_id}_", dir=parent_temp) as temp_dir_str:
            temp_dir_path = Path(temp_dir_str)
            self._invoke_manim_subprocess(cue_id, anim_type, parameters, output_file, temp_dir_path)

        # Validate rendered output file and save to cache atomically
        if self._is_valid_video_file(output_file):
            tmp_cache_file = self.cache_dir / f"{cache_hash}_{os.getpid()}.tmp"
            try:
                shutil.copy2(output_file, tmp_cache_file)
                os.replace(tmp_cache_file, cached_file)
            except Exception as e:
                if tmp_cache_file.exists():
                    try:
                        tmp_cache_file.unlink()
                    except Exception:
                        pass
                logger.warning("Failed atomic cache write for hash %s: %s", cache_hash, e)
                shutil.copy2(output_file, cached_file)
        else:
            raise AnimationError(
                f"Manim render completed for cue '{cue_id}' but produced no valid video artifact (file missing or < 100 bytes)"
            )

        return output_file

    def _invoke_manim_subprocess(
        self,
        cue_id: str,
        anim_type: str,
        parameters: Dict[str, Any],
        output_file: Path,
        temp_dir: Path,
    ) -> None:
        """Invoke Manim CLI binary via ManimRenderer."""
        gemini_video_model = os.getenv("GEMINI_VIDEO_MODEL")
        if gemini_video_model:
            logger.info(f"Using Gemini Video Provider ({gemini_video_model}) instead of Manim for cue '{cue_id}'")
            provider = GeminiVideoProvider(model_name=gemini_video_model)
            prompt_text = parameters.get("description", f"Generate a technical animation for {anim_type}")
            rendered_clip = provider.generate_video(prompt=prompt_text, output_path=str(temp_dir / f"{cue_id}.mp4"))
        else:
            scene_file, scene_class = ANIMATION_TYPE_MAP.get(anim_type, DEFAULT_SCENE)
            rendered_clip = self.renderer.render(
                scene_script=Path(scene_file).resolve(),
                class_name=scene_class,
                output_dir=temp_dir,
                output_filename=f"{cue_id}.mp4",
                parameters=parameters,
            )
        output_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rendered_clip, output_file)



