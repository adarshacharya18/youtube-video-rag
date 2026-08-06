"""LinkedList Node & Pointer Connection Scene Template."""

import math

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import DOWN, RIGHT, Arrow, Rectangle, Text, ValueTracker, VGroup  # type: ignore


class LinkedListScene(BaseDSAScene):
    """Visualizes linked nodes connected via next arrows."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        nodes_data = self.params.get("nodes", [10, 20, 30])
        duration: float = float(self.params.get("duration", 5.0))

        elements = []
        node_groups = []
        for i, val in enumerate(nodes_data):
            rect = Rectangle(width=1.2, height=0.8, color=self.theme.PRIMARY_ACCENT)
            txt = Text(str(val), font_size=22, color=self.theme.TEXT_PRIMARY)
            node_group = VGroup(rect, txt)
            elements.append(node_group)
            node_groups.append(node_group)
            if i < len(nodes_data) - 1:
                arrow = Arrow(start=RIGHT * 0, end=RIGHT * 0.8, color=self.theme.HIGHLIGHT)
                elements.append(arrow)

        chain = VGroup(*elements).arrange(RIGHT, buff=0.1)
        chain.move_to([0, 0, 0])

        pointer = Arrow(start=DOWN * 0.6, end=DOWN * 0.1, color=self.theme.HIGHLIGHT)
        pointer.move_to(node_groups[0].get_bottom() + DOWN * 0.4)

        intro_time = min(1.0, duration * 0.2)
        rem_time = max(0.1, duration - intro_time)
        step2_time = min(0.5, rem_time * 0.2)
        wait_time = max(0.1, rem_time - step2_time)

        self.play(manim.Create(chain), run_time=intro_time)
        self.play(manim.Create(pointer), run_time=step2_time)

        # Deterministic pointer traversal using standard .animate syntax
        if len(node_groups) > 1:
            step_time = wait_time / (len(node_groups) - 1)
            for i in range(1, len(node_groups)):
                target_pos = node_groups[i].get_bottom() + DOWN * 0.4
                self.play(
                    pointer.animate.move_to(target_pos),
                    run_time=step_time,
                    rate_func=manim.smooth
                )
        else:
            self.wait(wait_time)
