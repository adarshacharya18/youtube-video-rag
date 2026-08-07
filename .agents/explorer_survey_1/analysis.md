# Codebase Survey Analysis: Parameter Parsing and Scene Template Architecture

## 1. Executive Summary

This report presents an architectural investigation of the Manim visualization subsystem in `/home/adarsh/Documents/Youtube-Channel/src/animation/`. The survey evaluates how animation parameters are loaded, passed, and rendered across all 9 scene templates (`linkedlist_scene.py`, `array_scene.py`, `tree_scene.py`, `graph_scene.py`, `hashmap_scene.py`, `stack_queue_scene.py`, `code_scene.py`, `complexity_scene.py`, `title_scene.py`). 

The current architecture provides a functional baseline with `BaseDSAScene` handling parameter ingestion from `parameters.json`, `ManimRenderer` managing CLI subprocess execution, and `AnimationGeneratorNode` bridging pipeline script payloads into rendered MP4 clips. However, significant gaps exist between the current implementation and **Objective R1** (Dynamic Custom Input & Parameter Parsing). Key deficiencies include hardcoded fallback operations, ignored custom parameter keys, inflexible step animations, fragile indexing/layout logic, and lack of parameter validation across scene types.

---

## 2. Codebase Architecture & Parameter Flow

### 2.1 Component Overview & Integration Architecture

The animation rendering pipeline follows a 4-tier lifecycle:

```
[LLM Script Generation] 
        │
        ▼ (VisualCue.parameters dict)
[AnimationGeneratorNode]
        │
        ▼ Writes parameters.json & invokes
[ManimRenderer] (Subprocess: manim render -ql -o segment_X.mp4 ...)
        │
        ▼ Instantiates scene class (cwd = output_dir)
[BaseDSAScene Subclass] ──> reads parameters.json in __init__/setup/construct
```

### 2.2 Lifecycle & Method Signatures in `BaseDSAScene`

Location: `src/animation/scenes/base_scene.py`

- **`__init__(self, *args, **kwargs)`**: Initializes `self.theme = DEFAULT_THEME`, `self.params = {}`, and immediately invokes `self.load_params_from_json()`.
- **`load_params_from_json(self, json_path: Optional[str] = None) -> Dict[str, Any]`**: Checks candidate paths in order:
  1. `json_path` (if explicitly provided)
  2. `Path("parameters.json")`
  3. `Path.cwd() / "parameters.json"`
  
  Reads and parses JSON content into `self.params`. If parsing fails or the file does not exist, `self.params` remains empty or retains its previous state.
- **`setup(self) -> None`**: Manim setup lifecycle hook. Re-checks `self.params` and reloads if empty.
- **`construct(self) -> None`**: Main entrypoint invoked by the Manim CLI binary (`manim render ...`). Ensures `self.params` is populated, executes `self.setup_scene_header()`, and calls `self.construct_dsa_animation()`.
- **`render_with_params(self, params: Dict[str, Any]) -> None`**: Direct programmatic entrypoint for custom wrapper scripts. Sets `self.params = params` directly and triggers header setup and animation construction.
- **`setup_scene_header(self) -> None`**: Evaluates `self.params.get("title", "")`. If non-empty, creates a `Text` mobject with `font_size=28` and `color=self.theme.PRIMARY_ACCENT`, positioned at `UP + LEFT` with `buff=0.5`.
- **`construct_dsa_animation(self) -> None`**: Abstract method overridden by concrete scene subclasses to construct domain-specific animations.

### 2.3 Subprocess Rendering via `ManimRenderer`

Location: `src/animation/renderer.py`

`ManimRenderer.render()` is invoked with `scene_script`, `class_name`, `output_dir`, `output_filename`, and `parameters`.
1. If `parameters` is provided, `ManimRenderer` serializes it to `output_dir / "parameters.json"`.
2. Executes `subprocess.run` with `cwd=str(output_dir)`.
3. Because the subprocess working directory is `output_dir`, when Manim imports the scene class and initializes `BaseDSAScene`, `Path("parameters.json")` successfully resolves to `output_dir / "parameters.json"`.

### 2.4 Pipeline Parameter Preprocessing & Injection

Location: `src/pipeline/nodes/animation_generator_node.py`

