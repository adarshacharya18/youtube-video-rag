"""Array & Multi-Pointer Visualization Scene Template."""

import math
from typing import List

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import RIGHT, UP, Arrow, Square, Text, ValueTracker, VGroup  # type: ignore


class ArrayScene(BaseDSAScene):
    """Visualizes 1D Arrays, element highlights, and pointer movements."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        array_data: List[int] = self.params.get("array", [2, 7, 11, 15])
        highlights: List[int] = self.params.get("highlight_indices", [])
        duration: float = float(self.params.get("duration", 5.0))

        boxes = []
        for i, val in enumerate(array_data):
            color = self.theme.HIGHLIGHT if i in highlights else self.theme.PRIMARY_ACCENT
            box = Square(side_length=1.0, color=color, fill_color=self.theme.CONTAINER_BG, fill_opacity=0.8)
            txt = Text(str(val), font_size=24, color=self.theme.TEXT_PRIMARY)
            element = VGroup(box, txt)
            boxes.append(element)

        array_group = VGroup(*boxes).arrange(RIGHT, buff=0.1)
        array_group.move_to([0, 0, 0])

        pointer = Arrow(start=UP * 0.6, end=UP * 0.1, color=self.theme.HIGHLIGHT)
        pointer.move_to(boxes[0].get_top() + UP * 0.4)

        intro_time = min(1.0, duration * 0.2)
        rem_time = max(0.1, duration - intro_time)
        step2_time = min(0.5, rem_time * 0.2)
        wait_time = max(0.1, rem_time - step2_time)

        self.play(manim.Create(array_group), run_time=intro_time)
        self.play(manim.Create(pointer), run_time=step2_time)

        # Deterministic wait replacing broken dt updater


        self.wait(wait_time)
