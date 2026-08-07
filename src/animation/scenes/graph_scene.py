from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim
    from manim import Graph

class GraphScene(BaseDSAScene):
    def construct_dsa_animation(self):
        if not MANIM_AVAILABLE:
            return

        action = self.params.get("action", "display")
        
        if action == "bfs":
            self.action_bfs()
        elif action == "dfs":
            self.action_dfs()
        else:
            self.action_display()

    def create_graph(self):
        vertices = self.params.get("vertices", [1, 2, 3, 4])
        edges = self.params.get("edges", [[1, 2], [2, 3], [3, 4], [4, 1]])
        edges_tuples = [(u, v) for u, v in edges]
        
        graph = Graph(
            vertices, edges_tuples,
            layout="spring",
            vertex_config={"radius": 0.4, "color": self.theme.BORDER, "fill_color": self.theme.CONTAINER_BG, "fill_opacity": 1},
            edge_config={"stroke_color": self.theme.PRIMARY_ACCENT},
            labels=True
        )
        return graph

    def action_display(self):
        duration = float(self.params.get("duration", 5.0))
        graph = self.create_graph()
        self.play(manim.Create(graph), run_time=duration * 0.8)
        self.wait(duration * 0.2)

    def action_bfs(self):
        duration = float(self.params.get("duration", 5.0))
        traversal_path = self.params.get("traversal_path", [1, 2, 4, 3])
        graph = self.create_graph()
        self.play(manim.Create(graph), run_time=duration * 0.4)
        
        if traversal_path:
            step_time = (duration * 0.5) / len(traversal_path)
            for v in traversal_path:
                if v in graph.vertices:
                    self.play(
                        graph.vertices[v].animate.set_fill(self.theme.HIGHLIGHT),
                        run_time=step_time
                    )
        self.wait(duration * 0.1)

    def action_dfs(self):
        duration = float(self.params.get("duration", 5.0))
        traversal_path = self.params.get("traversal_path", [1, 2, 3, 4])
        graph = self.create_graph()
        self.play(manim.Create(graph), run_time=duration * 0.4)
        
        if traversal_path:
            step_time = (duration * 0.5) / len(traversal_path)
            for v in traversal_path:
                if v in graph.vertices:
                    self.play(
                        graph.vertices[v].animate.set_fill(self.theme.HIGHLIGHT),
                        run_time=step_time
                    )
        self.wait(duration * 0.1)
