# Deep Technical Analysis & Refactoring Specification: `TreeScene` (`src/animation/scenes/tree_scene.py`)

## 1. Parameter Parsing Flaws & Complete 1D Heap Indexing Failure

### 1.1 Current Parameter Parsing Flaws
- **Direct Parameter Access**: In `tree_scene.py`, parameters are parsed via `self.params.get("nodes", ...)` directly (lines 60, 68, 80, 104).
- **Bypassing `BaseDSAScene` Normalization**: This bypasses `self.get_parameter(...)`, missing canonical alias resolution (e.g. `"tree"`, `"root"`, `"nodes_data"`, `"node_list"`, `"vals"`) and safe type coercion provided by `BaseDSAScene`.

### 1.2 Mathematical & Algorithmic Failure of 1D Heap Indexing (`2i+1`, `2i+2`)
In `build_tree_vgroup`:
```python
def layout_node(idx, x, y, dx):
    if idx < len(nodes) and nodes[idx] is not None:
        nodes[idx].move_to([x, y, 0])
        left_idx = 2 * idx + 1
        right_idx = 2 * idx + 2
        if left_idx < len(nodes) and nodes[left_idx] is not None:
            layout_node(left_idx, x - dx, y - 1.2, dx * 0.5)
            ...
```

- **Heap Indexing Formula**: The formula $left = 2i + 1$ and $right = 2i + 2$ holds **only** for complete binary heaps where every array index represents a node position in a perfect/complete tree grid.
- **Breakdown on Level-Order Lists with `None` Gaps**:
  In standard level-order serialization (LeetCode convention):
  - Null subtrees are represented as `None` in the queue expansion stream.
  - Intermediate `None` values are *not* expanded into $2^k$ dummy `None` placeholders for all missing descendants at deeper levels.
  - **Concrete Counter-Example**: Consider tree `[1, 2, 3, None, 4]`:
    - Root `1` is at index 0. Left child `2` (index 1), Right child `3` (index 2).
    - Under heap formula for index 1 (`2`): $left = 2(1)+1 = 3$ (value `None`), $right = 2(1)+2 = 4$ (value `4`). Correct for node 2.
    - Under heap formula for index 2 (`3`): $left = 2(2)+1 = 5$ (Out of bounds!), $right = 2(2)+2 = 6$ (Out of bounds!). Node `3` appears childless under heap indexing even if `5` and `6` existed elsewhere in array!
  - **Concrete Counter-Example 2**: `[1, None, 2, None, 3]`:
    - Root `1` at index 0. Heap left index 1 (`None`), right index 2 (`2`).
    - Index 2 (`2`): Heap left index $2(2)+1=5$ (Out of bounds), Heap right index $2(2)+2=6$ (Out of bounds). But in level-order, node `2`'s child is at index 4 (`3`)!
  - **Conclusion**: Heap indexing formula $2i+1$ / $2i+2$ fails catastrophically on general binary trees with missing nodes or level-order arrays with `None` gaps.

### 1.3 Binary Tree Dictionary Structural Failure
- If `nodes` is passed as a nested dictionary (e.g. `{"val": 1, "left": {"val": 2}, "right": {"val": 3}}`), line 31 (`for val in nodes_data:`) iterates over dictionary keys (`"val"`, `"left"`, `"right"`).
- This produces circle nodes labeled `"val"`, `"left"`, `"right"`, completely failing to parse the tree topology.

### 1.4 Rigid Visual Layout & Node Overlap Bottlenecks
- `layout_node` divides `dx` by 2 at each level (`dx * 0.5`).
- Starting at level 0 with $dx = 2.0$:
  - Level 1: $dx = 1.0$
  - Level 2: $dx = 0.5$
  - Level 3: $dx = 0.25$
  - Level 4: $dx = 0.125$
- Manim `Circle(radius=0.4)` has a diameter of $0.8$.
- At depth 3, adjacent sibling/cousin node centers are separated by $2 \times 0.25 = 0.5$ units. Because $0.5 < 0.8$, node circles **visually collide and overlap horizontally**, making labels illegible.
- Fixed vertical step `y - 1.2` ignores tree height $H$, risking off-screen clipping at canvas top/bottom.

### 1.5 Flawed Edge Attachment Mechanics
- Lines 49 & 52: `Line(nodes[idx].get_bottom(), nodes[left_idx].get_top())`.
- `get_bottom()` attaches to the exact $(x, y - R)$ point of the parent circle. For diagonal edges, this creates an ugly angled line originating from the parent's bottom center rather than pointing from parent center to child center trimmed at circle boundaries.

---

## 2. Hardcoded Values & Missing Tree Actions Analysis

### 2.1 Hardcoded Node Insertion Value
- `tree_scene.py:110`: `nodes_data_new = nodes_data + [4]`
- Hardcodes value `4`! Bypasses parameter inputs (`new_node`, `insert_val`, `val`, `element`).
- Test `T1_TR_04` passes `{"nodes": [10, 5, 15], "action": "insert", "new_node": 2, "duration": 3.5}`. Current code ignores `new_node: 2` and inserts `4`.

