"""LinkedList Node & Pointer Connection Scene Template."""

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import RIGHT, Arrow, Rectangle, Text, VGroup  # type: ignore


class LinkedListScene(BaseDSAScene):
    """Visualizes linked nodes connected via next arrows."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        nodes_data = self.params.get("nodes", [10, 20, 30])
        elements = []
        for i, val in enumerate(nodes_data):
            rect = Rectangle(width=1.2, height=0.8, color=self.theme.PRIMARY_ACCENT)
            txt = Text(str(val), font_size=22, color=self.theme.TEXT_PRIMARY)
            node_group = VGroup(rect, txt)
            elements.append(node_group)
            if i < len(nodes_data) - 1:
                arrow = Arrow(start=RIGHT * 0, end=RIGHT * 0.8, color=self.theme.HIGHLIGHT)
                elements.append(arrow)

        chain = VGroup(*elements).arrange(RIGHT, buff=0.1)
        chain.move_to([0, 0, 0])
        self.play(manim.Create(chain))
        self.wait(1)
