# Milestone M2 — Integration, Base Scene & Test Suite Investigation Analysis

## Executive Summary
This analysis investigates the base scene architecture (`BaseDSAScene`), rendering pipeline (`ManimRenderer`), and test suite (`test_manim_animation.py`) for Milestone M2 (Hierarchical & Network Scene Renderers: `TreeScene` and `GraphScene`). It evaluates parameter schemas, subclass validation, existing test cases, code defects, and critical edge cases (empty trees/graphs, single nodes, skewed trees, disconnected graphs, directed cycles, negative weights, and non-deterministic layout positioning).

---

## 1. Parameter Schemas & `BaseDSAScene` Subclass Integration

### 1.1 `BaseDSAScene` Core Parameter Infrastructure
- `BaseDSAScene` in `src/animation/scenes/base_scene.py` provides:
  - `GLOBAL_ALIAS_MAP`: Centralized alias mapping dictionary (e.g. `nodes_data` $\rightarrow$ `nodes`, `nodes_graph` $\rightarrow$ `vertices`, `edge_list` $\rightarrow$ `edges`, `step_time` $\rightarrow$ `step_duration`).
  - `load_parameters(param_path_or_dict, schema, custom_aliases)`: Normalizes alias keys, validates Pydantic schema, and populates `self.params`.
  - `get_parameter(key, default, expected_type)`: Safe parameter retrieval with fallback to alias map and type coercion (`_coerce_type`).
  - `get_step_runtime(total_steps, ...)`: Dynamic step runtime calculation using sub-linear logarithmic damping to prevent rushing or flickering.
  - `animate_continuous_wait(duration, ...)`: Continuous micro-motion wait generator preventing static freeze frames.

### 1.2 `TreeScene` Subclass Parameter Validation & Pydantic Schema
- **Pydantic Schema Specification (`TreeParameters`)**:
  ```python
  class TreeParameters(BaseModel):
      nodes: Optional[Union[List[Optional[Union[int, str]]], Dict[str, Any]]] = Field(
          default_factory=lambda: [1, 2, 3, 4, 5]
      )
      action: str = "display"  # "display", "bfs", "dfs", "insert", "delete"
      new_node: Optional[Union[int, str]] = None
      target_node: Optional[Union[int, str]] = None
      traversal_path: Optional[List[Union[int, str]]] = None
      duration: float = 3.0
      title: Optional[str] = None
  ```
- **Input Format Normalization**:
  - `TreeScene` must handle two input representations:
    1. **Level-Order Array**: `[1, 2, 3, None, 4, 5]`
    2. **Recursive Dict Tree**: `{"val": 1, "left": {"val": 2}, "right": {"val": 3}}`
  - Needs a tree builder utility `_parse_tree_input(raw_nodes)` that normalizes either format into a standard tree node object model prior to visual layout construction.

### 1.3 `GraphScene` Subclass Parameter Validation & Pydantic Schema
- **Pydantic Schema Specification (`GraphParameters`)**:
  ```python
  class GraphParameters(BaseModel):
      vertices: List[Union[int, str]] = Field(default_factory=list)
      edges: List[Union[Tuple[Union[int, str], Union[int, str]], Tuple[Union[int, str], Union[int, str], Union[int, float]], List[Any]]] = Field(default_factory=list)
      directed: bool = False
      layout: str = "kamada_kawai"  # "kamada_kawai", "circular", "spectral", "spring", "planar"
      action: str = "display"  # "display", "bfs", "dfs", "dijkstra", "weighted_edges"
      traversal_path: Optional[List[Union[int, str]]] = None
      shortest_path: Optional[List[Union[int, str]]] = None
      duration: float = 3.0
      title: Optional[str] = None
  ```
- **Input Format Normalization**:
  - Edge inputs must be normalized from `[u, v]`, `[u, v, weight]`, or `{"from": u, "to": v, "weight": w}` into standard tuples `(u, v, weight)`.

---

## 2. Test Suite Investigation (`tests/test_animation/test_manim_animation.py`)

### 2.1 Existing Test Cases Analysis
- **TreeScene Tier 1 Tests**:
  - `T1_TR_01`: `nodes=[1, 2, 3, 4, 5]`, `action="display"`.
  - `T1_TR_02`: `nodes=[1, 2, 3, 4, 5, 6, 7]`, `action="bfs"`.
  - `T1_TR_03`: `nodes=[1, 2, 3, 4, 5]`, `action="dfs"`.
  - `T1_TR_04`: `nodes=[10, 5, 15]`, `action="insert"`, `new_node=2`.
  - `T1_TR_05`: `nodes=[10, 5, 15, 2]`, `action="delete"`, `target_node=5`.
