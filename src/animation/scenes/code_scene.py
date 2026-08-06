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

        highlight_lines = self.params.get("highlight_lines", [])
        lines_str = self.params.get("lines")
        if not highlight_lines and lines_str and isinstance(lines_str, str):
            try:
                if "-" in lines_str:
                    start, end = map(int, lines_str.split("-"))
                    highlight_lines = list(range(start, end + 1))
                else:
                    highlight_lines = [int(lines_str)]
            except Exception:
                pass

        intro_time = min(1.0, duration * 0.2)
        rem_time = max(0.1, duration - intro_time)

        self.play(manim.Create(code_block), run_time=intro_time)

        # Highlight lines if requested
        if highlight_lines and isinstance(highlight_lines, list):
            step_time = rem_time / len(highlight_lines)
            cursor = None
            for line_num in highlight_lines:
                idx = max(0, min(int(line_num) - 1, len(code_block.code) - 1))
                target_line = code_block.code[idx]
                
                if cursor is None:
                    cursor = SurroundingRectangle(target_line, color=self.theme.HIGHLIGHT, buff=0.05)
                    self.play(manim.Create(cursor), run_time=min(0.5, step_time))
                    self.wait(max(0.1, step_time - 0.5))
                else:
                    self.play(cursor.animate.move_to(target_line).stretch_to_fit_width(target_line.width + 0.1).stretch_to_fit_height(target_line.height + 0.1), run_time=min(0.5, step_time))
                    self.wait(max(0.1, step_time - 0.5))
        else:
            # Fallback: Just highlight the whole block if no specific lines provided
            cursor = SurroundingRectangle(code_block, color=self.theme.HIGHLIGHT, buff=0.1)
            self.play(manim.Create(cursor), run_time=min(0.5, rem_time))
            self.wait(rem_time - min(0.5, rem_time))
