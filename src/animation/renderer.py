"""Manim Subprocess Execution Manager."""

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.exceptions import AnimationError

logger = logging.getLogger(__name__)

QUALITY_FLAGS = {
    "low": "-ql",
    "480p": "-ql",
    "medium": "-qm",
    "720p": "-qm",
    "high": "-qh",
    "1080p": "-qh",
    "fourk": "-qk",
    "4k": "-qk",
}


class ManimRenderer:
    """Encapsulates subprocess execution of Manim CLI renders."""

    def __init__(
        self,
        manim_binary: Optional[str] = None,
        quality: str = "high",
        timeout: float = 120.0,
    ) -> None:
        self.manim_binary = manim_binary
        self.quality = quality
        self.timeout = timeout

    def render(
        self,
        scene_script: Path,
        class_name: str,
        output_dir: Path,
        output_filename: str = "scene.mp4",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Executes Manim rendering via subprocess."""
        output_dir.mkdir(parents=True, exist_ok=True)
        target_video = output_dir / output_filename

        import os
        env = dict(os.environ)
        if parameters is not None:
            params_file = output_dir / "parameters.json"
            params_file.write_text(json.dumps(parameters, indent=2), encoding="utf-8")
            env["PARAM_FILE"] = str(params_file)

        q_flag = QUALITY_FLAGS.get(self.quality.lower(), "-qm")
        if self.manim_binary:
            if self.manim_binary.endswith(".py"):
                cmd = [
                    sys.executable,
                    self.manim_binary,
                    "render",
                    q_flag,
                    "--format=mp4",
                    "--media_dir",
                    str(output_dir),
                    "-o",
                    output_filename,
                    str(scene_script),
                    class_name,
                ]
            else:
                cmd = [
                    self.manim_binary,
                    "render",
                    q_flag,
                    "--format=mp4",
                    "--media_dir",
                    str(output_dir),
                    "-o",
                    output_filename,
                    str(scene_script),
                    class_name,
                ]
        else:
            cmd = [
                sys.executable,
                "-m",
                "manim",
                "render",
                q_flag,
                "--format=mp4",
                "--media_dir",
                str(output_dir),
                "-o",
                output_filename,
                str(scene_script),
                class_name,
            ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                close_fds=True,
                timeout=self.timeout,
                cwd=str(output_dir),
                env=env,
            )
            if result.returncode != 0:
                raise AnimationError(
                    f"Manim render failed for scene '{class_name}' (exit code {result.returncode}):\n{result.stderr}"
                )
        except subprocess.TimeoutExpired as e:
            raise AnimationError(f"Manim render timed out after {self.timeout}s for scene '{class_name}'") from e
        except AnimationError:
            raise
        except Exception as e:
            raise AnimationError(f"Failed to execute Manim subprocess: {e}") from e

        if target_video.exists() and target_video.stat().st_size > 0:
            return target_video

        rendered_mp4s = [f for f in output_dir.rglob("*.mp4") if f.stat().st_size > 0]
        if rendered_mp4s:
            best_mp4 = sorted(rendered_mp4s, key=lambda f: f.stat().st_size, reverse=True)[0]
            if best_mp4 != target_video:
                shutil.copy2(best_mp4, target_video)
            return target_video

        raise AnimationError(
            f"Manim render completed for scene '{class_name}' but produced no valid video artifact or empty file at {target_video}"
        )

