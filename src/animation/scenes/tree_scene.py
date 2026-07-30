"""Binary Tree Traversal Scene Template."""

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import Circle, Text, VGroup  # type: ignore


class TreeScene(BaseDSAScene):
    """Visualizes hierarchical binary tree nodes and traversal order."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        root_val = self.params.get("root", 1)
        c = Circle(radius=0.5, color=self.theme.HIGHLIGHT)
        t = Text(str(root_val), font_size=24)
        node = VGroup(c, t).move_to([0, 2, 0])
        self.play(manim.Create(node))
        self.wait(1)