- **GraphScene Tier 1 Tests**:
  - `T1_GR_01`: 5 vertices cyclic graph, `action="display"`.
  - `T1_GR_02`: 4 vertices graph, `action="bfs"`, `traversal_path=[1, 2, 3, 4]`.
  - `T1_GR_03`: 4 vertices graph, `action="dfs"`, `traversal_path=[1, 2, 3, 4]`.
  - `T1_GR_04`: 4 vertices diamond graph, `action="dijkstra"`, `shortest_path=[1, 2, 4]`.
  - `T1_GR_05`: 4 vertices graph, `action="weighted_edges"`.

### 2.2 Critical Code Defects Identified in Existing Scene Code
1. **TreeScene Insertion Defect (`tree_scene.py:110`)**:
   - `action_insert()` hardcodes `nodes_data_new = nodes_data + [4]`, ignoring the `new_node` parameter passed via JSON.
2. **TreeScene Deletion Defect (`tree_scene.py`)**:
   - `action_delete()` is not implemented in `TreeScene`, falling back or using improper defaults.
3. **TreeScene Rigid Heap Array Indexing Defect (`tree_scene.py:45`)**:
   - `build_tree_vgroup` uses 1D binary heap array indexing (`2i+1`, `2i+2`). Sparse level-order arrays or deep trees lead to node overlap or off-screen placement.
4. **GraphScene Layout Instability Defect (`graph_scene.py:28`)**:
   - `create_graph()` uses `layout="spring"` without random seed, causing vertex position jitter and non-deterministic visual output across runs.
5. **Static Wait Defect**:
   - Both scenes currently use `self.wait(...)` with fixed fractions (`duration * 0.2`) instead of `self.animate_continuous_wait(...)` and `self.get_step_runtime(...)`.

### 2.3 Proposed New Test Cases & Fixture Configurations
- **TreeScene Expansion**:
  - `T1_TR_06`: Dict tree input (`{"nodes": {"val": 1, "left": {"val": 2}, "right": {"val": 3}}, "action": "display"}`).
  - `T1_TR_07`: Sparse tree with `None` gaps (`{"nodes": [1, 2, 3, None, 4, None, 5], "action": "bfs"}`).
  - `T1_TR_08`: Skewed left-heavy tree (`{"nodes": [1, 2, None, 3, None, None, None, 4], "action": "dfs"}`).
  - `T1_TR_09`: Single node tree (`{"nodes": [42], "action": "display"}`).
  - `T1_TR_10`: Dynamic insertion value verification (`{"nodes": [10, 5, 15], "action": "insert", "new_node": 99}`).
  - `T1_TR_11`: Dynamic deletion target verification (`{"nodes": [10, 5, 15, 2], "action": "delete", "target_node": 5}`).
  - `T1_TR_12`: Alias key parsing (`{"nodes_data": [1, 2, 3], "action": "display"}`).

- **GraphScene Expansion**:
  - `T1_GR_06`: Directed graph (`{"vertices": [1, 2, 3], "edges": [[1, 2], [2, 3], [3, 1]], "directed": True, "action": "display"}`).
  - `T1_GR_07`: Disconnected graph (`{"vertices": [1, 2, 3, 4], "edges": [[1, 2], [3, 4]], "action": "display"}`).
  - `T1_GR_08`: Weighted edges with negative/float weights (`{"vertices": [1, 2, 3], "edges": [[1, 2, 4.5], [2, 3, -1.0], [1, 3, 2.0]], "action": "weighted_edges"}`).
  - `T1_GR_09`: Deterministic layout check (`{"vertices": [1, 2, 3, 4], "edges": [[1, 2], [2, 3]], "layout": "kamada_kawai", "action": "display"}`).
  - `T1_GR_10`: Single vertex graph (`{"vertices": [1], "edges": [], "action": "display"}`).
  - `T1_GR_11`: Alias key resolution (`{"nodes_graph": [1, 2], "connections": [[1, 2]], "action": "display"}`).

---

## 3. Edge Case Matrix & Mitigation Strategies

