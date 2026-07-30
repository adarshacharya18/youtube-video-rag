"""Hashmap & Bucket Array Scene Template."""

from typing import Any, Dict

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import DOWN, Rectangle, Text, VGroup  # type: ignore


class HashmapScene(BaseDSAScene):
    """Visualizes Key-Value slots and hash table operations."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        entries: Dict[str, Any] = self.params.get("entries", {"key1": "val1", "key2": "val2"})
        slots = []
        for k, v in entries.items():
            slot_bg = Rectangle(width=3.0, height=0.8, color=self.theme.PRIMARY_ACCENT)
            txt = Text(f"{k} : {v}", font_size=20, color=self.theme.TEXT_PRIMARY)
            slots.append(VGroup(slot_bg, txt))

        table = VGroup(*slots).arrange(DOWN, buff=0.2)
        table.move_to([0, 0, 0])
        self.play(manim.Create(table))
        self.wait(1)
