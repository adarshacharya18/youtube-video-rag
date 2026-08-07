"""LinkedList Node & Pointer Connection Scene Template."""

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim
    from manim import DOWN, LEFT, RIGHT, UP, Arrow, Rectangle, Text, VGroup


class LinkedListScene(BaseDSAScene):
    """Visualizes linked nodes connected via next arrows."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
            
        self.nodes_data = self.params.get("nodes", [1, 2, 3, 4, 5])
        self.action = self.params.get("action", "traverse")
        self.duration = float(self.params.get("duration", 5.0))
        self.highlight_indices = self.params.get("highlight_indices", [])
        self.pointers = self.params.get("pointers", {})

        if self.action == "fast_slow":
            self.do_fast_slow()
        elif self.action == "reverse":
            self.do_reverse()
        elif self.action == "split":
            self.do_split()
        elif self.action in ["merge", "interleave", "reorder"]:
            self.do_merge()
        else:
            self.do_traverse()

    def _create_linked_list(self, nodes_data, position=manim.ORIGIN, buff=0.5):
        node_groups = []
        
        for i, val in enumerate(nodes_data):
            rect = Rectangle(width=1.2, height=0.8, color=self.theme.PRIMARY_ACCENT)
            if i in self.highlight_indices:
                rect.set_color(self.theme.HIGHLIGHT)
                rect.set_fill(self.theme.HIGHLIGHT, opacity=0.2)
                
            txt = Text(str(val), font_size=24, color=self.theme.TEXT_PRIMARY)
            node_group = VGroup(rect, txt)
            node_groups.append(node_group)
            
        nodes_vgroup = VGroup(*node_groups).arrange(RIGHT, buff=buff)
        nodes_vgroup.move_to(position)
        if nodes_vgroup.width > 12:
            nodes_vgroup.scale_to_fit_width(12)
            nodes_vgroup.center()
            
        arrows = []
        for i in range(len(node_groups) - 1):
            arrow = Arrow(node_groups[i].get_right(), node_groups[i+1].get_left(), buff=0.1, color=self.theme.SECONDARY_ACCENT)
            arrows.append(arrow)
            
        full_group = VGroup(*node_groups, *arrows)
        
        return full_group, node_groups, arrows

    def do_traverse(self):
        chain, node_groups, arrows = self._create_linked_list(self.nodes_data)
        
        intro_time = min(1.0, self.duration * 0.2)
        rem_time = max(0.1, self.duration - intro_time)
        
        self.play(manim.Create(chain), run_time=intro_time)
        
        if not node_groups:
            self.wait(rem_time)
            return
            
        pointer = Arrow(start=DOWN * 0.6, end=DOWN * 0.1, color=self.theme.HIGHLIGHT)
        pointer_label = Text("ptr", font_size=20, color=self.theme.TEXT_PRIMARY)
        pointer_label.next_to(pointer, DOWN, buff=0.1)
        pointer_group = VGroup(pointer, pointer_label)
        
        pointer_group.next_to(node_groups[0], DOWN, buff=0.2)
        
        self.play(manim.Create(pointer_group), run_time=rem_time * 0.1)
        
        step_time = (rem_time * 0.9) / max(1, len(node_groups) - 1)
        for i in range(1, len(node_groups)):
            self.play(
                pointer_group.animate.next_to(node_groups[i], DOWN, buff=0.2),
                run_time=step_time,
                rate_func=manim.smooth
            )

    def do_fast_slow(self):
        chain, node_groups, arrows = self._create_linked_list(self.nodes_data)
        
        intro_time = min(1.0, self.duration * 0.15)
        rem_time = max(0.1, self.duration - intro_time)
        
        self.play(manim.Create(chain), run_time=intro_time)
        
        if len(node_groups) < 2:
            self.wait(rem_time)
            return
            
        slow_ptr = Arrow(start=DOWN * 0.6, end=DOWN * 0.1, color=self.theme.HIGHLIGHT)
        slow_lbl = Text("slow", font_size=20, color=self.theme.HIGHLIGHT).next_to(slow_ptr, DOWN, buff=0.1)
        slow_grp = VGroup(slow_ptr, slow_lbl)
        
        fast_ptr = Arrow(start=UP * 0.6, end=UP * 0.1, color=self.theme.WARNING)
        fast_lbl = Text("fast", font_size=20, color=self.theme.WARNING).next_to(fast_ptr, UP, buff=0.1)
        fast_grp = VGroup(fast_ptr, fast_lbl)
        
        slow_grp.next_to(node_groups[0], DOWN, buff=0.2)
        fast_grp.next_to(node_groups[0], UP, buff=0.2)
        
        init_slow_anim = node_groups[0][0].animate.set_stroke(self.theme.HIGHLIGHT, width=3)
        self.play(
            manim.Create(slow_grp),
            manim.Create(fast_grp),
            init_slow_anim,
            run_time=min(0.5, rem_time * 0.15)
        )
        
        # Check if pointers param provided
        custom_slow = self.pointers.get("slow")
        custom_fast = self.pointers.get("fast")
        
        if custom_slow is not None and custom_fast is not None:
            s_target = min(int(custom_slow), len(node_groups) - 1)
            f_target = min(int(custom_fast), len(node_groups) - 1)
            steps_data = [(s_target, f_target)]
        else:
            steps_data = []
            s_idx = 0
            f_idx = 0
            while f_idx < len(node_groups) - 1:
                s_idx += 1
                f_idx += 2
                if f_idx >= len(node_groups):
                    f_idx = len(node_groups) - 1
                steps_data.append((s_idx, f_idx))
                
        num_steps = len(steps_data)
        if num_steps == 0:
            self.wait(rem_time * 0.7)
            return

        step_run_time = (rem_time * 0.55) / num_steps
        
        cur_slow_idx = 0
        cur_fast_idx = 0
        
        for s_idx, f_idx in steps_data:
            anims = [
                slow_grp.animate.next_to(node_groups[s_idx], DOWN, buff=0.2),
                fast_grp.animate.next_to(node_groups[f_idx], UP, buff=0.2),
                node_groups[s_idx][0].animate.set_stroke(self.theme.HIGHLIGHT, width=3).set_fill(self.theme.HIGHLIGHT, opacity=0.2),
                node_groups[f_idx][0].animate.set_stroke(self.theme.WARNING, width=3).set_fill(self.theme.WARNING, opacity=0.2),
            ]
            
            if cur_slow_idx != s_idx and cur_slow_idx != f_idx and cur_slow_idx not in self.highlight_indices:
                anims.append(node_groups[cur_slow_idx][0].animate.set_stroke(self.theme.PRIMARY_ACCENT, width=2).set_fill(self.theme.CONTAINER_BG, opacity=0.8))
            if cur_fast_idx != f_idx and cur_fast_idx != s_idx and cur_fast_idx not in self.highlight_indices:
                anims.append(node_groups[cur_fast_idx][0].animate.set_stroke(self.theme.PRIMARY_ACCENT, width=2).set_fill(self.theme.CONTAINER_BG, opacity=0.8))
                
            self.play(*anims, run_time=step_run_time, rate_func=manim.smooth)
            cur_slow_idx = s_idx
            cur_fast_idx = f_idx
            
        # Highlight middle node callout
        mid_node_idx = cur_slow_idx
        mid_rect = manim.SurroundingRectangle(node_groups[mid_node_idx], color=self.theme.HIGHLIGHT, buff=0.08)
        mid_label = Text("Middle Node", font_size=18, color=self.theme.HIGHLIGHT)
        mid_label.next_to(slow_grp, DOWN, buff=0.15)
        
        mid_anim_time = max(0.4, rem_time * 0.3)
        self.play(
            manim.Create(mid_rect),
            manim.Write(mid_label),
            run_time=mid_anim_time * 0.5
        )
        self.wait(mid_anim_time * 0.5)

    def do_reverse(self):
        chain, node_groups, arrows = self._create_linked_list(self.nodes_data)
        
        intro_time = min(1.0, self.duration * 0.2)
        rem_time = max(0.1, self.duration - intro_time)
        
        self.play(manim.Create(chain), run_time=intro_time)
        
        if not arrows:
            self.wait(rem_time)
            return
            
        step_time = rem_time / len(arrows)
        
        for i in range(len(arrows)):
            arrow = arrows[i]
            start_pt = arrow.get_start()
            end_pt = arrow.get_end()
            
            new_arrow = Arrow(start=end_pt, end=start_pt, color=self.theme.WARNING, buff=0.1)
            self.play(manim.Transform(arrow, new_arrow), run_time=step_time)

    def do_split(self):
        chain, node_groups, arrows = self._create_linked_list(self.nodes_data)
        
        intro_time = min(1.0, self.duration * 0.3)
        rem_time = max(0.1, self.duration - intro_time)
        
        self.play(manim.Create(chain), run_time=intro_time)
        
        if len(node_groups) < 2:
            self.wait(rem_time)
            return
            
        mid = len(node_groups) // 2
        
        if mid - 1 < len(arrows):
            mid_arrow = arrows[mid - 1]
            self.play(manim.FadeOut(mid_arrow), run_time=rem_time * 0.2)
        
        elements_to_move = []
        for i in range(mid, len(node_groups)):
            elements_to_move.append(node_groups[i])
            if i < len(arrows):
                elements_to_move.append(arrows[i])
                
        second_half = VGroup(*elements_to_move)
        self.play(second_half.animate.shift(DOWN * 2), run_time=rem_time * 0.8)

    def do_merge(self):
        nodes = self.nodes_data
        if len(nodes) < 2:
            self.wait(self.duration)
            return
            
        mid = (len(nodes) + 1) // 2
        first_half = nodes[:mid]
        second_half = nodes[mid:][::-1]
        
        chain1, nodes1, arrows1 = self._create_linked_list(first_half, position=UP * 1, buff=1.5)
        chain2, nodes2, arrows2 = self._create_linked_list(second_half, position=DOWN * 1, buff=0.5)
        
        all_group = VGroup(chain1, chain2)
        if all_group.width > 12:
            all_group.scale_to_fit_width(12)
            all_group.center()
            
        intro_time = min(1.0, self.duration * 0.2)
        rem_time = max(0.1, self.duration - intro_time)
        
        self.play(manim.Create(chain1), manim.Create(chain2), run_time=intro_time)
        
        step_time = rem_time / max(1, len(nodes2) * 2)
        
        for i in range(len(nodes2)):
            node = nodes2[i]
            if i < len(arrows2):
                self.play(manim.FadeOut(arrows2[i]), run_time=step_time * 0.5)
                
            if i < len(nodes1) - 1:
                target_pos = (nodes1[i].get_center() + nodes1[i+1].get_center()) / 2
            else:
                target_pos = nodes1[i].get_center() + RIGHT * 1.5
                
            self.play(node.animate.move_to(target_pos), run_time=step_time)
            
            if i < len(arrows1):
                self.play(manim.FadeOut(arrows1[i]), run_time=0.1)
                arr1 = Arrow(nodes1[i].get_right(), node.get_left(), buff=0.1, color=self.theme.HIGHLIGHT)
                arr2 = Arrow(node.get_right(), nodes1[i+1].get_left(), buff=0.1, color=self.theme.HIGHLIGHT)
                self.play(manim.Create(arr1), manim.Create(arr2), run_time=step_time * 0.4)
            else:
                arr1 = Arrow(nodes1[-1].get_right(), node.get_left(), buff=0.1, color=self.theme.HIGHLIGHT)
                self.play(manim.Create(arr1), run_time=step_time * 0.5)
