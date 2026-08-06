"""Code Walkthrough & Line Highlighting Scene Template."""

import math

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import Code, SurroundingRectangle, ValueTracker  # type: ignore


class CodeScene(BaseDSAScene):
    """Visualizes syntax-highlighted code blocks with line highlight markers."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        code_str = self.params.get("code", "# DSA Implementation\ndef solve():\n    pass")
        language = self.params.get("language", "python")
        duration: float = float(self.params.get("duration", 5.0))

        code_block = Code(
            code_string=code_str,
            tab_width=4,
            background="window",
            language=language,
        )
        code_block.move_to([0, 0, 0])

        cursor = SurroundingRectangle(code_block, color=self.theme.HIGHLIGHT, buff=0.1)

        intro_time = min(1.0, duration * 0.2)
        rem_time = max(0.1, duration - intro_time)
        step2_time = min(0.5, rem_time * 0.2)
        wait_time = max(0.1, rem_time - step2_time)

        self.play(manim.Create(code_block), run_time=intro_time)
        self.play(manim.Create(cursor), run_time=step2_time)

        # Deterministic wait replacing broken dt updater


        self.wait(wait_time)
