from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from src.animation.scenes.base_scene import (
    MANIM_AVAILABLE,
    BaseDSAScene,
    TreeSceneSchema,
)

if MANIM_AVAILABLE:
    import manim
    from manim import VGroup, Circle, Text, Line, FadeIn, FadeOut, Transform, Create


class TreeNodeInternal:
    """Internal binary tree node representation supporting dicts, level-order lists, and scalars."""

    def __init__(
        self,
        val: Any,
        left: Optional["TreeNodeInternal"] = None,
        right: Optional["TreeNodeInternal"] = None,
    ):
        self.val = val
        self.left = left
        self.right = right


def parse_tree_input(data: Any) -> Optional[TreeNodeInternal]:
    """Parses nested dicts, level-order arrays with None gaps, or scalar values into a TreeNodeInternal tree."""
    if data is None:
        return None
    if isinstance(data, dict):
        val = data.get("val", data.get("value", data.get("v")))
        if val is None:
            return None
        left = parse_tree_input(data.get("left", data.get("l")))
        right = parse_tree_input(data.get("right", data.get("r")))
        return TreeNodeInternal(val, left, right)
    elif isinstance(data, (list, tuple)):
        if not data or data[0] is None:
            return None
        root = TreeNodeInternal(data[0])
        queue = [root]
        idx = 1
        n = len(data)
        while idx < n and queue:
            curr = queue.pop(0)
            if idx < n:
                if data[idx] is not None:
                    curr.left = TreeNodeInternal(data[idx])
                    queue.append(curr.left)
                idx += 1
            if idx < n:
                if data[idx] is not None:
                    curr.right = TreeNodeInternal(data[idx])
                    queue.append(curr.right)
                idx += 1
        return root
    else:
        return TreeNodeInternal(data)


def count_tree_nodes(root: Optional[TreeNodeInternal]) -> int:
    if not root:
        return 0
    return 1 + count_tree_nodes(root.left) + count_tree_nodes(root.right)


def get_tree_height(root: Optional[TreeNodeInternal]) -> int:
    if not root:
        return 0
    return 1 + max(get_tree_height(root.left), get_tree_height(root.right))


