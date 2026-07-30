"""Code Walkthrough & Line Highlighting Scene Template."""

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import Code  # type: ignore


class CodeScene(BaseDSAScene):
    """Visualizes syntax-highlighted code blocks with line highlight markers."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        code_str = self.params.get("code", "# DSA Implementation\ndef solve():\n    pass")
        language = self.params.get("language", "python")

        code_block = Code(
            code=code_str,
            tab_width=4,
            background="window",
            language=language,
            font_size=20,
        )
        code_block.move_to([0, 0, 0])
        self.play(manim.Create(code_block))
        self.wait(1)
