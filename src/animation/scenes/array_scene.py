from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim
    from manim import VGroup, Square, Text, Arrow, Rectangle, UP, DOWN, LEFT, RIGHT

class ArrayScene(BaseDSAScene):
    def construct_dsa_animation(self):
        if not MANIM_AVAILABLE:
            return

        action = self.params.get("action", "traverse")
        
        if action == "two_pointers":
            self.action_two_pointers()
        elif action == "swap":
            self.action_swap()
        elif action == "highlight":
            self.action_highlight()
        elif action == "sliding_window":
            self.action_sliding_window()
        else:
            self.action_traverse()

    def create_array_vg(self, arr):
        group = VGroup()
        for val in arr:
            sq = Square(side_length=1.0, color=self.theme.BORDER, fill_color=self.theme.CONTAINER_BG, fill_opacity=1)
            t = Text(str(val), color=self.theme.TEXT_PRIMARY).scale(0.8)
            t.move_to(sq.get_center())
            group.add(VGroup(sq, t))
        group.arrange(RIGHT, buff=0.2)
        return group

    def action_traverse(self):
        arr = self.params.get("array", [1, 2, 3, 4, 5])
        duration = float(self.params.get("duration", 5.0))
        group = self.create_array_vg(arr)
        self.play(manim.Create(group), run_time=duration * 0.3)
        
        if len(arr) > 0:
            pointer = Arrow(start=UP, end=DOWN, color=self.theme.PRIMARY_ACCENT)
            pointer.next_to(group[0], UP)
            self.play(manim.Create(pointer), run_time=duration * 0.1)
            
            step_time = (duration * 0.5) / len(arr)
            for i in range(1, len(arr)):
                self.play(pointer.animate.next_to(group[i], UP), run_time=step_time)
        
        self.wait(duration * 0.1)

    def action_two_pointers(self):
        arr = self.params.get("array", [1, 2, 3, 4, 5])
        duration = float(self.params.get("duration", 5.0))
        group = self.create_array_vg(arr)
        self.play(manim.Create(group), run_time=duration * 0.3)
        
        if len(arr) >= 2:
            left_p = Arrow(start=UP, end=DOWN, color=self.theme.PRIMARY_ACCENT).next_to(group[0], UP)
            right_p = Arrow(start=UP, end=DOWN, color=self.theme.SECONDARY_ACCENT).next_to(group[-1], UP)
            self.play(manim.Create(left_p), manim.Create(right_p), run_time=duration * 0.2)
            
            self.play(
                left_p.animate.next_to(group[len(arr)//2 - 1], UP),
                right_p.animate.next_to(group[len(arr)//2], UP),
                run_time=duration * 0.4
            )
        self.wait(duration * 0.1)

    def action_swap(self):
        arr = self.params.get("array", [1, 2, 3, 4, 5])
        duration = float(self.params.get("duration", 5.0))
        swap_indices = self.params.get("swap_indices", [0, len(arr)-1])
        group = self.create_array_vg(arr)
        self.play(manim.Create(group), run_time=duration * 0.3)
        
        if len(arr) > max(swap_indices):
            i, j = swap_indices
            box_i, box_j = group[i], group[j]
            self.play(
                box_i.animate.move_to(box_j.get_center()),
                box_j.animate.move_to(box_i.get_center()),
                run_time=duration * 0.6
            )
        self.wait(duration * 0.1)

    def action_highlight(self):
        arr = self.params.get("array", [1, 2, 3, 4, 5])
        duration = float(self.params.get("duration", 5.0))
        highlight_indices = self.params.get("highlight_indices", [1, 3])
        group = self.create_array_vg(arr)
        self.play(manim.Create(group), run_time=duration * 0.4)
        
        anims = []
        for idx in highlight_indices:
            if idx < len(arr):
                sq = group[idx][0]
                anims.append(sq.animate.set_fill(self.theme.HIGHLIGHT, opacity=1))
        
        if anims:
            self.play(*anims, run_time=duration * 0.5)
        self.wait(duration * 0.1)

    def action_sliding_window(self):
        arr = self.params.get("array", [1, 2, 3, 4, 5])
        duration = float(self.params.get("duration", 5.0))
        window_size = self.params.get("window_size", 3)
        group = self.create_array_vg(arr)
        self.play(manim.Create(group), run_time=duration * 0.3)
        
        if len(arr) >= window_size and window_size > 0:
            window = Rectangle(
                width=window_size * 1.2, height=1.2,
                color=self.theme.HIGHLIGHT
            )
            window.move_to(VGroup(*group[:window_size]).get_center())
            self.play(manim.Create(window), run_time=duration * 0.2)
            
            steps = len(arr) - window_size
            if steps > 0:
                step_time = (duration * 0.4) / steps
                for i in range(1, steps + 1):
                    target_pos = VGroup(*group[i:i+window_size]).get_center()
                    self.play(window.animate.move_to(target_pos), run_time=step_time)
        self.wait(duration * 0.1)
