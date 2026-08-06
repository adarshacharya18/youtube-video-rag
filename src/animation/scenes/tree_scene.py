"""Binary Tree Traversal Scene Template."""

import math

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import Circle, Text, ValueTracker, VGroup  # type: ignore


class TreeScene(BaseDSAScene):
    """Visualizes hierarchical binary tree nodes and traversal order."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        root_val = self.params.get("root", 1)
        duration: float = float(self.params.get("duration", 5.0))

        c = Circle(radius=0.5, color=self.theme.HIGHLIGHT, fill_color=self.theme.CONTAINER_BG, fill_opacity=0.8)
        t = Text(str(root_val), font_size=24, color=self.theme.TEXT_PRIMARY)
        node = VGroup(c, t).move_to([0, 1.5, 0])

        pulse_ring = Circle(radius=0.6, color=self.theme.SECONDARY_ACCENT)
        pulse_ring.move_to(node.get_center())

        intro_time = min(1.0, duration * 0.2)
        rem_time = max(0.1, duration - intro_time)
        step2_time = min(0.5, rem_time * 0.2)
        wait_time = max(0.1, rem_time - step2_time)

        self.play(manim.Create(node), run_time=intro_time)
        self.play(manim.Create(pulse_ring), run_time=step2_time)

        # Deterministic wait replacing broken dt updater


        self.wait(wait_time)
