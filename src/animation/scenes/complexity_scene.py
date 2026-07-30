"""Big-O Time & Space Complexity Card Scene Template."""

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import DOWN, Text, VGroup  # type: ignore


class ComplexityScene(BaseDSAScene):
    """Visualizes complexity badges (e.g. O(N), O(1)) and growth curves."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        time_comp = self.params.get("time_complexity", "O(N)")
        space_comp = self.params.get("space_complexity", "O(1)")

        t_text = Text(f"Time Complexity: {time_comp}", font_size=32, color=self.theme.HIGHLIGHT)
        s_text = Text(f"Space Complexity: {space_comp}", font_size=32, color=self.theme.PRIMARY_ACCENT)

        card = VGroup(t_text, s_text).arrange(DOWN, buff=0.5)
        card.move_to([0, 0, 0])

        self.play(manim.Write(card))
        self.wait(1)