`AnimationGeneratorNode` normalizes visual cue parameters before passing them to `ManimRenderer`:
- Extracts `raw_params = cue.get("parameters")` (defaults to `{}`).
- Computes `duration = float(parameters.get("duration") or budgeted_duration)`.
- Fallback Injections:
  - If `description` is missing in `parameters`, injects `cue["description"]`.
  - For `code_walkthrough`, if `code` is missing, injects `script_data["solution"]["code_snippet"]`.
  - For `complexity_chart`, injects `time_complexity` and `space_complexity` from script data.
  - For `title_card`, injects `title` from script hook title or topic.

### 2.5 Data Schemas and LLM Prompt Contracts

Location: `src/models/script.py` & `src/core/llm/prompts/v1/script_generation.j2`

- **`VisualCue` Model**: Enforces `parameters: Dict[str, Any]` to be non-empty via `@field_validator("parameters")`.
- **Prompt Specifications (`script_generation.j2`)**: Dictates expected keys for each animation type:
  - `title_card`: `{"title": str, "subtitle": str}`
  - `linkedlist_operation`: `{"nodes": list, "action": str, "pointers": dict}`
  - `array_highlight`: `{"array": list, "action": str, "highlight_indices": list, "pointers": dict, "swap_indices": list, "window_size": int}`
  - `code_walkthrough`: `{"code": str, "language": str, "highlight_lines": list}`
  - `tree_traversal`: `{"nodes": list, "action": str, "highlight_nodes": list}`
  - `graph_animation`: `{"vertices": list, "edges": list, "action": str, "traversal_path": list}`
  - `hashmap_operation`: `{"entries": dict, "action": str, "highlight_key": str}`
  - `stack_queue_operation`: `{"elements": list, "action": str, "container_type": str, "new_element": val}`
  - `complexity_chart`: `{"time_complexity": str, "space_complexity": str}`

---

## 3. Comprehensive Scene Template Survey

### 3.1 `LinkedListScene`

- **File Path**: `/home/adarsh/Documents/Youtube-Channel/src/animation/scenes/linkedlist_scene.py`
- **Class Name**: `LinkedListScene(BaseDSAScene)`
- **Parameters Parsed**:
  - `nodes`: `List[Any]` (default: `[1, 2, 3, 4, 5]`)
  - `action`: `str` (default: `"traverse"`; options: `"traverse"`, `"fast_slow"`, `"reverse"`, `"split"`, `"merge"`, `"interleave"`, `"reorder"`)
  - `duration`: `float` (default: `5.0`)
  - `highlight_indices`: `List[int]` (default: `[]`)
  - `pointers`: `Dict[str, Any]` (default: `{}`)
- **Capabilities**:
  - `do_traverse()`: Animates single pointer (`ptr`) stepping through node list.
  - `do_fast_slow()`: Animates dual pointers (`slow` from bottom, `fast` from top) moving along list nodes.
  - `do_reverse()`: Transforms arrows in-place to reverse pointer arrows.
  - `do_split()`: Removes middle arrow and shifts second half downward.
  - `do_merge()`: Creates two sublists and interleaves nodes visually.
- **Gaps & R1 Deficiencies**:
  1. In `do_fast_slow()`, if custom `pointers` dict (`slow`, `fast`) is provided, it only performs a single jump to the target indices `(s_target, f_target)` in 1 step rather than executing a multi-step traversal sequence.
  2. In `do_reverse()`, arrows are transformed in-place without adjusting node positions or showing standard pointer variables (`prev`, `curr`, `next`).
  3. `do_split()` hardcodes splitting at `len(node_groups) // 2`, ignoring custom split indices.
  4. `do_merge()` hardcodes reversing the second half `nodes[mid:][::-1]` (tailored for list reorder/palindrome) and fails for generic two-list merges.
  5. No visual NULL/ground node symbol at list termination.
  6. Does not parse general pointer mapping dictionaries (e.g. `{"head": 0, "curr": 2, "prev": 1}`).

### 3.2 `ArrayScene`

- **File Path**: `/home/adarsh/Documents/Youtube-Channel/src/animation/scenes/array_scene.py`
- **Class Name**: `ArrayScene(BaseDSAScene)`
- **Parameters Parsed**:
  - `action`: `str` (default: `"traverse"`; options: `"traverse"`, `"two_pointers"`, `"swap"`, `"highlight"`, `"sliding_window"`)
  - `array`: `List[Any]` (default: `[1, 2, 3, 4, 5]`)
  - `duration`: `float` (default: `5.0`)
  - `swap_indices`: `List[int]` (default: `[0, len(arr)-1]`)
  - `highlight_indices`: `List[int]` (default: `[1, 3]`)
  - `window_size`: `int` (default: `3`)
