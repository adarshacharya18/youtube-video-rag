from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim
    from manim import VGroup, Rectangle, Text, Arrow

class HashmapScene(BaseDSAScene):
    def construct_dsa_animation(self):
        if not MANIM_AVAILABLE:
            return

        action = self.params.get("action", "display")
        
        if action == "put":
            self.action_put()
        elif action == "get":
            self.action_get()
        elif action == "collision":
            self.action_collision()
        else:
            self.action_display()

    def create_table(self, entries):
        group = VGroup()
        for k, v in entries.items():
            box = Rectangle(width=3, height=1, color=self.theme.BORDER, fill_color=self.theme.CONTAINER_BG, fill_opacity=1)
            t = Text(f"{k}: {v}", color=self.theme.TEXT_PRIMARY).scale(0.6)
            t.move_to(box.get_center())
            group.add(VGroup(box, t))
        group.arrange(manim.DOWN, buff=0)
        return group

    def action_display(self):
        duration = float(self.params.get("duration", 5.0))
        entries = self.params.get("entries", {"A": 1, "B": 2, "C": 3})
        table = self.create_table(entries)
        self.play(manim.Create(table), run_time=duration * 0.8)
        self.wait(duration * 0.2)

    def action_put(self):
        duration = float(self.params.get("duration", 5.0))
        entries = self.params.get("entries", {"A": 1, "B": 2})
        table = self.create_table(entries)
        self.play(manim.Create(table), run_time=duration * 0.4)
        
        new_entries = {**entries, "C": 3}
        new_table = self.create_table(new_entries)
        new_table.move_to(table.get_center())
        
        self.play(manim.Transform(table, new_table), run_time=duration * 0.4)
        self.wait(duration * 0.2)

    def action_get(self):
        duration = float(self.params.get("duration", 5.0))
        entries = self.params.get("entries", {"A": 1, "B": 2, "C": 3})
        highlight_key = self.params.get("highlight_key", "B")
        table = self.create_table(entries)
        self.play(manim.Create(table), run_time=duration * 0.4)
        
        idx = list(entries.keys()).index(highlight_key) if highlight_key in entries else -1
        if idx >= 0:
            pointer = Arrow(start=manim.LEFT, end=manim.RIGHT, color=self.theme.PRIMARY_ACCENT)
            pointer.next_to(table[idx], manim.LEFT)
            self.play(manim.Create(pointer), run_time=duration * 0.2)
            self.play(table[idx][0].animate.set_fill(self.theme.HIGHLIGHT), run_time=duration * 0.3)
        self.wait(duration * 0.1)

    def action_collision(self):
        duration = float(self.params.get("duration", 5.0))
        entries = self.params.get("entries", {"Hash 1": "Val 1"})
        table = self.create_table(entries)
        self.play(manim.Create(table), run_time=duration * 0.3)
        
        pointer1 = Arrow(start=manim.LEFT, end=manim.RIGHT, color=self.theme.PRIMARY_ACCENT).next_to(table[0], manim.LEFT).shift(manim.UP*0.2)
        pointer2 = Arrow(start=manim.LEFT, end=manim.RIGHT, color=self.theme.WARNING).next_to(table[0], manim.LEFT).shift(manim.DOWN*0.2)
        
        self.play(manim.Create(pointer1), run_time=duration * 0.2)
        self.play(manim.Create(pointer2), run_time=duration * 0.2)
        self.play(table[0][0].animate.set_fill(self.theme.WARNING), run_time=duration * 0.2)
        self.wait(duration * 0.1)
