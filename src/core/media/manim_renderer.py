"""
Manim Renderer Subsystem (Phase 13)

Responsible for translating semantic AnimationPlans into physical Manim Python
code, maintaining a strict rendering queue, handling incremental caching, and
triggering the Manim CLI/API to safely generate MP4 files.
"""
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from src.core.media.animation import RenderedScene
from src.core.script.animation import AnimationPlan, AnimationScene


@dataclass
class ManimConfig:
    """Configuration constraints for the Manim CLI execution."""
    quality: str = "h"          # 'l'=480p15, 'm'=720p30, 'h'=1080p60, 'k'=4k60
    preview_mode: bool = False  # If True, forces 'l' quality and auto-opens the MP4
    cache_dir: str = ".manim_cache"
    output_dir: str = "renders"


class ManimRenderer:
    """
    Manages the lifecycle of Manim scene generation.
    Generates Python scene files from JSON, then queues them for subprocess rendering.
    """
    
    def __init__(self, config: ManimConfig = ManimConfig()):
        self._logger = logging.getLogger(__name__)
        self.config = config
        
        # Rapid Prototyping: Drastically reduce GPU load during testing
        if self.config.preview_mode:
            self._logger.info("Preview Mode Enabled. Forcing 480p 15fps renders.")
            self.config.quality = "l"

    def _generate_scene_file(self, scene_id: int, scene_data: AnimationScene, project_dir: Path) -> Path:
        """
        Translates the semantic JSON into a physical Python file containing a Manim Construct.
        """
        scene_path = project_dir / f"scene_{scene_id}.py"
        self._logger.debug(f"Generating physical Manim code for Scene {scene_id}")
        
        # STUB: In production, we inject a sophisticated Jinja2 template here
        # that maps semantic `VisualObject` structs (from JSON) to physical `VGroup` or `Tex` objects.
        python_code = f"""from manim import *

class AutoScene{scene_id}(Scene):
    def construct(self):
        # Auto-generated from Phase 12 AnimationPlan Payload
        text = Text("Scene {scene_id}")
        self.play(Write(text))
        self.wait(2)
"""
        with open(scene_path, "w") as f:
            f.write(python_code)
            
        return scene_path

    def _execute_manim(self, scene_path: Path, scene_id: int, project_dir: Path) -> Optional[str]:
        """
        Forks a subprocess to execute the Manim CLI, managing caching and error recovery.
        """
        class_name = f"AutoScene{scene_id}"
        # Predict where Manim will output the file
        output_file = project_dir / self.config.cache_dir / "videos" / scene_path.stem / f"{self.config.quality}p60" / f"{class_name}.mp4"
        
        # Incremental Rendering / Caching: Skip if valid file exists
        if output_file.exists():
            self._logger.info(f"Cache hit: Scene {scene_id} already rendered. Skipping GPU execution.")
            return str(output_file)

        command = [
            "manim",
            "render",
            str(scene_path),
            class_name,
            f"-q{self.config.quality}",
            "--media_dir", str(project_dir / self.config.cache_dir)
        ]
        
        if self.config.preview_mode:
            command.append("-p") # Open file via system video player after render
            
        self._logger.info(f"Queueing Subprocess: {' '.join(command)}")
        
        try:
            # We use subprocess.run to isolate the heavy C-level GPU bindings of Cairo
            # entirely away from our primary synchronous Python orchestration loop.
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            self._logger.debug(result.stdout)
            
            return str(output_file)
            
        except subprocess.CalledProcessError as e:
            self._logger.error(f"Manim Subprocess Segfault/Crash for Scene {scene_id}:\n{e.stderr}")
            return None

    def render_queue(self, animation_plan: AnimationPlan, project_root: str) -> List[RenderedScene]:
        """
        Orchestrates the full end-to-end rendering pipeline for all scenes.
        """
        project_dir = Path(project_root)
        project_dir.mkdir(parents=True, exist_ok=True)
        
        rendered_scenes = []
        
        for scene_data in animation_plan.scenes:
            scene_id = scene_data.scene_id
            
            # 1. Generate Python Code
            scene_file = self._generate_scene_file(scene_id, scene_data, project_dir)
            
            # 2. Execute Render Subprocess
            output_mp4 = self._execute_manim(scene_file, scene_id, project_dir)
            
            # 3. Validation & Error Recovery
            if not output_mp4 or not Path(output_mp4).exists():
                self._logger.critical(f"FATAL: Rendering aborted at Scene {scene_id}.")
                raise RuntimeError(f"Video Pipeline crashed. Scene {scene_id} failed to render physically.")
                
            # 4. Construct Persistence Artifact
            rendered_scenes.append(
                RenderedScene(
                    scene_id=scene_id,
                    file_path=output_mp4,
                    duration_sec=0.0, # STUB: Calculate exact duration from FFmpeg headers
                    checksum="sha256_hash",
                    resolution="1080p" if self.config.quality == "h" else "480p",
                    fps=60 if self.config.quality == "h" else 15
                )
            )
            
        return rendered_scenes