- **Capabilities**:
  - Renders horizontal row of square boxes with centered value text.
  - Supports pointer traversal, dual pointer convergence, straight-line swap, element highlighting, and sliding window outline box.
- **Gaps & R1 Deficiencies**:
  1. Completely ignores the `pointers` dictionary parameter (e.g., `{"left": 0, "right": 3}` or custom pointer names). In `action_two_pointers()`, pointer targets are hardcoded to `len(arr)//2 - 1` and `len(arr)//2`.
  2. In `action_swap()`, element boxes move in a linear direct path, causing visual collision during animation instead of swapping via smooth arcs.
  3. `action_sliding_window()` assumes starting at index 0 and moving to the end, unable to take custom window bounds `[start, end]`.
  4. Lacks element index labels (0, 1, 2, 3...) below array boxes.
  5. Arrays with >8 elements overflow screen margins because `create_array_vg` lacks dynamic scale-to-fit boundary logic.

### 3.3 `TreeScene`

- **File Path**: `/home/adarsh/Documents/Youtube-Channel/src/animation/scenes/tree_scene.py`
- **Class Name**: `TreeScene(BaseDSAScene)`
- **Parameters Parsed**:
  - `nodes`: `List[Optional[Any]]` (default: `[1, 2, 3, None, 4, 5]`)
  - `action`: `str` (default: `"display"`; options: `"display"`, `"bfs"`, `"dfs"`, `"insert"`)
  - `duration`: `float` (default: `5.0`)
- **Capabilities**:
  - Builds binary tree graphic from level-order array representation (`2*i + 1`, `2*i + 2`).
  - Animates BFS and DFS node highlights, tree creation, and insert transformation.
- **Gaps & R1 Deficiencies**:
  1. Flawed `action_dfs()` node indexing logic (`valid_count = sum(1 for x in nodes_data[:idx] if x is not None)`), which breaks and highlights wrong nodes when `None` entries exist in earlier tree levels.
  2. `action_insert()` hardcodes inserting value `4` (`nodes_data + [4]`) instead of reading an `inserted_value` parameter from `self.params`.
  3. Test suite in `test_manim_animation.py` passes `{"root": 42}` which is completely ignored because `TreeScene` expects `nodes`.
  4. Rigid array-based layout (`dx * 0.5`) causes node overlap for deeper trees (>3 levels).
  5. No support for nested object tree structures (`{"val": 1, "left": ...}`) or explicit target node search paths.

### 3.4 `GraphScene`

- **File Path**: `/home/adarsh/Documents/Youtube-Channel/src/animation/scenes/graph_scene.py`
- **Class Name**: `GraphScene(BaseDSAScene)`
- **Parameters Parsed**:
  - `vertices`: `List[Any]` (default: `[1, 2, 3, 4]`)
  - `edges`: `List[List[Any]]` (default: `[[1, 2], [2, 3], [3, 4], [4, 1]]`)
  - `action`: `str` (default: `"display"`; options: `"display"`, `"bfs"`, `"dfs"`)
  - `traversal_path`: `List[Any]` (default: `[1, 2, 4, 3]` or `[1, 2, 3, 4]`)
  - `duration`: `float` (default: `5.0`)
- **Capabilities**:
  - Constructs graph via `manim.Graph(vertices, edges_tuples, layout="spring")`.
  - Sequentially highlights vertices in `traversal_path`.
- **Gaps & R1 Deficiencies**:
  1. `manim.Graph` renders undirected lines; directed graph edges (arrows) are unsupported.
  2. Traversal animations (`bfs`, `dfs`) only highlight vertices; traversed edges between vertices are not highlighted.
  3. Spring layout (`layout="spring"`) produces non-deterministic, inconsistent visual placements for structured graphs (e.g. DAGs or trees).
  4. Lacks support for edge weights, custom vertex coordinate layouts, or shortest path highlighting.

### 3.5 `HashmapScene`

- **File Path**: `/home/adarsh/Documents/Youtube-Channel/src/animation/scenes/hashmap_scene.py`
- **Class Name**: `HashmapScene(BaseDSAScene)`
- **Parameters Parsed**:
  - `entries`: `Dict[str, Any]` (default: `{"A": 1, "B": 2, "C": 3}`)
  - `action`: `str` (default: `"display"`; options: `"display"`, `"put"`, `"get"`, `"collision"`)
  - `duration`: `float` (default: `5.0`)
  - `highlight_key`: `str` (default: `"B"`)
