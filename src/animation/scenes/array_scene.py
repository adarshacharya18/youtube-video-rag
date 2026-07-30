"""Array & Multi-Pointer Visualization Scene Template."""

from typing import List

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import RIGHT, Square, Text, VGroup  # type: ignore


class ArrayScene(BaseDSAScene):
    """Visualizes 1D Arrays, element highlights, and pointer movements."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        array_data: List[int] = self.params.get("array", [2, 7, 11, 15])
        highlights: List[int] = self.params.get("highlight_indices", [])

        boxes = []
        for i, val in enumerate(array_data):
            color = self.theme.HIGHLIGHT if i in highlights else self.theme.PRIMARY_ACCENT
            box = Square(side_length=1.0, color=color, fill_color=self.theme.CONTAINER_BG, fill_opacity=0.8)
            txt = Text(str(val), font_size=24, color=self.theme.TEXT_PRIMARY)
            element = VGroup(box, txt)
            boxes.append(element)

        array_group = VGroup(*boxes).arrange(RIGHT, buff=0.1)
        array_group.move_to([0, 0, 0])

        self.play(manim.Create(array_group))
        self.wait(1)
