"""Title Card Scene Template supporting dynamic inputs, difficulty badges, category tags, and ambient continuous animations."""

import logging
from typing import Any, Dict, List, Optional

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

    class TitleSceneParameters(BaseModel):
        """Pydantic schema for TitleScene parameters."""

        title: str = Field(default="Data Structures & Algorithms", description="Main topic title text")
        subtitle: Optional[str] = Field(default=None, description="Optional subtitle text")
        difficulty: Optional[str] = Field(default=None, description="Difficulty level badge (Easy, Medium, Hard)")
        category: Optional[str] = Field(default=None, description="Category tag (e.g. Sorting Algorithms, Graph Theory)")
        action: str = Field(default="main_title", description="Action mode: main_title, subtitle, difficulty_badge, category_badge, particle_ambient")
        duration: float = Field(default=5.0, description="Total scene animation duration in seconds")
        theme: Optional[str] = Field(default=None, description="Visual theme styling")


if MANIM_AVAILABLE:
    import random
    import manim  # type: ignore
    from manim import (  # type: ignore
        DOWN,
        LEFT,
        ORIGIN,
        RIGHT,
        UP,
        Circle,
        Dot,
        FadeIn,
        RoundedRectangle,
        Text,
        VGroup,
        Write,
        there_and_back,
    )