class TreeScene(BaseDSAScene):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.load_parameters(schema=TreeSceneSchema)

    def construct_dsa_animation(self) -> None:
        if not MANIM_AVAILABLE:
            return

        action = str(self.get_parameter("action", "display")).lower()

        if action == "bfs":
            self.action_bfs()
        elif action == "dfs":
            self.action_dfs()
        elif action == "insert":
            self.action_insert()
        elif action in ("delete", "remove"):
            self.action_delete()
        else:
            self.action_display()

    def compute_tree_layout(
        self, root: Optional[TreeNodeInternal]
    ) -> Tuple[Dict[TreeNodeInternal, np.ndarray], float]:
        """2-pass layout algorithm: in-order X position calculation + post-order parent centering."""
        if not root:
            return {}, 0.4

        N = count_tree_nodes(root)
        radius = max(0.25, min(0.4, 3.5 / max(1, N)))

        H = get_tree_height(root)
        y_spacing = min(1.3, 4.8 / max(1, H - 1)) if H > 1 else 0.0
        y_top = (H - 1) * y_spacing / 2.0 if H > 1 else 0.0

        inorder_nodes: List[TreeNodeInternal] = []
        node_depths: Dict[TreeNodeInternal, int] = {}

        def inorder(node: Optional[TreeNodeInternal], depth: int) -> None:
            if not node:
                return
            node_depths[node] = depth
            inorder(node.left, depth + 1)
            inorder_nodes.append(node)
            inorder(node.right, depth + 1)

        inorder(root, 0)

        W = len(inorder_nodes) - 1 if len(inorder_nodes) > 1 else 1
        x_step = min(1.6, 10.0 / max(1, W))

        pos_x: Dict[TreeNodeInternal, float] = {}
        for idx, node in enumerate(inorder_nodes):
            pos_x[node] = (idx - W / 2.0) * x_step

        def center_parents(node: Optional[TreeNodeInternal]) -> None:
            if not node:
                return
            center_parents(node.left)
            center_parents(node.right)
            if node.left and node.right:
                pos_x[node] = (pos_x[node.left] + pos_x[node.right]) / 2.0
            elif node.left:
                pos_x[node] = pos_x[node.left] + x_step * 0.35
            elif node.right:
                pos_x[node] = pos_x[node.right] - x_step * 0.35

        center_parents(root)

        positions: Dict[TreeNodeInternal, np.ndarray] = {}
        for node in inorder_nodes:
            y = y_top - node_depths[node] * y_spacing
            positions[node] = np.array([pos_x[node], y, 0.0])

        return positions, radius

    def build_tree_mobjects(
        self, root: Optional[TreeNodeInternal]
    ) -> Tuple[
        Any,
        Dict[TreeNodeInternal, Any],
        List[Tuple[TreeNodeInternal, TreeNodeInternal, Any]],
    ]:
        """Builds Manim tree Mobjects (circles, text labels, and perimeter-buffered edge lines)."""
        if not root:
            text_sec = getattr(self.theme, "TEXT_SECONDARY", self.theme.PRIMARY_ACCENT)
            placeholder = Text("Empty Tree", color=text_sec, font_size=24)
            return VGroup(placeholder), {}, []

        positions, radius = self.compute_tree_layout(root)

        node_mobjects: Dict[TreeNodeInternal, Any] = {}
        edge_list: List[Tuple[TreeNodeInternal, TreeNodeInternal, Any]] = []
        edges_vg = VGroup()
        nodes_vg = VGroup()

        def create_nodes_and_edges(node: Optional[TreeNodeInternal]) -> None:
            if not node:
                return
            pos = positions[node]
            c = Circle(
                radius=radius,
                color=self.theme.BORDER,
                fill_color=self.theme.CONTAINER_BG,
                fill_opacity=1.0,
                stroke_width=2.5,
            )
            t = Text(str(node.val), color=self.theme.TEXT_PRIMARY).scale(max(0.3, radius * 1.1))
            t.move_to(pos)
            c.move_to(pos)
            vg = VGroup(c, t)
            node_mobjects[node] = vg
            nodes_vg.add(vg)

            for child in (node.left, node.right):
                if child:
                    create_nodes_and_edges(child)
                    child_pos = positions[child]
                    line = Line(
                        pos,
                        child_pos,
                        buff=radius,
                        color=self.theme.PRIMARY_ACCENT,
                        stroke_width=2.5,
                    )
                    edges_vg.add(line)
                    edge_list.append((node, child, line))

        create_nodes_and_edges(root)
        tree_vg = VGroup(edges_vg, nodes_vg)
        return tree_vg, node_mobjects, edge_list

    def action_display(self) -> None:
        raw_nodes = self.get_parameter("nodes", default=[1, 2, 3, None, 4, 5])
        duration = float(self.get_parameter("duration", default=5.0))

        root = parse_tree_input(raw_nodes)
        tree_vg, node_mobs, _ = self.build_tree_mobjects(root)

        anim_time = self.get_step_runtime(1, default_step_time=duration * 0.8)
        self.play(Create(tree_vg), run_time=anim_time)

        target_mobs = [v[0] for v in node_mobs.values()] if node_mobs else [tree_vg]
        wait_time = max(0.2, duration - anim_time)
        self.animate_continuous_wait(duration=wait_time, pulse_targets=target_mobs, scale_factor=1.10)

    def action_bfs(self) -> None:
        raw_nodes = self.get_parameter("nodes", default=[1, 2, 3, 4, 5, 6, 7])
        duration = float(self.get_parameter("duration", default=5.0))

        root = parse_tree_input(raw_nodes)
        tree_vg, node_mobs, edge_tuples = self.build_tree_mobjects(root)

        init_time = self.get_step_runtime(10, default_step_time=duration * 0.3)
        self.play(Create(tree_vg), run_time=init_time)

        if root:
            bfs_nodes: List[TreeNodeInternal] = []
            bfs_edges: List[Optional[Any]] = []
            q: List[Tuple[TreeNodeInternal, Optional[Any]]] = [(root, None)]

            while q:
                curr, edge = q.pop(0)
                bfs_nodes.append(curr)
                bfs_edges.append(edge)
                for child in (curr.left, curr.right):
                    if child:
                        ch_edge = None
                        for p, c, l in edge_tuples:
                            if p == curr and c == child:
                                ch_edge = l
                                break
                        q.append((child, ch_edge))

            step_time = self.get_step_runtime(
                len(bfs_nodes), default_step_time=0.6, target_duration=duration * 0.6
            )
            for idx, node in enumerate(bfs_nodes):
                anims = []
                if node in node_mobs:
                    anims.append(node_mobs[node][0].animate.set_fill(self.theme.HIGHLIGHT))
                if idx < len(bfs_edges) and bfs_edges[idx] is not None:
                    anims.append(
                        bfs_edges[idx].animate.set_color(self.theme.HIGHLIGHT).set_stroke(width=4)
                    )
                if anims:
                    self.play(*anims, run_time=step_time)

        target_mobs = [v[0] for v in node_mobs.values()] if node_mobs else [tree_vg]
        self.animate_continuous_wait(duration=duration * 0.1, pulse_targets=target_mobs, scale_factor=1.06)

    def action_dfs(self) -> None:
        raw_nodes = self.get_parameter("nodes", default=[1, 2, 3, 4, 5])
        duration = float(self.get_parameter("duration", default=5.0))

        root = parse_tree_input(raw_nodes)
        tree_vg, node_mobs, edge_tuples = self.build_tree_mobjects(root)

        init_time = self.get_step_runtime(10, default_step_time=duration * 0.3)
        self.play(Create(tree_vg), run_time=init_time)

        if root:
            dfs_steps: List[Tuple[TreeNodeInternal, Optional[Any]]] = []

            def dfs(curr: Optional[TreeNodeInternal], edge: Optional[Any]) -> None:
                if not curr:
                    return
                dfs_steps.append((curr, edge))
                for child in (curr.left, curr.right):
                    if child:
                        ch_edge = None
                        for p, c, l in edge_tuples:
                            if p == curr and c == child:
                                ch_edge = l
                                break
                        dfs(child, ch_edge)

            dfs(root, None)

            step_time = self.get_step_runtime(
                len(dfs_steps), default_step_time=0.6, target_duration=duration * 0.6
            )
            for node, edge in dfs_steps:
                anims = []
                if node in node_mobs:
                    anims.append(node_mobs[node][0].animate.set_fill(self.theme.HIGHLIGHT))
                if edge is not None:
                    anims.append(
                        edge.animate.set_color(self.theme.HIGHLIGHT).set_stroke(width=4)
                    )
                if anims:
                    self.play(*anims, run_time=step_time)

        target_mobs = [v[0] for v in node_mobs.values()] if node_mobs else [tree_vg]
        self.animate_continuous_wait(duration=duration * 0.1, pulse_targets=target_mobs[:3])

    def action_insert(self) -> None:
        raw_nodes = self.get_parameter("nodes", default=[10, 5, 15])
        new_val = self.get_parameter("new_node", default=None)
        if new_val is None:
            new_val = self.get_parameter("insert_value", default=4)

        duration = float(self.get_parameter("duration", default=5.0))

        root = parse_tree_input(raw_nodes)
        tree_vg, node_mobs, _ = self.build_tree_mobjects(root)

        init_time = self.get_step_runtime(2, default_step_time=duration * 0.4)
        self.play(Create(tree_vg), run_time=init_time)

        def insert_into_tree(r: Optional[TreeNodeInternal], val: Any) -> TreeNodeInternal:
            if not r:
                return TreeNodeInternal(val)

            def is_bst(node: Optional[TreeNodeInternal], min_v: Any, max_v: Any) -> bool:
                if not node:
                    return True
                try:
                    v = float(node.val)
                    if min_v is not None and v <= min_v:
                        return False
                    if max_v is not None and v >= max_v:
                        return False
                    return is_bst(node.left, min_v, v) and is_bst(node.right, v, max_v)
                except (ValueError, TypeError):
                    return False

            if is_bst(r, None, None):

                def bst_insert(node: Optional[TreeNodeInternal], v: Any) -> TreeNodeInternal:
                    if not node:
                        return TreeNodeInternal(v)
                    try:
                        if float(v) < float(node.val):
                            node.left = bst_insert(node.left, v)
                        else:
                            node.right = bst_insert(node.right, v)
                    except (ValueError, TypeError):
                        if node.left is None:
                            node.left = TreeNodeInternal(v)
                        else:
                            node.right = bst_insert(node.right, v)
                    return node

                return bst_insert(r, val)
            else:
                q = [r]
                while q:
                    curr = q.pop(0)
                    if not curr.left:
                        curr.left = TreeNodeInternal(val)
                        break
                    else:
                        q.append(curr.left)
                    if not curr.right:
                        curr.right = TreeNodeInternal(val)
                        break
                    else:
                        q.append(curr.right)
                return r

        updated_root = insert_into_tree(root, new_val)
        new_tree_vg, new_node_mobs, _ = self.build_tree_mobjects(updated_root)

        step_time = self.get_step_runtime(2, default_step_time=duration * 0.5)
        self.play(Transform(tree_vg, new_tree_vg), run_time=step_time)

        target_mobs = [v[0] for v in new_node_mobs.values()] if new_node_mobs else [tree_vg]
        self.animate_continuous_wait(duration=duration * 0.1, pulse_targets=target_mobs, scale_factor=1.06)

    def action_delete(self) -> None:
        raw_nodes = self.get_parameter("nodes", default=[10, 5, 15, 2])
        target_val = self.get_parameter("target_node", default=None)
        if target_val is None:
            target_val = self.get_parameter("delete_node", default=5)

        duration = float(self.get_parameter("duration", default=5.0))

        root = parse_tree_input(raw_nodes)
        tree_vg, node_mobs, _ = self.build_tree_mobjects(root)

        init_time = self.get_step_runtime(3, default_step_time=duration * 0.35)
        self.play(Create(tree_vg), run_time=init_time)

        target_mob_key = None
        for n_obj in node_mobs:
            if str(n_obj.val) == str(target_val):
                target_mob_key = n_obj
                break

        if target_mob_key and target_mob_key in node_mobs:
            self.play(
                node_mobs[target_mob_key][0].animate.set_fill(self.theme.SECONDARY_ACCENT),
                run_time=init_time * 0.5,
            )

        def delete_from_tree(
            r: Optional[TreeNodeInternal], val: Any
        ) -> Optional[TreeNodeInternal]:
            if not r:
                return None
            if str(r.val) == str(val):
                if not r.left:
                    return r.right
                if not r.right:
                    return r.left
                succ_parent = r
                succ = r.right
                while succ.left:
                    succ_parent = succ
                    succ = succ.left
                r.val = succ.val
                if succ_parent != r:
                    succ_parent.left = succ.right
                else:
                    succ_parent.right = succ.right
                return r
            r.left = delete_from_tree(r.left, val)
            r.right = delete_from_tree(r.right, val)
            return r

        updated_root = delete_from_tree(root, target_val)
        new_tree_vg, new_node_mobs, _ = self.build_tree_mobjects(updated_root)

        step_time = self.get_step_runtime(3, default_step_time=duration * 0.5)
        self.play(Transform(tree_vg, new_tree_vg), run_time=step_time)

        target_mobs = [v[0] for v in new_node_mobs.values()] if new_node_mobs else [tree_vg]
        self.animate_continuous_wait(duration=duration * 0.15, pulse_targets=target_mobs, scale_factor=1.06)
