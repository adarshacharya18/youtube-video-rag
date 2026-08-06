"""Big-O Time & Space Complexity Card Scene Template."""

import math

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import DOWN, SurroundingRectangle, Text, ValueTracker, VGroup  # type: ignore


class ComplexityScene(BaseDSAScene):
    """Visualizes complexity badges (e.g. O(N), O(1)) and growth curves."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        time_comp = self.params.get("time_complexity", "O(N)")
        space_comp = self.params.get("space_complexity", "O(1)")
        duration: float = float(self.params.get("duration", 5.0))

        t_text = Text(f"Time Complexity: {time_comp}", font_size=32, color=self.theme.HIGHLIGHT)
        s_text = Text(f"Space Complexity: {space_comp}", font_size=32, color=self.theme.PRIMARY_ACCENT)

        card = VGroup(t_text, s_text).arrange(DOWN, buff=0.5)
        card.move_to([0, 0, 0])

        border = SurroundingRectangle(card, color=self.theme.HIGHLIGHT, buff=0.3)

        intro_time = min(1.0, duration * 0.2)
        rem_time = max(0.1, duration - intro_time)
        step2_time = min(0.5, rem_time * 0.2)
        wait_time = max(0.1, rem_time - step2_time)

        self.play(manim.Write(card), run_time=intro_time)
        self.play(manim.Create(border), run_time=step2_time)

        # Deterministic wait replacing broken dt updater


        self.wait(wait_time)