### 2.2 Missing Tree Action: `delete`
- Test `T1_TR_05` tests `{"nodes": [10, 5, 15, 2], "action": "delete", "target_node": 5, "duration": 3.5}`.
- `construct_dsa_animation` only checks `"bfs"`, `"dfs"`, `"insert"`. `"delete"` defaults to `action_display()`, failing requirement R1 & R2.

### 2.3 Static `self.wait()` Pauses & Unconstrained Timing Violations
- Static `self.wait(duration * 0.2)` or `self.wait(duration * 0.1)` present in all actions.
- Fixed step duration slicing `(duration * 0.8) / N` creates rapid acceleration for large trees or sluggish step holds for small trees.
- Requires complete replacement with `self.get_step_runtime(...)` and `self.animate_continuous_wait(...)`.

---

## 3. Unified Binary Tree Data Parsing Engine Design

### 3.1 `TreeNode` Data Class
```python
class TreeNode:
    def __init__(self, val: Any):
        self.val = val
        self.left: Optional['TreeNode'] = None
        self.right: Optional['TreeNode'] = None
        self.x: float = 0.0
        self.y: float = 0.0
        self.inorder_idx: int = 0
        self.depth: int = 0
        self.mobject: Optional[Any] = None  # VGroup(Circle, Text)
```

### 3.2 Deserialization Engine Architecture

#### A. Dictionary Tree Parser (`parse_dict_tree`)
Supports arbitrary nested dictionaries:
```python
def parse_dict_tree(data: Dict[str, Any]) -> Optional[TreeNode]:
    if not isinstance(data, dict):
        if data is not None:
            return TreeNode(data)
        return None

    # Key aliases for value
    val = None
    for key in ("val", "value", "data", "id", "label"):
        if key in data:
            val = data[key]
            break
    if val is None and "val" not in data:
        return None

    node = TreeNode(val)
    left_data = data.get("left")
    right_data = data.get("right")

    if left_data is not None:
        node.left = parse_dict_tree(left_data) if isinstance(left_data, dict) else TreeNode(left_data)
    if right_data is not None:
        node.right = parse_dict_tree(right_data) if isinstance(right_data, dict) else TreeNode(right_data)

    return node
```

#### B. Level-Order Array Parser (`parse_level_order_array`)
Queue-based BFS deserialization algorithm:
```python
def parse_level_order_array(arr: List[Any]) -> Optional[TreeNode]:
    if not arr or arr[0] is None:
        return None
    root = TreeNode(arr[0])
    queue = [root]
    i = 1
    while queue and i < len(arr):
        curr = queue.pop(0)
        # Left child
        if i < len(arr):
            if arr[i] is not None:
                curr.left = TreeNode(arr[i])
                queue.append(curr.left)
            i += 1
        # Right child
        if i < len(arr):
            if arr[i] is not None:
                curr.right = TreeNode(arr[i])
                queue.append(curr.right)
            i += 1
    return root
```

#### C. Unified Parsing Entry Point (`parse_tree_input`)
```python
def parse_tree_input(raw_input: Any) -> Optional[TreeNode]:
    if raw_input is None:
        return None
    if isinstance(raw_input, dict):
        return parse_dict_tree(raw_input)
    if isinstance(raw_input, (list, tuple)):
        return parse_level_order_array(list(raw_input))
    return TreeNode(raw_input)
```

---

## 4. Dynamic Tree Node Layout & Positioning Algorithm Design

### 4.1 In-Order Traversal X-Coordinate Positioning Algorithm
To guarantee **zero horizontal node overlaps** and maintain natural left-to-right ordering across arbitrary tree topologies:

1. **In-Order Traversal Indexing**:
   Perform in-order traversal (Left $\to$ Root $\to$ Right), assigning each node an integer index `inorder_idx` (0, 1, 2, ..., $N-1$).
2. **Depth Determination**:
   Track depth $d$ for each node ($d=0$ for root, $d_{child} = d_{parent} + 1$). Track $H = \max(d)$.
3. **Dynamic Coordinate Calculation**:
   - Total node count $N$.
   - Max horizontal span $W_{max} = 11.0$, max vertical span $H_{max} = 5.0$.
   - Horizontal spacing:
     $$x\_spacing = \begin{cases} \min\left(1.8, \frac{11.0}{N-1}\right) & \text{if } N > 1 \\ 0.0 & \text{if } N = 1 \end{cases}$$
     $$x\_offset = -\frac{(N - 1) \times x\_spacing}{2}$$
     $$node.x = x\_offset + node.inorder\_idx \times x\_spacing$$
   - Vertical spacing:
     $$y\_spacing = \min\left(1.4, \frac{5.0}{\max(1, H)}\right)$$
     $$node.y = 2.0 - node.depth \times y\_spacing$$