- **Capabilities**:
  - Displays key-value entries as vertical table cells.
  - Highlights cells for lookup (`get`) and simulates key insertion (`put`).
- **Gaps & R1 Deficiencies**:
  1. `action_put()` hardcodes inserting `"C": 3` (`new_entries = {**entries, "C": 3}`), ignoring custom input `key` and `value` parameters.
  2. `action_collision()` places two arrows pointing at index 0 of a single table without showing bucket arrays, hash calculation formulas, or collision resolution mechanisms (chaining / open addressing).
  3. Lacks hash function visualization (`hash(key) % N -> index`).

### 3.6 `StackQueueScene`

- **File Path**: `/home/adarsh/Documents/Youtube-Channel/src/animation/scenes/stack_queue_scene.py`
- **Class Name**: `StackQueueScene(BaseDSAScene)`
- **Parameters Parsed**:
  - `action`: `str` (default: `"display"`; options: `"display"`, `"push"`, `"pop"`, `"enqueue"`, `"dequeue"`)
  - `elements`: `List[Any]` (default: `[1, 2, 3]`)
  - `container_type`: `str` (default: `"stack"`; options: `"stack"`, `"queue"`)
  - `new_element`: `Any` (default: `3`)
  - `duration`: `float` (default: `5.0`)
- **Capabilities**:
  - Arranges elements vertically (stack) or horizontally (queue).
  - Animates push/pop with vertical shifts and enqueue/dequeue with horizontal shifts.
- **Gaps & R1 Deficiencies**:
  1. `action_pop()` pops `container[0]`. However, `create_container` stacks elements from top to bottom, making `container[0]` the top visually, whereas standard stack conventions treat the last element as top.
  2. Lacks container boundary graphics (e.g. U-shaped bucket for stack, open-ended tube for queue).
  3. Lacks pointer arrows and text labels for `Top`, `Front`, and `Rear`.

### 3.7 `CodeScene`

- **File Path**: `/home/adarsh/Documents/Youtube-Channel/src/animation/scenes/code_scene.py`
- **Class Name**: `CodeScene(BaseDSAScene)`
- **Parameters Parsed**:
  - `code`: `str` (default: `"# DSA Implementation\ndef solve():\n    pass"`)
  - `language`: `str` (default: `"python"`)
  - `duration`: `float` (default: `5.0`)
  - `highlight_lines`: `List[int]` (default: `[]`)
  - `lines`: `str` (e.g. `"1-3"`)
  - `action`: `str` (default: `"default_action"`)
- **Capabilities**:
  - Renders syntax-highlighted code block using `manim.Code`.
  - Animates line highlight cursor (`SurroundingRectangle`) jumping through `highlight_lines`, with auto-scrolling for long code blocks (>15 lines).
- **Gaps & R1 Deficiencies**:
  1. Does not display side-by-side variable execution state or call-stack tracking.
  2. Multi-line range specifications (e.g. lines 3-5) are animated sequentially line-by-line rather than highlighting the block as a single cohesive unit when desired.

### 3.8 `ComplexityScene`

- **File Path**: `/home/adarsh/Documents/Youtube-Channel/src/animation/scenes/complexity_scene.py`
- **Class Name**: `ComplexityScene(BaseDSAScene)`
- **Parameters Parsed**:
  - `time_complexity`: `str` (default: `"O(N)"`)
  - `space_complexity`: `str` (default: `"O(1)"`)
  - `duration`: `float` (default: `5.0`)
- **Capabilities**:
  - Renders time and space complexity text badges inside a rectangular border.
- **Gaps & R1 Deficiencies**:
  1. Static visual card with minimal animation (`Write` + `Create(border)` + `wait`).
  2. Lacks Big-O growth curves, mathematical comparison plots, or rationale text breakdown.

### 3.9 `TitleScene`

- **File Path**: `/home/adarsh/Documents/Youtube-Channel/src/animation/scenes/title_scene.py`
- **Class Name**: `TitleScene(BaseDSAScene)`
- **Parameters Parsed**:
  - `title` or `text`: `str` (default: `"Data Structures & Algorithms"`)
  - `duration`: `float` (default: `5.0`)
- **Capabilities**:
  - Renders centered title string with `Write` animation.
- **Gaps & R1 Deficiencies**:
  1. Displays only single centered text block.
  2. Ignores `subtitle`, `difficulty`, or topic tags.

