"""Code Walkthrough, Line Highlighting, and Live Variable Watcher Scene Renderer."""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

logger = logging.getLogger(__name__)

# Optional Pydantic Import
try:
    from pydantic import BaseModel, Field

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = Any  # type: ignore


if PYDANTIC_AVAILABLE:

    class CodeSceneParameters(BaseModel):
        """Pydantic schema for CodeScene parameters."""

        code: str = Field(default="# DSA Implementation\ndef solve():\n    pass", description="Source code text")
        language: str = Field(default="python", description="Programming language syntax")
        highlight_lines: Optional[Union[List[int], str, int]] = Field(default=None, description="Line numbers to highlight")
        variables: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(default=None, description="Variable watcher dictionary/steps")
        captions: Optional[Union[List[str], Dict[int, str]]] = Field(default=None, description="Execution step captions")
        action: str = Field(default="default_action", description="Action mode")
        duration: float = Field(default=5.0, description="Scene duration in seconds")


if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import (  # type: ignore
        DOWN,
        LEFT,
        ORIGIN,
        RIGHT,
        UP,
        Code,
        Create,
        FadeIn,
        ReplacementTransform,
        RoundedRectangle,
        SurroundingRectangle,
        Text,
        VGroup,
        config,
    )


class CodeScene(BaseDSAScene):
    """Visualizes syntax-highlighted code blocks with line execution focus,
    live Variable Watcher side panel, natural language captions, and continuous ambient animation.
    """

    def _parse_highlight_lines(self) -> List[int]:
        """Extracts and parses highlight line numbers from parameters."""
        raw_lines = self.get_parameter("highlight_lines", None)
        if raw_lines is None:
            raw_lines = self.get_parameter("lines", None)

        if isinstance(raw_lines, list):
            parsed = []
            for item in raw_lines:
                try:
                    parsed.append(int(item))
                except (ValueError, TypeError):
                    pass
            return parsed
        elif isinstance(raw_lines, (int, float)):
            return [int(raw_lines)]
        elif isinstance(raw_lines, str):
            clean_str = raw_lines.strip()
            if "-" in clean_str:
                parts = clean_str.split("-")
                if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                    start, end = int(parts[0]), int(parts[1])
                    return list(range(start, end + 1))
            elif clean_str.isdigit():
                return [int(clean_str)]
        return []

    def _parse_variables(self) -> Dict[str, Any]:
        """Extracts variable watcher state dictionary from parameters."""
        vars_data = self.get_parameter("variables", None)
        if vars_data is None:
            vars_data = self.get_parameter("variable_states", None)
        if vars_data is None:
            vars_data = self.get_parameter("watch_variables", None)

        if isinstance(vars_data, dict):
            return vars_data
        elif isinstance(vars_data, list) and len(vars_data) > 0:
            if isinstance(vars_data[0], dict):
                return vars_data[0]
        return {}

    def _parse_captions(self) -> List[str]:
        """Extracts step captions from parameters."""
        captions = self.get_parameter("captions", None)
        if captions is None:
            captions = self.get_parameter("explanations", None)
        if captions is None:
            captions = self.get_parameter("step_captions", None)

        if isinstance(captions, list):
            return [str(c) for c in captions]
        elif isinstance(captions, str):
            return [captions]
        elif isinstance(captions, dict):
            sorted_keys = sorted(captions.keys())
            return [str(captions[k]) for k in sorted_keys]
        return []

    def _build_variable_panel(self, variables: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Constructs a styled Variable Watcher side panel mobject."""
        box_width = 3.6
        box_height = 4.5
        container = RoundedRectangle(
            corner_radius=0.15,
            height=box_height,
            width=box_width,
            color=self.theme.BORDER,
            fill_color=self.theme.CONTAINER_BG,
            fill_opacity=0.9,
            stroke_width=1.5,
        )

        panel_title = Text("VARIABLE WATCHER", font_size=16, color=self.theme.PRIMARY_ACCENT)
        panel_title.move_to(container.get_top() + DOWN * 0.35)

        entries = VGroup()
        text_map = {}
        for var_name, var_val in variables.items():
            entry_str = f"{var_name} = {var_val}"
            txt = Text(entry_str, font_size=15, color=self.theme.TEXT_PRIMARY)
            entries.add(txt)
            text_map[str(var_name)] = txt

        if len(entries) > 0:
            entries.arrange(DOWN, aligned_edge=LEFT, buff=0.25)
            entries.move_to(container.get_center() + DOWN * 0.2)
            panel_group = VGroup(container, panel_title, entries)
        else:
            panel_group = VGroup(container, panel_title)

        panel_group.to_edge(RIGHT, buff=0.5)
        return panel_group, text_map

    def _build_caption_bar(self) -> Tuple[Any, Any]:
        """Constructs a styled execution caption bar at bottom of screen."""
        box_width = 12.0
        box_height = 0.7
        container = RoundedRectangle(
            corner_radius=0.1,
            height=box_height,
            width=box_width,
            color=self.theme.PRIMARY_ACCENT,
            fill_color=self.theme.CONTAINER_BG,
            fill_opacity=0.9,
            stroke_width=1.0,
        )
        container.to_edge(DOWN, buff=0.4)

        caption_text = Text("Executing code walkthrough...", font_size=15, color=self.theme.TEXT_PRIMARY)
        caption_text.move_to(container.get_center())
        return container, caption_text

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return

        if PYDANTIC_AVAILABLE:
            self.load_parameters(schema=CodeSceneParameters)

        code_str = self.get_parameter("code", "# DSA Implementation\ndef solve():\n    pass", expected_type=str)
        language = self.get_parameter("language", "python", expected_type=str)
        duration = float(self.get_parameter("duration", 5.0, expected_type=float))
        action = self.get_parameter("action", "default_action", expected_type=str)

        highlight_lines = self._parse_highlight_lines()
        variables_data = self._parse_variables()
        captions_data = self._parse_captions()

        code_block = Code(
            code_string=code_str,
            tab_width=4,
            background="window",
            language=language,
        )

        total_lines = len(code_str.split("\n"))
        has_variables = bool(variables_data) or action == "variable_watcher"
        should_scroll = total_lines > 15 and bool(highlight_lines)

        # Screen Layout
        if has_variables:
            code_block.to_edge(LEFT, buff=0.5)
            if code_block.height > config.frame_height - 2.5:
                code_block.scale_to_fit_height(config.frame_height - 2.5)
                code_block.to_edge(LEFT, buff=0.5)
        else:
            if should_scroll:
                code_block.to_edge(UP, buff=0.8)
            else:
                code_block.move_to(ORIGIN)
                if code_block.height > config.frame_height - 2.5:
                    code_block.scale_to_fit_height(config.frame_height - 2.5)
                    code_block.to_edge(UP, buff=0.8)

        # Variable Watcher & Caption Bar
        var_panel, var_text_map = self._build_variable_panel(variables_data) if has_variables else (None, {})
        caption_box, caption_text = self._build_caption_bar()

        # Intro Animation
        intro_time = min(1.0, duration * 0.2)
        intro_anims = [Create(code_block)]
        if var_panel is not None:
            intro_anims.append(FadeIn(var_panel))
        intro_anims.append(FadeIn(caption_box))
        intro_anims.append(FadeIn(caption_text))

        self.play(*intro_anims, run_time=intro_time)

        # Access line mobjects safely
        code_lines = getattr(code_block, "code_lines", getattr(code_block, "code", []))
        num_available_lines = len(code_lines) if hasattr(code_lines, "__len__") else 1

        # Execution Line Walkthrough
        if highlight_lines and num_available_lines > 0:
            num_steps = len(highlight_lines)
            step_time = self.get_step_runtime(
                total_steps=num_steps,
                default_step_time=1.0,
                min_step_time=0.4,
                max_step_time=2.5,
                target_duration=duration - intro_time,
            )

            cursor = None
            code_lines_list = code_str.split("\n")

            for step_idx, line_num in enumerate(highlight_lines):
                idx = max(0, min(int(line_num) - 1, num_available_lines - 1))
                target_line = code_lines[idx]

                # Auto-scroll logic if code snippet is long
                scroll_anim = []
                target_center = target_line.get_center()
                if should_scroll:
                    shift_amount = 0.5 - target_line.get_y()
                    if shift_amount > 0:
                        scroll_anim = [code_block.animate.shift(UP * shift_amount)]
                        target_center = target_center + UP * shift_amount

                # Caption Text for step
                if step_idx < len(captions_data):
                    cap_str = captions_data[step_idx]
                elif idx < len(code_lines_list):
                    cap_str = f"Executing line {line_num}: {code_lines_list[idx].strip()}"
                else:
                    cap_str = f"Executing line {line_num}"

                new_caption_text = Text(cap_str, font_size=15, color=self.theme.TEXT_PRIMARY)
                new_caption_text.move_to(caption_box.get_center())

                trans_time = min(0.4, step_time * 0.4)

                if cursor is None:
                    cursor = SurroundingRectangle(
                        target_line,
                        color=self.theme.HIGHLIGHT,
                        stroke_width=2,
                        buff=0.06,
                        fill_color=self.theme.HIGHLIGHT,
                        fill_opacity=0.15,
                    )
                    if scroll_anim:
                        cursor.shift(UP * (0.5 - target_line.get_y()))
                    self.play(
                        Create(cursor),
                        ReplacementTransform(caption_text, new_caption_text),
                        *scroll_anim,
                        run_time=trans_time,
                    )
                else:
                    self.play(
                        cursor.animate.move_to(target_center)
                        .stretch_to_fit_width(target_line.width + 0.12)
                        .stretch_to_fit_height(target_line.height + 0.1),
                        ReplacementTransform(caption_text, new_caption_text),
                        *scroll_anim,
                        run_time=trans_time,
                    )

                caption_text = new_caption_text

                # Anti-freeze continuous ambient wait
                hold_time = max(0.1, step_time - trans_time)
                pulse_targets = [cursor]
                if var_panel is not None:
                    pulse_targets.append(var_panel)

                self.animate_continuous_wait(
                    duration=hold_time,
                    pulse_targets=pulse_targets,
                    mode="pulse",
                    scale_factor=1.02,
                )

        else:
            # Fallback when no highlight_lines specified
            rem_time = max(0.5, duration - intro_time)
            cursor = SurroundingRectangle(
                code_block,
                color=self.theme.HIGHLIGHT,
                buff=0.1,
                fill_color=self.theme.HIGHLIGHT,
                fill_opacity=0.1,
            )
            self.play(Create(cursor), run_time=min(0.5, rem_time))
            hold_time = max(0.1, rem_time - 0.5)
            self.animate_continuous_wait(duration=hold_time, pulse_targets=[cursor, caption_box])