| Area | Edge Case | Risk / Failure Mode | Proposed Mitigation Strategy |
|---|---|---|---|
| **Tree** | Empty Tree (`nodes = []`) | `IndexError` or 0-frame video output | Graceful fallback returning empty canvas with header title & continuous wait |
| **Tree** | Single Node (`nodes = [42]`) | Edge loop failure | Place single root node at center `(0, 0, 0)` without edge creation |
| **Tree** | Skewed Tree (height $> 4$) | Heap array index overflow & node visual overlap | Implement dynamic tree layout algorithm (e.g. Reingold-Tilford or recursive level bounding boxes) |
| **Tree** | Dict Tree Input Format | `TypeError` or array parsing failure | Unified `_parse_tree_input()` handler converting dicts or arrays to tree node objects |
| **Tree** | Dynamic `new_node` / `target_node` | Hardcoded value `4` inserted, deletion ignored | Access parameter dynamically via `get_parameter("new_node")` / `get_parameter("target_node")` |
| **Graph** | Empty Graph (`vertices = []`) | Manim `Graph` instantiation error | Graceful fallback returning header title and continuous wait |
| **Graph** | Single Vertex (`vertices = [1]`) | Empty edge list error in NetworkX / Manim | Render single vertex node without edges |
| **Graph** | Disconnected Components | Nodes pushed off-screen by spring physics | Use deterministic layout (`kamada_kawai` or `circular`) with bounded canvas scaling |
| **Graph** | Directed Graph (`directed = True`) | Undirected straight lines rendered | Use `manim.DiGraph` or attach arrow mobjects to edges |
| **Graph** | Negative / Floating Edge Weights | Text label overlap or Dijkstra visualization error | Render weight badges at edge midpoints and handle negative weights in path tracing |
| **Graph** | Spring Layout Randomness | Non-deterministic node positioning across renders | Default layout to `"kamada_kawai"` or set fixed random seed |

---

## 4. Proposed Code Modifications (Patches / Design Sketches)

### 4.1 Proposed `TreeScene` Refactoring Sketch (`src/animation/scenes/tree_scene.py`)
```python
class TreeScene(BaseDSAScene):
    def setup(self):
        super().setup()
        self.load_parameters(schema=TreeParameters)

    def construct_dsa_animation(self):
        if not MANIM_AVAILABLE:
            return
        
        nodes_raw = self.get_parameter("nodes", [1, 2, 3, 4, 5])
        action = self.get_parameter("action", "display")
        duration = self.get_parameter("duration", 3.0, expected_type=float)
        
        root = self._parse_tree_input(nodes_raw)
        if root is None:
            self.animate_continuous_wait(duration=duration)
            return

        if action == "bfs":
            self.action_bfs(root, duration)
        elif action == "dfs":
            self.action_dfs(root, duration)
        elif action == "insert":
            new_node = self.get_parameter("new_node", 4)
            self.action_insert(root, new_node, duration)
        elif action == "delete":
            target_node = self.get_parameter("target_node", None)
            self.action_delete(root, target_node, duration)
        else:
            self.action_display(root, duration)
```

### 4.2 Proposed `GraphScene` Refactoring Sketch (`src/animation/scenes/graph_scene.py`)
```python
class GraphScene(BaseDSAScene):
    def setup(self):
        super().setup()
        self.load_parameters(schema=GraphParameters)

    def create_graph(self):
        vertices = self.get_parameter("vertices", [1, 2, 3, 4], expected_type=list)
        edges_raw = self.get_parameter("edges", [[1, 2], [2, 3], [3, 4], [4, 1]], expected_type=list)
        is_directed = self.get_parameter("directed", False, expected_type=bool)
        layout_type = self.get_parameter("layout", "kamada_kawai", expected_type=str)
        
        if not vertices:
            return None, {}

        parsed_edges, weights = self._parse_edges(edges_raw)
        
        if is_directed:
            graph = manim.DiGraph(
                vertices, parsed_edges,
                layout=layout_type,
                vertex_config={"radius": 0.4, "color": self.theme.BORDER, "fill_color": self.theme.CONTAINER_BG, "fill_opacity": 1},
                edge_config={"stroke_color": self.theme.PRIMARY_ACCENT},
                labels=True
            )
        else:
            graph = manim.Graph(
                vertices, parsed_edges,
                layout=layout_type,
                vertex_config={"radius": 0.4, "color": self.theme.BORDER, "fill_color": self.theme.CONTAINER_BG, "fill_opacity": 1},
                edge_config={"stroke_color": self.theme.PRIMARY_ACCENT},
                labels=True
            )
        return graph, weights
```

---
