import heapq
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from src.animation.scenes.base_scene import (
    MANIM_AVAILABLE,
    BaseDSAScene,
    GraphSceneSchema,
)

if MANIM_AVAILABLE:
    import manim
    from manim import VGroup, Text, Create, FadeIn


def normalize_graph_inputs(
    raw_vertices: Any,
    raw_edges: Any,
    raw_weights: Any,
) -> Tuple[List[Any], List[Tuple[Any, Any]], Dict[Tuple[Any, Any], Any], List[Tuple[Any, Any, float]]]:
    """Parses arbitrary vertices, 2-tuples, 3-tuples, dict edges, and weight maps."""
    edge_tuples: List[Tuple[Any, Any]] = []
    weights_map: Dict[Tuple[Any, Any], Any] = {}
    edges_with_weights: List[Tuple[Any, Any, float]] = []

    if isinstance(raw_edges, (list, tuple)):
        for edge_item in raw_edges:
            if isinstance(edge_item, (list, tuple)):
                if len(edge_item) >= 3:
                    u, v, w = edge_item[0], edge_item[1], edge_item[2]
                    edge_tuples.append((u, v))
                    weights_map[(u, v)] = w
                    try:
                        edges_with_weights.append((u, v, float(w)))
                    except (ValueError, TypeError):
                        edges_with_weights.append((u, v, 1.0))
                elif len(edge_item) == 2:
                    u, v = edge_item[0], edge_item[1]
                    edge_tuples.append((u, v))
                elif len(edge_item) == 1:
                    pass
            elif isinstance(edge_item, dict):
                u = edge_item.get("u", edge_item.get("source", edge_item.get("from")))
                v = edge_item.get("v", edge_item.get("target", edge_item.get("to")))
                if u is not None and v is not None:
                    edge_tuples.append((u, v))
                    w = edge_item.get("w", edge_item.get("weight"))
                    if w is not None:
                        weights_map[(u, v)] = w
                        try:
                            edges_with_weights.append((u, v, float(w)))
                        except (ValueError, TypeError):
                            edges_with_weights.append((u, v, 1.0))

    if raw_weights is not None:
        if isinstance(raw_weights, dict):
            for k, w in raw_weights.items():
                if isinstance(k, (tuple, list)) and len(k) == 2:
                    u, v = k[0], k[1]
                    weights_map[(u, v)] = w
                    try:
                        edges_with_weights.append((u, v, float(w)))
                    except (ValueError, TypeError):
                        edges_with_weights.append((u, v, 1.0))
                elif isinstance(k, str) and "," in k:
                    parts = k.split(",")
                    u, v = parts[0].strip(), parts[1].strip()
                    weights_map[(u, v)] = w
        elif isinstance(raw_weights, (list, tuple)):
            for idx, w in enumerate(raw_weights):
                if idx < len(edge_tuples):
                    u, v = edge_tuples[idx]
                    weights_map[(u, v)] = w

    # Assign default weight 1.0 if missing in edges_with_weights
    for u, v in edge_tuples:
        if (u, v) not in weights_map and (v, u) not in weights_map:
            edges_with_weights.append((u, v, 1.0))

    vertices: List[Any] = []
    if isinstance(raw_vertices, (list, tuple, set)):
        vertices = list(raw_vertices)
    elif raw_vertices is not None:
        vertices = [raw_vertices]

    if not vertices:
        seen = set()
        for u, v in edge_tuples:
            if u not in seen:
                seen.add(u)
                vertices.append(u)
            if v not in seen:
                seen.add(v)
                vertices.append(v)

    return vertices, edge_tuples, weights_map, edges_with_weights