class TitleScene(BaseDSAScene):
    """Visualizes dynamic centered title cards, difficulty badges, category tags, and background ambient animations."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return

        if PYDANTIC_AVAILABLE:
            self.load_parameters(schema=TitleSceneParameters)

        title_text = self.get_parameter("title", "Data Structures & Algorithms", expected_type=str)
        subtitle_text = self.get_parameter("subtitle", None, expected_type=str)
        difficulty = self.get_parameter("difficulty", None, expected_type=str)
        category = self.get_parameter("category", None, expected_type=str)
        action = self.get_parameter("action", "main_title", expected_type=str)
        duration = float(self.get_parameter("duration", 5.0, expected_type=float))

        if action == "subtitle":
            self.action_subtitle(title_text, subtitle_text or "Algorithm & Data Structure Breakdown", duration)
        elif action == "difficulty_badge":
            self.action_difficulty_badge(title_text, subtitle_text, difficulty or "Medium", duration)
        elif action == "category_badge":
            self.action_category_badge(title_text, category or "Data Structures", duration)
        elif action == "particle_ambient":
            self.action_particle_ambient(title_text, subtitle_text, duration)
        else:
            self.action_main_title(title_text, duration)

    def _create_difficulty_badge(self, diff_str: str) -> Any:
        """Creates a styled pill badge mobject for difficulty rating."""
        diff_upper = diff_str.upper()
        if "EASY" in diff_upper:
            bg_color = "#2ecc71"  # Emerald Green
        elif "HARD" in diff_upper:
            bg_color = "#e74c3c"  # Crimson Red
        else:
            bg_color = "#f39c12"  # Amber Orange

        badge_text = Text(diff_str.capitalize(), font_size=20, color="#ffffff")
        badge_box = RoundedRectangle(
            corner_radius=0.15,
            height=0.45,
            width=badge_text.width + 0.4,
            fill_color=bg_color,
            fill_opacity=0.9,
            stroke_color="#ffffff",
            stroke_width=1,
        )
        badge_text.move_to(badge_box.get_center())
        return VGroup(badge_box, badge_text)

    def _create_category_badge(self, cat_str: str) -> Any:
        """Creates a styled category pill badge mobject."""
        cat_text = Text(cat_str.upper(), font_size=18, color=self.theme.SECONDARY_ACCENT)
        cat_box = RoundedRectangle(
            corner_radius=0.1,
            height=0.4,
            width=cat_text.width + 0.35,
            fill_color=self.theme.CONTAINER_BG,
            fill_opacity=0.8,
            stroke_color=self.theme.SECONDARY_ACCENT,
            stroke_width=1.5,
        )
        cat_text.move_to(cat_box.get_center())
        return VGroup(cat_box, cat_text)

    def action_main_title(self, title_text: str, duration: float) -> None:
        """Renders main title text with continuous ambient pulse."""
        intro_time = self.get_step_runtime(total_steps=1, default_step_time=1.0, min_step_time=0.6, max_step_time=1.2)
        remaining_time = max(0.5, duration - intro_time)

        title = Text(title_text, font_size=44, color=self.theme.TEXT_PRIMARY)
        title.move_to(ORIGIN)

        self.play(Write(title), run_time=intro_time)
        self.animate_continuous_wait(duration=remaining_time, pulse_targets=[title], mode="pulse", scale_factor=1.04)

    def action_subtitle(self, title_text: str, subtitle_text: str, duration: float) -> None:
        """Renders main title text with subtitle animated below."""
        intro_time = self.get_step_runtime(total_steps=2, default_step_time=0.8, min_step_time=0.5, max_step_time=1.0)
        remaining_time = max(0.5, duration - (intro_time * 2))

        title = Text(title_text, font_size=44, color=self.theme.TEXT_PRIMARY)
        text_sec = getattr(self.theme, "TEXT_SECONDARY", self.theme.PRIMARY_ACCENT)
        subtitle = Text(subtitle_text, font_size=26, color=text_sec)

        title_group = VGroup(title, subtitle).arrange(DOWN, buff=0.4).move_to(ORIGIN)

        self.play(Write(title), run_time=intro_time)
        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=intro_time)
        self.animate_continuous_wait(duration=remaining_time, pulse_targets=[subtitle], mode="opacity", opacity_range=(0.6, 1.0))

    def action_difficulty_badge(self, title_text: str, subtitle_text: Optional[str], difficulty: str, duration: float) -> None:
        """Renders main title, optional subtitle, and difficulty badge."""
        intro_time = self.get_step_runtime(total_steps=3, default_step_time=0.7, min_step_time=0.4, max_step_time=0.9)
        remaining_time = max(0.5, duration - (intro_time * 2))

        title = Text(title_text, font_size=42, color=self.theme.TEXT_PRIMARY)
        badge = self._create_difficulty_badge(difficulty)
        text_sec = getattr(self.theme, "TEXT_SECONDARY", self.theme.PRIMARY_ACCENT)

        if subtitle_text:
            sub = Text(subtitle_text, font_size=24, color=text_sec)
            content = VGroup(title, sub, badge).arrange(DOWN, buff=0.35).move_to(ORIGIN)
        else:
            content = VGroup(title, badge).arrange(DOWN, buff=0.4).move_to(ORIGIN)

        self.play(Write(title), run_time=intro_time)
        self.play(FadeIn(badge, shift=UP * 0.2), run_time=intro_time)
        self.animate_continuous_wait(duration=remaining_time, pulse_targets=[badge], mode="pulse", scale_factor=1.05)

    def action_category_badge(self, title_text: str, category: str, duration: float) -> None:
        """Renders category tag above main title."""
        intro_time = self.get_step_runtime(total_steps=2, default_step_time=0.8, min_step_time=0.5, max_step_time=1.0)
        remaining_time = max(0.5, duration - (intro_time * 2))

        title = Text(title_text, font_size=44, color=self.theme.TEXT_PRIMARY)
        cat_badge = self._create_category_badge(category)

        content = VGroup(cat_badge, title).arrange(DOWN, buff=0.4).move_to(ORIGIN)

        self.play(FadeIn(cat_badge, shift=DOWN * 0.2), run_time=intro_time)
        self.play(Write(title), run_time=intro_time)
        self.animate_continuous_wait(duration=remaining_time, pulse_targets=[cat_badge], mode="pulse", scale_factor=1.03)

    def action_particle_ambient(self, title_text: str, subtitle_text: Optional[str], duration: float) -> None:
        """Renders main title with continuous ambient background particles."""
        intro_time = self.get_step_runtime(total_steps=1, default_step_time=1.0, min_step_time=0.6, max_step_time=1.2)
        remaining_time = max(0.5, duration - intro_time)

        particles = VGroup()
        random.seed(42)
        for _ in range(12):
            x = random.uniform(-6, 6)
            y = random.uniform(-3.5, 3.5)
            r = random.uniform(0.08, 0.25)
            p = Dot(point=[x, y, 0], radius=r, color=self.theme.PRIMARY_ACCENT)
            p.set_fill(opacity=random.uniform(0.15, 0.4))
            particles.add(p)

        title = Text(title_text, font_size=46, color=self.theme.TEXT_PRIMARY)
        text_sec = getattr(self.theme, "TEXT_SECONDARY", self.theme.PRIMARY_ACCENT)
        if subtitle_text:
            sub = Text(subtitle_text, font_size=24, color=text_sec)
            main_group = VGroup(title, sub).arrange(DOWN, buff=0.35).move_to(ORIGIN)
        else:
            main_group = VGroup(title).move_to(ORIGIN)

        self.play(FadeIn(particles), Write(title), run_time=intro_time)

        particle_anims = [
            p.animate.shift(UP * 0.3 * random.choice([1, -1]) + RIGHT * 0.2 * random.choice([1, -1]))
            for p in particles
        ]
        particle_anims.append(title.animate.scale(1.03))

        if there_and_back:
            self.play(*particle_anims, run_time=remaining_time, rate_func=there_and_back)
        else:
            self.play(*particle_anims, run_time=remaining_time)
