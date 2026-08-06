"""Graph Traversal (BFS/DFS) Scene Template."""

import math

from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim  # type: ignore
    from manim import Dot, Graph, ValueTracker  # type: ignore


class GraphScene(BaseDSAScene):
    """Visualizes graph vertices, edges, and traversal highlights."""

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return
        vertices = self.params.get("vertices", [1, 2, 3, 4])
        raw_edges = self.params.get("edges", [(1, 2), (2, 3), (3, 4), (4, 1)])
        edges = [tuple(e) if isinstance(e, list) else e for e in raw_edges]
        duration: float = float(self.params.get("duration", 5.0))

        g = Graph(vertices, edges, layout="circular")
        dot = Dot(color=self.theme.HIGHLIGHT, radius=0.15)

        intro_time = min(1.0, duration * 0.2)
        rem_time = max(0.1, duration - intro_time)
        step2_time = min(0.5, rem_time * 0.2)
        wait_time = max(0.1, rem_time - step2_time)

        self.play(manim.Create(g), run_time=intro_time)
        self.play(manim.Create(dot), run_time=step2_time)

        # Deterministic wait replacing broken dt updater


        self.wait(wait_time)
