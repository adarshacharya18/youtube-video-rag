"""Stack & Queue Operation Container Scene Template."""

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import UP, Rectangle, Text, VGroup  # type: ignore


class StackQueueScene(BaseDSAScene):
    """Visualizes push/pop stack or enqueue/dequeue queue elements."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        elements = self.params.get("elements", ["A", "B", "C"])
        boxes = [
            VGroup(
                Rectangle(width=2.0, height=0.6, color=self.theme.PRIMARY_ACCENT),
                Text(str(e), font_size=20),
            )
            for e in elements
        ]
        stack_group = VGroup(*boxes).arrange(UP, buff=0.1)
        stack_group.move_to([0, 0, 0])
        self.play(manim.Create(stack_group))
        self.wait(1)
