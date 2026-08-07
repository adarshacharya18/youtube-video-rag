"""Code Walkthrough & Line Highlighting Scene Template."""

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import Code, SurroundingRectangle, config  # type: ignore


class CodeScene(BaseDSAScene):
    """Visualizes syntax-highlighted code blocks with line highlight markers."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        code_str = self.params.get("code", "# DSA Implementation\ndef solve():\n    pass")
        language = self.params.get("language", "python")
        duration: float = float(self.params.get("duration", 5.0))
        # action is read to fulfill the system instruction, though not strictly required here
        action = self.params.get("action", "default_action")

        code_block = Code(
            code_string=code_str,
            tab_width=4,
            background="window",
            language=language,
        )

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

        total_lines = len(code_str.split("\n"))
        should_scroll = total_lines > 15 and bool(highlight_lines)

        if should_scroll:
            # Position at top to start, don't scale down to fit height
            code_block.to_edge(manim.UP, buff=0.8)
        else:
            code_block.move_to([0, 0, 0])
            # Auto-scale if taller than frame
            if code_block.height > config.frame_height - 2.0:
                code_block.scale_to_fit_height(config.frame_height - 2.0)
                code_block.to_edge(manim.UP, buff=0.8)

        intro_time = min(1.0, duration * 0.2)
        rem_time = max(0.1, duration - intro_time)

        self.play(manim.Create(code_block), run_time=intro_time)

        if highlight_lines and isinstance(highlight_lines, list):
            step_time = rem_time / len(highlight_lines)
            cursor = None
            for line_num in highlight_lines:
                idx = max(0, min(int(line_num) - 1, len(code_block.code) - 1))
                target_line = code_block.code[idx]
                
                scroll_anim = []
                target_center = target_line.get_center()
                
                # Check if we should scroll the code block up
                if should_scroll:
                    # If target line is below the center of the screen, shift code block up
                    shift_amount = 0 - target_line.get_y()
                    if shift_amount > 0:
                        scroll_anim = [code_block.animate.shift(manim.UP * shift_amount)]
                        target_center += manim.UP * shift_amount

                if cursor is None:
                    cursor = SurroundingRectangle(target_line, color=self.theme.HIGHLIGHT, buff=0.05)
                    # If we are shifting on the very first line, adjust cursor initial position
                    if scroll_anim:
                        cursor.shift(manim.UP * shift_amount)
                    self.play(manim.Create(cursor), *scroll_anim, run_time=min(0.5, step_time))
                    self.wait(max(0.1, step_time - 0.5))
                else:
                    self.play(
                        cursor.animate.move_to(target_center)
                        .stretch_to_fit_width(target_line.width + 0.1)
                        .stretch_to_fit_height(target_line.height + 0.1),
                        *scroll_anim,
                        run_time=min(0.5, step_time)
                    )
                    self.wait(max(0.1, step_time - 0.5))
        else:
            # Fallback: Just highlight the whole block if no specific lines provided
            cursor = SurroundingRectangle(code_block, color=self.theme.HIGHLIGHT, buff=0.1)
            self.play(manim.Create(cursor), run_time=min(0.5, rem_time))
            self.wait(rem_time - min(0.5, rem_time))
