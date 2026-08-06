"""Base DSA Scene Class supporting Manim rendering and fallback stub mode."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Graceful Manim Import Fallback
MANIM_AVAILABLE = False
try:
    import manim  # type: ignore # noqa: F401
    from manim import LEFT, UP, DOWN, Scene, Text  # type: ignore

    MANIM_AVAILABLE = True
except ImportError:

    class Scene:  # type: ignore
        """Stub Scene base class when Manim is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def construct(self) -> None:
            pass


from src.animation.theme import DEFAULT_THEME, ThemeColors


class BaseDSAScene(Scene):
    """Abstract Base Class for all DSA Visual Scene Templates."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.theme: ThemeColors = DEFAULT_THEME
        self.params: Dict[str, Any] = {}
        self.load_params_from_json()

    def load_params_from_json(self, json_path: Optional[str] = None) -> Dict[str, Any]:
        """Loads visual cue parameters from a JSON file."""
        candidates = []
        if json_path:
            candidates.append(Path(json_path))
        candidates.extend(
            [
                Path("parameters.json"),
                Path.cwd() / "parameters.json",
            ]
        )

        for path in candidates:
            if path.exists() and path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self.params = json.load(f)
                    logger.debug("Successfully loaded scene parameters from %s", path)
                    break
                except Exception as e:
                    logger.warning("Failed to parse scene parameters from %s: %s", path, e)
        return self.params

    def setup(self) -> None:
        """Manim setup lifecycle hook."""
        if hasattr(super(), "setup"):
            super().setup()
        if not self.params:
            self.load_params_from_json()

    def construct(self) -> None:
        """Standard Manim scene construct method called by Manim CLI."""
        if not self.params:
            self.load_params_from_json()
        self.setup_scene_header()
        self.construct_dsa_animation()

    def render_with_params(self, params: Dict[str, Any]) -> None:
        """Entry point called by dynamic wrapper script to pass parameters."""
        self.params = params
        if MANIM_AVAILABLE:
            self.setup_scene_header()
            self.construct_dsa_animation()
        else:
            logger.info("Manim not installed: Skipping graphical construction.")

    def setup_scene_header(self) -> None:
        """Renders standard scene header title and description if present."""
        if not MANIM_AVAILABLE:
            return
        title_text = self.params.get("title", "")
        desc_text = self.params.get("description", "")
        
        if title_text:
            header = Text(title_text, font_size=28, color=self.theme.PRIMARY_ACCENT)
            header.to_corner(UP + LEFT, buff=0.5)
            self.add(header)
            
        if desc_text:
            import textwrap
            wrapped_desc = "\n".join(textwrap.wrap(desc_text, width=70))
            desc_mob = Text(wrapped_desc, font_size=24, color=self.theme.TEXT_PRIMARY)
            desc_mob.to_edge(DOWN, buff=0.5)
            self.add(desc_mob)

    def construct_dsa_animation(self) -> None:
        """Override in concrete scene subclasses to build visual animations."""
        pass

