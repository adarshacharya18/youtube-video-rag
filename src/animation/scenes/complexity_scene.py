"""Big-O Time & Space Complexity Card, Growth Curves, and Tracer Dot Scene Renderer."""

import logging
import math
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

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

    class ComplexitySceneParameters(BaseModel):
        """Pydantic schema for ComplexityScene parameters."""

        time_complexity: str = Field(default="O(N)", description="Time complexity notation (e.g. O(N), O(N log N))")
        space_complexity: str = Field(default="O(1)", description="Space complexity notation (e.g. O(1), O(N))")
        action: str = Field(default="time_complexity", description="Action mode: time_complexity, space_complexity, dual_complexity, growth_curves, curve_tracer, comparison_bars")
        curves: List[str] = Field(default_factory=lambda: ["O(1)", "O(log N)", "O(N)", "O(N^2)"], description="Big-O curves to plot")
        max_n: float = Field(default=10.0, description="Maximum input size N for 2D graphs")
        title: Optional[str] = Field(default=None, description="Optional scene header title")
        duration: float = Field(default=5.0, description="Total scene animation duration in seconds")


if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import (  # type: ignore
        DOWN,
        LEFT,
        ORIGIN,
        RIGHT,
        UP,
        Axes,
        Create,
        Dot,
        FadeIn,
        Line,
        Rectangle,
        ReplacementTransform,
        RoundedRectangle,
        SurroundingRectangle,
        Text,
        ValueTracker,
        VGroup,
        Write,
        config,
    )


