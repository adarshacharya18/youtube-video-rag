from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim
    from manim import VGroup, Circle, Text, Line, DOWN, UP

class TreeScene(BaseDSAScene):
    def construct_dsa_animation(self):
        if not MANIM_AVAILABLE:
            return

        action = self.params.get("action", "display")
        
        if action == "bfs":
            self.action_bfs()
        elif action == "dfs":
            self.action_dfs()
        elif action == "insert":
            self.action_insert()
        else:
            self.action_display()

    def build_tree_vgroup(self, nodes_data):
        if not nodes_data:
            return VGroup(), []
        
        nodes = []
        edges = VGroup()
        node_vgroups = []
        
        for val in nodes_data:
            if val is not None:
                c = Circle(radius=0.4, color=self.theme.BORDER, fill_color=self.theme.CONTAINER_BG, fill_opacity=1)
                t = Text(str(val), color=self.theme.TEXT_PRIMARY).scale(0.6)
                t.move_to(c.get_center())
                vg = VGroup(c, t)
                nodes.append(vg)
                node_vgroups.append(vg)
            else:
                nodes.append(None)
                
        def layout_node(idx, x, y, dx):
            if idx < len(nodes) and nodes[idx] is not None:
                nodes[idx].move_to([x, y, 0])
                left_idx = 2 * idx + 1
                right_idx = 2 * idx + 2
                if left_idx < len(nodes) and nodes[left_idx] is not None:
                    layout_node(left_idx, x - dx, y - 1.2, dx * 0.5)
                    edges.add(Line(nodes[idx].get_bottom(), nodes[left_idx].get_top(), color=self.theme.PRIMARY_ACCENT))
                if right_idx < len(nodes) and nodes[right_idx] is not None:
                    layout_node(right_idx, x + dx, y - 1.2, dx * 0.5)
                    edges.add(Line(nodes[idx].get_bottom(), nodes[right_idx].get_top(), color=self.theme.PRIMARY_ACCENT))

        if len(nodes) > 0 and nodes[0] is not None:
            layout_node(0, 0, 2, 2)
            
        return VGroup(*node_vgroups, edges), node_vgroups

    def action_display(self):
        nodes_data = self.params.get("nodes", [1, 2, 3, None, 4, 5])
        duration = float(self.params.get("duration", 5.0))
        
        tree_vg, _ = self.build_tree_vgroup(nodes_data)
        self.play(manim.Create(tree_vg), run_time=duration * 0.8)
        self.wait(duration * 0.2)

    def action_bfs(self):
        nodes_data = self.params.get("nodes", [1, 2, 3, 4, 5])
        duration = float(self.params.get("duration", 5.0))
        
        tree_vg, node_vgroups = self.build_tree_vgroup(nodes_data)
        self.add(tree_vg)
        
        if node_vgroups:
            step_time = (duration * 0.8) / len(node_vgroups)
            for node in node_vgroups:
                self.play(node[0].animate.set_fill(self.theme.HIGHLIGHT), run_time=step_time)
        self.wait(duration * 0.2)

    def action_dfs(self):
        nodes_data = self.params.get("nodes", [1, 2, 3, 4, 5])
        duration = float(self.params.get("duration", 5.0))
        
        tree_vg, node_vgroups = self.build_tree_vgroup(nodes_data)
        self.add(tree_vg)
        
        dfs_order = []
        def dfs(idx):
            if idx < len(nodes_data) and nodes_data[idx] is not None:
                valid_count = sum(1 for x in nodes_data[:idx] if x is not None)
                if valid_count < len(node_vgroups):
                    dfs_order.append(node_vgroups[valid_count])
                dfs(2 * idx + 1)
                dfs(2 * idx + 2)
        dfs(0)
        
        if dfs_order:
            step_time = (duration * 0.8) / len(dfs_order)
            for node in dfs_order:
                self.play(node[0].animate.set_fill(self.theme.HIGHLIGHT), run_time=step_time)
        self.wait(duration * 0.2)

    def action_insert(self):
        nodes_data = self.params.get("nodes", [1, 2, 3])
        duration = float(self.params.get("duration", 5.0))
        
        tree_vg, node_vgroups = self.build_tree_vgroup(nodes_data)
        self.play(manim.Create(tree_vg), run_time=duration * 0.4)
        
        nodes_data_new = nodes_data + [4]
        tree_vg_new, _ = self.build_tree_vgroup(nodes_data_new)
        
        self.play(manim.Transform(tree_vg, tree_vg_new), run_time=duration * 0.5)
        self.wait(duration * 0.1)