class GraphScene(BaseDSAScene):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.load_parameters(schema=GraphSceneSchema)

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return

        action = str(self.get_parameter("action", "display")).lower()

        if action == "bfs":
            self.action_bfs()
        elif action == "dfs":
            self.action_dfs()
        elif action == "dijkstra":
            self.action_dijkstra()
        elif action in ("weighted_edges", "weighted"):
            self.action_weighted_edges()
        else:
            self.action_display()

    def create_graph(
        self,
    ) -> Tuple[
        Any,  # graph mobject
        List[Any],  # vertices
        List[Tuple[Any, Any]],  # edge_tuples
        Dict[Tuple[Any, Any], Any],  # weights_map
        Any,  # weight_labels_vgroup
    ]:
        raw_vertices = self.get_parameter("vertices", default=[1, 2, 3, 4])
        raw_edges = self.get_parameter("edges", default=[[1, 2], [2, 3], [3, 4], [4, 1]])
        raw_weights = self.get_parameter("weights", default=None)
        directed = self.get_parameter("directed", default=False, expected_type=bool)
        layout_param = self.get_parameter("layout", default="kamada_kawai")

        vertices, edge_tuples, weights_map, _ = normalize_graph_inputs(
            raw_vertices, raw_edges, raw_weights
        )

        if not vertices:
            vertices = [1]

        if isinstance(layout_param, dict):
            layout_val = layout_param
            layout_config = None
        else:
            s_layout = str(layout_param)
            if s_layout in ["kamada_kawai", "circle", "circular", "spectral", "spring", "planar", "shell"]:
                layout_val = "circular" if s_layout == "circle" else s_layout
            else:
                layout_val = "kamada_kawai"

            if layout_val == "spring":
                layout_config = {"seed": 42}
            else:
                layout_config = None

        vertex_config = {
            "radius": 0.35,
            "color": self.theme.BORDER,
            "fill_color": self.theme.CONTAINER_BG,
            "fill_opacity": 1.0,
        }
        edge_config = {"stroke_color": self.theme.PRIMARY_ACCENT, "stroke_width": 2.5}

        if directed and hasattr(manim, "DiGraph"):
            graph = manim.DiGraph(
                vertices,
                edge_tuples,
                layout=layout_val,
                layout_config=layout_config,
                vertex_config=vertex_config,
                edge_config=edge_config,
                labels=True,
            )
        else:
            graph = manim.Graph(
                vertices,
                edge_tuples,
                layout=layout_val,
                layout_config=layout_config,
                vertex_config=vertex_config,
                edge_config=edge_config,
                labels=True,
            )

        weight_labels_vg = VGroup()
        for (u, v), w in weights_map.items():
            if u in graph.vertices and v in graph.vertices:
                p_u = graph.vertices[u].get_center()
                p_v = graph.vertices[v].get_center()
                mid = (p_u + p_v) / 2.0
                vec = p_v - p_u
                norm = np.linalg.norm(vec[:2])
                if norm > 1e-4:
                    perp = np.array([-vec[1], vec[0], 0.0]) / norm
                else:
                    perp = np.array([0.0, 0.25, 0.0])
                lbl_pos = mid + perp * 0.25
                lbl = Text(str(w), font_size=16, color=self.theme.SECONDARY_ACCENT)
                lbl.move_to(lbl_pos)
                weight_labels_vg.add(lbl)

        return graph, vertices, edge_tuples, weights_map, weight_labels_vg

    def action_display(self) -> None:
        duration = float(self.get_parameter("duration", default=5.0))
        graph, vertices, _, _, weight_labels_vg = self.create_graph()

        anim_time = self.get_step_runtime(1, default_step_time=duration * 0.6)
        self.play(Create(graph), FadeIn(weight_labels_vg), run_time=anim_time)

        target_mobs = [graph.vertices[v] for v in vertices if v in graph.vertices]
        wait_time = max(0.4, duration - anim_time)
        self.animate_continuous_wait(
            duration=wait_time, pulse_targets=[graph], scale_factor=1.06
        )

    def action_bfs(self) -> None:
        duration = float(self.get_parameter("duration", default=5.0))
        graph, vertices, edge_tuples, _, weight_labels_vg = self.create_graph()

        traversal_path = self.get_parameter("traversal_path", default=None, expected_type=list)
        if not traversal_path:
            start_v = vertices[0] if vertices else 1
            adj: Dict[Any, List[Any]] = {v: [] for v in vertices}
            for u, v in edge_tuples:
                adj[u].append(v)
                adj[v].append(u)
            visited = {start_v}
            q = [start_v]
            traversal_path = []
            while q:
                curr = q.pop(0)
                traversal_path.append(curr)
                for nxt in adj.get(curr, []):
                    if nxt not in visited:
                        visited.add(nxt)
                        q.append(nxt)
            for v in vertices:
                if v not in visited:
                    traversal_path.append(v)

        init_time = self.get_step_runtime(10, default_step_time=duration * 0.3)
        self.play(Create(graph), FadeIn(weight_labels_vg), run_time=init_time)

        if traversal_path:
            step_time = self.get_step_runtime(
                len(traversal_path), default_step_time=0.6, target_duration=duration * 0.6
            )
            for idx, v in enumerate(traversal_path):
                anims = []
                if v in graph.vertices:
                    anims.append(graph.vertices[v].animate.set_fill(self.theme.HIGHLIGHT))
                if idx > 0:
                    prev_v = traversal_path[idx - 1]
                    edge_key = None
                    if (prev_v, v) in graph.edges:
                        edge_key = (prev_v, v)
                    elif (v, prev_v) in graph.edges:
                        edge_key = (v, prev_v)
                    if edge_key:
                        anims.append(
                            graph.edges[edge_key].animate.set_color(self.theme.HIGHLIGHT).set_stroke(width=4.5)
                        )
                if anims:
                    self.play(*anims, run_time=step_time)

        self.animate_continuous_wait(
            duration=duration * 0.1, pulse_targets=[graph], scale_factor=1.06
        )

    def action_dfs(self) -> None:
        duration = float(self.get_parameter("duration", default=5.0))
        graph, vertices, edge_tuples, _, weight_labels_vg = self.create_graph()

        traversal_path = self.get_parameter("traversal_path", default=None, expected_type=list)
        if not traversal_path:
            start_v = vertices[0] if vertices else 1
            adj: Dict[Any, List[Any]] = {v: [] for v in vertices}
            for u, v in edge_tuples:
                adj[u].append(v)
                adj[v].append(u)
            visited = set()
            traversal_path = []

            def dfs(curr: Any) -> None:
                visited.add(curr)
                traversal_path.append(curr)
                for nxt in adj.get(curr, []):
                    if nxt not in visited:
                        dfs(nxt)

            dfs(start_v)
            for v in vertices:
                if v not in visited:
                    traversal_path.append(v)

        init_time = self.get_step_runtime(10, default_step_time=duration * 0.3)
        self.play(Create(graph), FadeIn(weight_labels_vg), run_time=init_time)

        if traversal_path:
            step_time = self.get_step_runtime(
                len(traversal_path), default_step_time=0.6, target_duration=duration * 0.6
            )
            for idx, v in enumerate(traversal_path):
                anims = []
                if v in graph.vertices:
                    anims.append(graph.vertices[v].animate.set_fill(self.theme.HIGHLIGHT))
                if idx > 0:
                    prev_v = traversal_path[idx - 1]
                    edge_key = None
                    if (prev_v, v) in graph.edges:
                        edge_key = (prev_v, v)
                    elif (v, prev_v) in graph.edges:
                        edge_key = (v, prev_v)
                    if edge_key:
                        anims.append(
                            graph.edges[edge_key].animate.set_color(self.theme.HIGHLIGHT).set_stroke(width=4.5)
                        )
                if anims:
                    self.play(*anims, run_time=step_time)

        self.animate_continuous_wait(
            duration=duration * 0.1, pulse_targets=[graph], scale_factor=1.06
        )

    def action_dijkstra(self) -> None:
        duration = float(self.get_parameter("duration", default=5.0))
        graph, vertices, edge_tuples, weights_map, weight_labels_vg = self.create_graph()

        shortest_path = self.get_parameter("shortest_path", default=None, expected_type=list)
        if not shortest_path:
            raw_vertices = self.get_parameter("vertices", default=[1, 2, 3, 4])
            raw_edges = self.get_parameter("edges", default=[[1, 2], [2, 3], [3, 4], [4, 1]])
            raw_weights = self.get_parameter("weights", default=None)
            _, _, _, edges_with_weights = normalize_graph_inputs(
                raw_vertices, raw_edges, raw_weights
            )
            start_v = vertices[0] if vertices else 1
            target_v = vertices[-1] if len(vertices) > 1 else start_v

            adj: Dict[Any, List[Tuple[Any, float]]] = {v: [] for v in vertices}
            for u, v, w in edges_with_weights:
                adj[u].append((v, w))
                adj[v].append((u, w))

            dist = {v: float("inf") for v in vertices}
            parent = {v: None for v in vertices}
            dist[start_v] = 0.0
            pq = [(0.0, start_v)]

            while pq:
                d, u = heapq.heappop(pq)
                if d > dist[u]:
                    continue
                if u == target_v:
                    break
                for v_nxt, w_val in adj.get(u, []):
                    if dist[u] + w_val < dist[v_nxt]:
                        dist[v_nxt] = dist[u] + w_val
                        parent[v_nxt] = u
                        heapq.heappush(pq, (dist[v_nxt], v_nxt))

            path = []
            curr = target_v
            while curr is not None:
                path.append(curr)
                curr = parent[curr]
            path.reverse()
            shortest_path = path if (len(path) > 1 and path[0] == start_v) else vertices

        init_time = self.get_step_runtime(10, default_step_time=duration * 0.3)
        self.play(Create(graph), FadeIn(weight_labels_vg), run_time=init_time)

        if shortest_path:
            step_time = self.get_step_runtime(
                len(shortest_path), default_step_time=0.7, target_duration=duration * 0.6
            )
            for idx, v in enumerate(shortest_path):
                anims = []
                if v in graph.vertices:
                    anims.append(graph.vertices[v].animate.set_fill(self.theme.HIGHLIGHT))
                if idx > 0:
                    prev_v = shortest_path[idx - 1]
                    edge_key = None
                    if (prev_v, v) in graph.edges:
                        edge_key = (prev_v, v)
                    elif (v, prev_v) in graph.edges:
                        edge_key = (v, prev_v)
                    if edge_key:
                        anims.append(
                            graph.edges[edge_key].animate.set_color(self.theme.HIGHLIGHT).set_stroke(width=5.0)
                        )
                if anims:
                    self.play(*anims, run_time=step_time)

        self.animate_continuous_wait(
            duration=duration * 0.1, pulse_targets=[graph], scale_factor=1.06
        )

    def action_weighted_edges(self) -> None:
        duration = float(self.get_parameter("duration", default=5.0))
        graph, vertices, edge_tuples, weights_map, weight_labels_vg = self.create_graph()

        init_time = self.get_step_runtime(10, default_step_time=duration * 0.3)
        self.play(Create(graph), FadeIn(weight_labels_vg), run_time=init_time)

        if edge_tuples:
            step_time = self.get_step_runtime(
                len(edge_tuples), default_step_time=0.6, target_duration=duration * 0.6
            )
            for u, v in edge_tuples:
                anims = []
                edge_key = None
                if (u, v) in graph.edges:
                    edge_key = (u, v)
                elif (v, u) in graph.edges:
                    edge_key = (v, u)
                if edge_key:
                    anims.append(
                        graph.edges[edge_key].animate.set_color(self.theme.SECONDARY_ACCENT).set_stroke(width=4.0)
                    )
                if u in graph.vertices:
                    anims.append(graph.vertices[u].animate.set_fill(self.theme.HIGHLIGHT))
                if v in graph.vertices:
                    anims.append(graph.vertices[v].animate.set_fill(self.theme.HIGHLIGHT))

                if anims:
                    self.play(*anims, run_time=step_time)

        self.animate_continuous_wait(
            duration=duration * 0.1, pulse_targets=[graph], scale_factor=1.06
        )