---

## 4. Base Classes, Helper Utilities, and Configuration Schemas

### 4.1 Base Class Mechanics (`BaseDSAScene`)

`BaseDSAScene` provides fallback stub handling when Manim is not installed (`MANIM_AVAILABLE = False`), enabling headless testing. However, parameter parsing is unvalidated and lacks schema enforcement:
- Ingestion relies purely on `.get(key, default)`.
- Type mismatches (e.g., passing a string for `duration` or single int for `highlight_indices`) cause unhandled exceptions during animation construction.

### 4.2 Styling and Color Palette (`ThemeColors`)

Location: `src/animation/theme.py`

The system utilizes a Catppuccin Mocha theme palette:
- `BACKGROUND`: `#1E1E2E`
- `TEXT_PRIMARY`: `#CDD6F4`
- `TEXT_SECONDARY`: `#A6ADC8`
- `PRIMARY_ACCENT`: `#89B4FA` (Blue)
- `SECONDARY_ACCENT`: `#F38BA8` (Pink/Red)
- `HIGHLIGHT`: `#A6E3A1` (Green)
- `WARNING`: `#F9E2AF` (Yellow)
- `CONTAINER_BG`: `#313244`
- `BORDER`: `#45475A`

### 4.3 Scene Routing Table (`ANIMATION_TYPE_MAP`)

Location: `src/pipeline/nodes/animation_generator_node.py`

Maps LLM visual cue `animation_type` strings to `(scene_file, class_name)`. Aliases exist for common variants (e.g. `array_highlight`, `array_traversal` -> `ArrayScene`). Fallback defaults to `ArrayScene`.

---

## 5. Synthesized Custom Parameter Capabilities & Gaps Matrix for R1

| Scene Type | Primary File & Class | Parameter JSON Schema | Currently Supported Keys | Action Types | Identified Gaps for Custom Inputs (R1) |
|---|---|---|---|---|---|
| **LinkedList** | `linkedlist_scene.py`<br>`LinkedListScene` | `nodes`: List<br>`action`: str<br>`pointers`: dict<br>`duration`: float | `nodes`, `action`, `duration`, `highlight_indices`, `pointers` | `traverse`, `fast_slow`, `reverse`, `split`, `merge`, `interleave`, `reorder` | • Dual pointers jump to target in 1 step instead of step sequence.<br>• Reversal flips arrows in-place without node movement or prev/curr/next labels.<br>• Merge/Split hardcode sublist partitioning.<br>• No NULL ground terminal. |
| **Array** | `array_scene.py`<br>`ArrayScene` | `array`: List<br>`action`: str<br>`swap_indices`: List[2]<br>`highlight_indices`: List<br>`window_size`: int<br>`pointers`: dict | `array`, `action`, `duration`, `swap_indices`, `highlight_indices`, `window_size` | `traverse`, `two_pointers`, `swap`, `highlight`, `sliding_window` | • `pointers` dict parameter is completely ignored.<br>• Linear element swap causes visual overlap.<br>• Lacks array index labels.<br>• Large arrays (>8 elements) overflow screen without scaling. |
| **Tree** | `tree_scene.py`<br>`TreeScene` | `nodes`: List<br>`action`: str<br>`duration`: float | `nodes`, `action`, `duration` | `display`, `bfs`, `dfs`, `insert` | • `action_dfs` index logic breaks on `None` nodes.<br>• `action_insert` hardcodes inserting `4`.<br>• Ignoring `root` key passed by test suite.<br>• Deep trees cause node overlap. |
| **Graph** | `graph_scene.py`<br>`GraphScene` | `vertices`: List<br>`edges`: List[List]<br>`action`: str<br>`traversal_path`: List | `vertices`, `edges`, `action`, `traversal_path`, `duration` | `display`, `bfs`, `dfs` | • Directed graph arrows unsupported.<br>• Traversal only highlights vertices, not traversed edges.<br>• Spring layout produces erratic, non-deterministic graph layout. |
| **Hashmap** | `hashmap_scene.py`<br>`HashmapScene` | `entries`: Dict<br>`action`: str<br>`highlight_key`: str | `entries`, `action`, `highlight_key`, `duration` | `display`, `put`, `get`, `collision` | • `action_put` hardcodes inserting key `"C": 3`.<br>• `action_collision` does not render buckets, hash formulas, or chaining.<br>• Lacks hash function step visualization. |
| **StackQueue** | `stack_queue_scene.py`<br>`StackQueueScene` | `elements`: List<br>`action`: str<br>`container_type`: str<br>`new_element`: Any | `elements`, `action`, `container_type`, `new_element`, `duration` | `display`, `push`, `pop`, `enqueue`, `dequeue` | • `action_pop` removes top item but container ordering lacks clear Top/Bottom labels.<br>• Missing container boundary graphics.<br>• Missing Top/Front/Rear pointer labels. |
| **Code** | `code_scene.py`<br>`CodeScene` | `code`: str<br>`language`: str<br>`highlight_lines`: List[int] | `code`, `language`, `duration`, `highlight_lines`, `lines`, `action` | Any / default | • Missing side-by-side variable execution state tracking panel.<br>• Range line highlights animated sequentially rather than as single block. |
| **Complexity** | `complexity_scene.py`<br>`ComplexityScene` | `time_complexity`: str<br>`space_complexity`: str | `time_complexity`, `space_complexity`, `duration` | Any / default | • Static text card.<br>• Lacks Big-O growth curves or comparative graphs. |
| **Title** | `title_scene.py`<br>`TitleScene` | `title`: str<br>`subtitle`: str | `title`, `text`, `duration` | Any / default | • Renders single title line only.<br>• Ignores `subtitle` parameter and topic badges. |

