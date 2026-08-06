"""Stack & Queue Operation Container Scene Template."""

import math

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import RIGHT, UP, Arrow, Rectangle, Text, ValueTracker, VGroup  # type: ignore


class StackQueueScene(BaseDSAScene):
    """Visualizes push/pop stack or enqueue/dequeue queue elements."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        elements = self.params.get("elements", ["A", "B", "C"])
        duration: float = float(self.params.get("duration", 5.0))

        boxes = [
            VGroup(
                Rectangle(width=2.0, height=0.6, color=self.theme.PRIMARY_ACCENT),
                Text(str(e), font_size=20),
            )
            for e in elements
        ]
        stack_group = VGroup(*boxes).arrange(UP, buff=0.1)
        stack_group.move_to([0, 0, 0])

        top_arrow = Arrow(start=RIGHT * 1.5, end=RIGHT * 0.5, color=self.theme.HIGHLIGHT)
        top_arrow.move_to(boxes[-1].get_right() + RIGHT * 0.8)

        intro_time = min(1.0, duration * 0.2)
        rem_time = max(0.1, duration - intro_time)
        step2_time = min(0.5, rem_time * 0.2)
        wait_time = max(0.1, rem_time - step2_time)

        self.play(manim.Create(stack_group), run_time=intro_time)
        self.play(manim.Create(top_arrow), run_time=step2_time)

        # Deterministic wait replacing broken dt updater


        self.wait(wait_time)