4. **Mathematical Anti-Collision Proof**:
   - Since every node gets a unique in-order traversal index $i \in [0, N-1]$, $x_i \ne x_j$ for all $i \ne j$.
   - Left child is visited before parent $\implies x_{left} < x_{parent}$.
   - Right child is visited after parent $\implies x_{right} > x_{parent}$.
   - Minimum horizontal spacing between any two nodes is $\ge x\_spacing$, preventing overlap regardless of tree symmetry or depth.

### 4.2 Edge Trim Vector Calculation
For parent center $(x_p, y_p)$ and child center $(x_c, y_c)$, circle radius $R = 0.4$:
$$\vec{d} = (x_c - x_p, y_c - y_p), \quad L = \sqrt{(x_c - x_p)^2 + (y_c - y_p)^2}$$
$$\hat{u} = \left(\frac{x_c - x_p}{L}, \frac{y_c - y_p}{L}\right)$$
- `start_point` = $(x_p, y_p) + \hat{u} \cdot R$
- `end_point` = $(x_c, y_c) - \hat{u} \cdot R$
- Edge Line: `Line(start_point, end_point, color=theme.PRIMARY_ACCENT, stroke_width=3.0)`

---

## 5. Animation Routines Design

### 5.1 Traversal Animations (`bfs` & `dfs`) with Pulsing Glow
- **Queue BFS / DFS Traversal Sequence**:
  Collect sequence of `(parent_node, curr_node)` tuples.
- **Per-Step Highlight Routine**:
  1. Dynamic step duration $T_{step} = \text{self.get\_step\_runtime}(total\_steps=N, default\_step\_time=1.0)$.
  2. If parent exists, animate incoming edge stroke color shift to `theme.SECONDARY_ACCENT` and stroke width expansion to `5.0`.
  3. Animate node circle fill change to `theme.HIGHLIGHT` with a subtle scale pulse (`scale(1.15) -> scale(1.0)` using `there_and_back` rate function).
  4. Spawn temporary glowing halo ring `Circle(radius=0.55, color=theme.HIGHLIGHT, opacity=0.8)` that expands to radius `0.75` and fades out.
- **Anti-Freeze Hold**:
  Call `self.animate_continuous_wait(duration=remaining_time, pulse_targets=visited_mobjects)` at completion.

### 5.2 Dynamic Insertion Animation (`action_insert`)
1. Parameter Extraction: Extract `new_node_val` from parameters (`new_node`, `insert_val`, `val`, `element`, defaulting to 4).
2. Render base tree $T$ ($N$ nodes) with `manim.Create`.
3. Compute insertion parent and slot (BST rules or level-order first open child slot).
4. Animate traversal path to insertion parent using edge/node pulse highlights.
5. Add new node to tree data structure, creating updated tree $T'$ ($N+1$ nodes).
6. Recalculate in-order positions for $T'$.
7. Animate simultaneous transition:
   - Existing tree nodes shift smoothly to their new positions in $T'$ using `node.animate.move_to(...)`.
   - Connected edges update endpoints dynamically.
   - New node appears at target position using `GrowFromCenter(new_node_vg)`.
   - New edge draws from parent to new node using `manim.Create(new_edge)`.
8. Final anti-freeze hold via `animate_continuous_wait()`.

### 5.3 Dynamic Deletion Animation (`action_delete`)
1. Parameter Extraction: Extract `target_val` from parameters (`target_node`, `delete_val`, `val`, `element`).
2. Render base tree $T$.
3. Animate traversal path to target node. Highlight target node in `theme.WARNING` / `theme.SECONDARY_ACCENT` (alert color).
4. Fade out target node `FadeOut(target_mobject)` and shrink/fade connected edges.
5. Re-link tree data structure (standard BST deletion / subtree shift).
6. Recalculate layout for remaining $N-1$ nodes.
7. Animate remaining node mobjects smoothly shifting to updated coordinates.
8. Final anti-freeze hold via `animate_continuous_wait()`.

---

## 6. Continuous Timing & Anti-Freeze Replacement Plan

| Scene Function | Legacy Freeze Code | Proposed Anti-Freeze Code |
|---|---|---|
| `action_display` | `self.wait(duration * 0.2)` | `self.animate_continuous_wait(duration=rem_time, pulse_targets=all_nodes)` |
| `action_bfs` step time | `step_time = (duration * 0.8) / N` | `step_time = self.get_step_runtime(total_steps=N)` |
| `action_bfs` hold | `self.wait(duration * 0.2)` | `self.animate_continuous_wait(duration=rem_time, pulse_targets=visited_nodes)` |
| `action_dfs` step time | `step_time = (duration * 0.8) / N` | `step_time = self.get_step_runtime(total_steps=N)` |
| `action_dfs` hold | `self.wait(duration * 0.2)` | `self.animate_continuous_wait(duration=rem_time, pulse_targets=visited_nodes)` |
| `action_insert` step time | `duration * 0.4`, `duration * 0.5` | `self.get_step_runtime(total_steps=steps_count)` |
| `action_insert` hold | `self.wait(duration * 0.1)` | `self.animate_continuous_wait(duration=rem_time, pulse_targets=all_nodes)` |
| `action_delete` | Missing | Implemented with `get_step_runtime()` and `animate_continuous_wait()` |

