"""Title Card Scene Template."""

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim
    from manim import Text, VGroup

class TitleScene(BaseDSAScene):
    """Visualizes a centered title card for introductions."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
            
        title_text = self.params.get("title") or self.params.get("text") or "Data Structures & Algorithms"
        duration = float(self.params.get("duration", 5.0))
        
        # Apple Mac style presentation for the title
        title = Text(title_text, font_size=48, color=self.theme.TEXT_PRIMARY)
        
        intro_time = min(1.0, duration * 0.2)
        wait_time = max(0.1, duration - intro_time)
        
        self.play(manim.Write(title), run_time=intro_time)
        self.wait(wait_time)