class ComplexityScene(BaseDSAScene):
    """Visualizes Big-O complexity cards, 2D growth curves with Axes, tracer dots, and comparative charts."""

    def _get_growth_function(self, notation: str) -> Callable[[float], float]:
        """Maps a Big-O notation string to a scaled mathematical evaluator f(x)."""
        clean = notation.upper().replace(" ", "")
        if "O(1)" in clean:
            return lambda x: 1.0
        elif "O(LOGN)" in clean or "O(LOG2N)" in clean:
            return lambda x: math.log2(max(1.0, x + 1.0)) * 2.0
        elif "O(NLOGN)" in clean:
            return lambda x: (x * math.log2(max(1.0, x + 1.0))) / 3.0
        elif "O(N^2)" in clean or "O(N2)" in clean:
            return lambda x: 0.08 * (x ** 2)
        elif "O(2^N)" in clean or "O(2N)" in clean:
            return lambda x: min(10.0, 0.1 * (2.0 ** min(x, 6.0)))
        elif "O(V+E)" in clean or "O(E+V)" in clean:
            return lambda x: 1.2 * x
        elif "O(N)" in clean or "O(V)" in clean or "O(E)" in clean:
            return lambda x: x
        return lambda x: x

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return

        if PYDANTIC_AVAILABLE:
            self.load_parameters(schema=ComplexitySceneParameters)

        time_comp = self.get_parameter("time_complexity", "O(N)", expected_type=str)
        space_comp = self.get_parameter("space_complexity", "O(1)", expected_type=str)
        action = self.get_parameter("action", "time_complexity", expected_type=str)
        curves_list = self.get_parameter("curves", ["O(1)", "O(N)", "O(N^2)"], expected_type=list)
        duration = float(self.get_parameter("duration", 5.0, expected_type=float))

        if action == "space_complexity":
            self.action_space_complexity(space_comp, duration)
        elif action == "dual_complexity":
            self.action_dual_complexity(time_comp, space_comp, duration)
        elif action == "growth_curves":
            self.action_growth_curves(curves_list, duration)
        elif action == "curve_tracer":
            self.action_curve_tracer(curves_list, duration)
        elif action == "comparison_bars":
            self.action_comparison_bars(curves_list, duration)
        else:
            self.action_time_complexity(time_comp, duration)

    def action_time_complexity(self, time_comp: str, duration: float) -> None:
        """Renders Time Complexity Card with asymptotic trend graphic and ambient pulse."""
        intro_time = self.get_step_runtime(total_steps=1, default_step_time=1.0, min_step_time=0.6, max_step_time=1.2)
        remaining_time = max(0.5, duration - intro_time)

        t_text = Text(f"Time Complexity: {time_comp}", font_size=34, color=self.theme.HIGHLIGHT)
        t_card = RoundedRectangle(
            corner_radius=0.15,
            height=1.5,
            width=max(6.0, t_text.width + 0.8),
            color=self.theme.HIGHLIGHT,
            fill_color=self.theme.CONTAINER_BG,
            fill_opacity=0.9,
            stroke_width=2.0,
        )
        t_text.move_to(t_card.get_center())
        card_group = VGroup(t_card, t_text).move_to(ORIGIN)

        self.play(Write(t_text), Create(t_card), run_time=intro_time)
        self.animate_continuous_wait(duration=remaining_time, pulse_targets=[card_group], mode="pulse", scale_factor=1.03)

    def action_space_complexity(self, space_comp: str, duration: float) -> None:
        """Renders Space Complexity Card with memory allocation graphic."""
        intro_time = self.get_step_runtime(total_steps=1, default_step_time=1.0, min_step_time=0.6, max_step_time=1.2)
        remaining_time = max(0.5, duration - intro_time)

        s_text = Text(f"Space Complexity: {space_comp}", font_size=34, color=self.theme.PRIMARY_ACCENT)
        s_card = RoundedRectangle(
            corner_radius=0.15,
            height=1.5,
            width=max(6.0, s_text.width + 0.8),
            color=self.theme.PRIMARY_ACCENT,
            fill_color=self.theme.CONTAINER_BG,
            fill_opacity=0.9,
            stroke_width=2.0,
        )
        s_text.move_to(s_card.get_center())
        card_group = VGroup(s_card, s_text).move_to(ORIGIN)

        self.play(Write(s_text), Create(s_card), run_time=intro_time)
        self.animate_continuous_wait(duration=remaining_time, pulse_targets=[card_group], mode="pulse", scale_factor=1.03)

    def action_dual_complexity(self, time_comp: str, space_comp: str, duration: float) -> None:
        """Renders side-by-side / stacked Time and Space complexity cards."""
        intro_time = self.get_step_runtime(total_steps=2, default_step_time=0.8, min_step_time=0.5, max_step_time=1.0)
        remaining_time = max(0.5, duration - intro_time)

        t_text = Text(f"Time Complexity: {time_comp}", font_size=30, color=self.theme.HIGHLIGHT)
        s_text = Text(f"Space Complexity: {space_comp}", font_size=30, color=self.theme.PRIMARY_ACCENT)

        card_content = VGroup(t_text, s_text).arrange(DOWN, buff=0.5)
        border = SurroundingRectangle(
            card_content,
            color=self.theme.BORDER,
            buff=0.4,
            corner_radius=0.15,
            fill_color=self.theme.CONTAINER_BG,
            fill_opacity=0.9,
            stroke_width=1.5,
        )
        card_group = VGroup(border, card_content).move_to(ORIGIN)

        self.play(Write(card_content), Create(border), run_time=intro_time)
        self.animate_continuous_wait(duration=remaining_time, pulse_targets=[card_group], mode="pulse", scale_factor=1.03)

    def action_growth_curves(self, curves_list: List[str], duration: float) -> None:
        """Renders 2D Big-O coordinate Axes graph with multiple growth curves."""
        num_curves = len(curves_list)
        step_time = self.get_step_runtime(
            total_steps=num_curves + 1,
            default_step_time=0.8,
            min_step_time=0.4,
            max_step_time=1.2,
            target_duration=duration,
        )

        axes = Axes(
            x_range=[0, 10, 2],
            y_range=[0, 10, 2],
            x_length=6.0,
            y_length=4.2,
            axis_config={"color": self.theme.BORDER, "stroke_width": 2},
        )
        axes.move_to(ORIGIN + DOWN * 0.2)

        text_secondary = getattr(self.theme, "TEXT_SECONDARY", self.theme.BORDER)
        x_label = Text("Input Size (N)", font_size=14, color=text_secondary)
        x_label.next_to(axes.x_axis, DOWN, buff=0.2)
        y_label = Text("Operations", font_size=14, color=text_secondary)
        y_label.next_to(axes.y_axis, LEFT, buff=0.2).rotate(math.pi / 2)

        axes_group = VGroup(axes, x_label, y_label)
        self.play(Create(axes_group), run_time=step_time)

        colors = [
            self.theme.PRIMARY_ACCENT,
            self.theme.HIGHLIGHT,
            self.theme.SECONDARY_ACCENT,
            "#9b59b6",
            "#e74c3c",
        ]

        plot_mobjects = []
        for i, notation in enumerate(curves_list):
            f_eval = self._get_growth_function(notation)
            c_color = colors[i % len(colors)]

            curve = axes.plot(f_eval, x_range=[0, 10], color=c_color, stroke_width=2.5)

            end_val = min(10.0, f_eval(10.0))
            end_point = axes.c2p(10, end_val)
            label = Text(notation, font_size=14, color=c_color)
            label.move_to(end_point + RIGHT * 0.45)

            plot_mobjects.extend([curve, label])
            self.play(Create(curve), FadeIn(label), run_time=step_time)

        elapsed = step_time * (num_curves + 1)
        remaining_time = max(0.5, duration - elapsed)

        pulse_targets = plot_mobjects if plot_mobjects else [axes_group]
        self.animate_continuous_wait(duration=remaining_time, pulse_targets=pulse_targets, mode="pulse", scale_factor=1.02)

    def action_curve_tracer(self, curves_list: List[str], duration: float) -> None:
        """Renders 2D Axes graph with dynamic growth curve tracer dot animation."""
        target_notation = curves_list[0] if curves_list else "O(N)"
        f_eval = self._get_growth_function(target_notation)

        intro_time = min(1.0, duration * 0.2)
        axes = Axes(
            x_range=[0, 10, 2],
            y_range=[0, 10, 2],
            x_length=6.0,
            y_length=4.2,
            axis_config={"color": self.theme.BORDER, "stroke_width": 2},
        )
        axes.move_to(ORIGIN + DOWN * 0.2)

        curve = axes.plot(f_eval, x_range=[0, 10], color=self.theme.HIGHLIGHT, stroke_width=3.0)
        curve_label = Text(f"Growth: {target_notation}", font_size=18, color=self.theme.HIGHLIGHT)
        curve_label.to_corner(UP + RIGHT, buff=0.8)

        self.play(Create(axes), Create(curve), FadeIn(curve_label), run_time=intro_time)

        start_pt = axes.c2p(0, f_eval(0))
        end_pt = axes.c2p(10, min(10.0, f_eval(10)))

        tracer_dot = Dot(point=start_pt, color=self.theme.PRIMARY_ACCENT, radius=0.12)
        readout_box = RoundedRectangle(
            corner_radius=0.1,
            height=0.5,
            width=3.2,
            color=self.theme.PRIMARY_ACCENT,
            fill_color=self.theme.CONTAINER_BG,
            fill_opacity=0.9,
        )
        readout_box.to_corner(UP + LEFT, buff=0.8)
        readout_text = Text("N = 0.0, Ops = 0.0", font_size=14, color=self.theme.TEXT_PRIMARY)
        readout_text.move_to(readout_box.get_center())

        readout_group = VGroup(readout_box, readout_text)

        trace_time = min(2.0, max(1.0, (duration - intro_time) * 0.6))
        self.play(
            Create(tracer_dot),
            FadeIn(readout_group),
            tracer_dot.animate.move_to(end_pt),
            run_time=trace_time,
        )

        remaining_time = max(0.5, duration - intro_time - trace_time)
        self.animate_continuous_wait(
            duration=remaining_time,
            pulse_targets=[tracer_dot, readout_group, curve_label],
            mode="pulse",
            scale_factor=1.04,
        )

    def action_comparison_bars(self, curves_list: List[str], duration: float) -> None:
        """Renders operation growth comparison bars across input sizes."""
        intro_time = min(1.0, duration * 0.2)
        remaining_time = max(0.5, duration - intro_time)

        n_sizes = [10, 50, 100]
        bars = VGroup()
        colors = [self.theme.PRIMARY_ACCENT, self.theme.HIGHLIGHT, self.theme.SECONDARY_ACCENT]

        for idx, n_val in enumerate(n_sizes):
            bar_h = 1.0 + idx * 0.8
            bar = Rectangle(
                height=bar_h,
                width=1.2,
                color=colors[idx % len(colors)],
                fill_color=colors[idx % len(colors)],
                fill_opacity=0.8,
            )
            lbl = Text(f"N={n_val}", font_size=14, color=self.theme.TEXT_PRIMARY)
            lbl.next_to(bar, DOWN, buff=0.15)
            bar_item = VGroup(bar, lbl)
            bars.add(bar_item)

        bars.arrange(RIGHT, buff=0.8).move_to(ORIGIN)

        self.play(Create(bars), run_time=intro_time)
        self.animate_continuous_wait(duration=remaining_time, pulse_targets=[bars], mode="pulse", scale_factor=1.03)