---

## 6. Concrete Structural & Architectural Recommendations for Objective R1

To achieve full compliance with Objective R1, the following structural enhancements should be implemented:

### 6.1 Unified Parameter Loading & Schema Validation Framework
- **Strict Parameter Alias Resolution**: Implement a robust parameter normalization layer in `BaseDSAScene` that maps synonymous parameter keys (e.g. `root` -> `nodes`, `text` -> `title`, `values` -> `array`).
- **Pydantic Parameter Schemas**: Define Pydantic models for scene parameters to ensure runtime type coercion (e.g., converting string integers, defaulting missing keys safely, validating bounds).

### 6.2 Step-by-Step Custom Animation Sequence Support
- Extend parameter schemas to accept explicit multi-step sequences (e.g., `steps: [{"pointers": {"left": 0, "right": 4}, "highlight": [0, 4]}, ...]`).
- Replace single-jump animations in `ArrayScene`, `LinkedListScene`, and `TreeScene` with iterative step loops that execute each step smoothly across the total budgeted `duration`.

### 6.3 Dynamic Layout & Auto-Scaling Engine
- Implement auto-scaling bounding boxes across all container builders (`create_array_vg`, `_create_linked_list`, `build_tree_vgroup`, `create_table`, `create_container`).
- If total width or height exceeds `config.frame_width - 1.5` or `config.frame_height - 2.0`, automatically apply `.scale_to_fit_width(...)` or `.scale_to_fit_height(...)` and center on screen.

### 6.4 Scene-Specific Enhancements for R1 Compliance
1. **`LinkedListScene`**: Support custom pointer dictionaries (`{"head": 0, "curr": 2, "prev": 1}`), add visual `NULL` ground box at termination, and implement multi-step pointer traversal.
2. **`ArrayScene`**: Parse `pointers` dict, render index numbers `0..N-1` below boxes, animate swaps using curved arc paths (`ArcBetweenPoints` or `path_arc`), and support custom window bounds `[start, end]`.
3. **`TreeScene`**: Support hierarchical nested tree objects `{"val": 1, "left": ...}`, fix DFS tree indexing with proper tree node recursion, and dynamically animate custom inserted values (`inserted_value`).
4. **`GraphScene`**: Support directed arrows (`Arrow` edges), highlight traversed edges along with vertices, and support pre-computed node layout coordinates or hierarchical DAG layouts.
5. **`HashmapScene`**: Accept custom `key` and `value` for `put`, render indexed bucket array with linked list chains for `collision`, and visualize `hash(key)` evaluation.
6. **`StackQueueScene`**: Add U-bucket / tube graphic walls, render `Top`, `Front`, and `Rear` pointers, and fix stack top/bottom orientation.
7. **`CodeScene`**: Support multi-line block highlighting and optional side-by-side variable watch panel.
8. **`ComplexityScene`**: Add Big-O growth curve graphs (`manim.Axes` with functions like $O(1)$, $O(\log N)$, $O(N)$, $O(N^2)$).
9. **`TitleScene`**: Support `subtitle` text and topic/difficulty badges.
