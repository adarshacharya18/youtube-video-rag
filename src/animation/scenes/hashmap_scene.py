"""Hashmap & Bucket Array Scene Template."""

import math
from typing import Any, Dict

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import DOWN, Rectangle, SurroundingRectangle, Text, ValueTracker, VGroup  # type: ignore


class HashmapScene(BaseDSAScene):
    """Visualizes Key-Value slots and hash table operations."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        entries: Dict[str, Any] = self.params.get("entries", {"key1": "val1", "key2": "val2"})
        duration: float = float(self.params.get("duration", 5.0))

        slots = []
        for k, v in entries.items():
            slot_bg = Rectangle(width=3.0, height=0.8, color=self.theme.PRIMARY_ACCENT)
            txt = Text(f"{k} : {v}", font_size=20, color=self.theme.TEXT_PRIMARY)
            slots.append(VGroup(slot_bg, txt))

        table = VGroup(*slots).arrange(DOWN, buff=0.2)
        table.move_to([0, 0, 0])

        active_box = SurroundingRectangle(slots[0], color=self.theme.HIGHLIGHT, buff=0.08)

        intro_time = min(1.0, duration * 0.2)
        rem_time = max(0.1, duration - intro_time)
        step2_time = min(0.5, rem_time * 0.2)
        wait_time = max(0.1, rem_time - step2_time)

        self.play(manim.Create(table), run_time=intro_time)
        self.play(manim.Create(active_box), run_time=step2_time)

        # Deterministic wait replacing broken dt updater


        self.wait(wait_time)
