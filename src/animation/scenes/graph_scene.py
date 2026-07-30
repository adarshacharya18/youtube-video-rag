"""Graph Traversal (BFS/DFS) Scene Template."""

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import Graph  # type: ignore


class GraphScene(BaseDSAScene):
    """Visualizes graph vertices, edges, and traversal highlights."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        vertices = self.params.get("vertices", [1, 2, 3, 4])
        edges = self.params.get("edges", [(1, 2), (2, 3), (3, 4), (4, 1)])

        g = Graph(vertices, edges, layout="circular")
        self.play(manim.Create(g))
        self.wait(1)
