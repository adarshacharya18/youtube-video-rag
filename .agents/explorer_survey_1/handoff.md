# Explorer 1 Codebase Survey Handoff Report

## 1. Observation

### 1.1 Inspected File Locations & Line References
- **`src/animation/scenes/base_scene.py`**:
  - `BaseDSAScene(Scene)` class definition (lines 32-101).
  - `load_params_from_json()` candidate path search: `Path("parameters.json")` and `Path.cwd() / "parameters.json"` (lines 41-62).
  - `setup_scene_header()` adds title text to `UP + LEFT` corner (lines 87-96).
  - `construct()` executes `load_params_from_json()`, `setup_scene_header()`, and `construct_dsa_animation()` (lines 71-76).
- **`src/animation/renderer.py`**:
  - `ManimRenderer.render()` serializes `parameters` dict into `output_dir / "parameters.json"` (lines 52-54).
  - Subprocess execution `subprocess.run(cmd, ..., cwd=str(output_dir))` sets child process working directory (line 108).
- **`src/pipeline/nodes/animation_generator_node.py`**:
  - `ANIMATION_TYPE_MAP` maps visual cue animation types to scene files (lines 43-72).
  - Preprocesses cue parameters, injecting default fallback values for `code`, `time_complexity`, `space_complexity`, and `title` (lines 274-305).
- **`src/animation/scenes/linkedlist_scene.py`**:
  - `LinkedListScene(BaseDSAScene)` (lines 10-276). Reads `nodes`, `action`, `duration`, `highlight_indices`, `pointers`.
  - `do_fast_slow()` only jumps to custom pointer targets in 1 step (lines 126-130).
  - `do_reverse()` transforms arrows in-place without node movement or pointer labels (lines 182-202).
  - `do_split()` hardcodes mid-split index `len(node_groups)//2` (line 216).
  - `do_merge()` hardcodes reversing the second half `nodes[mid:][::-1]` (line 237).
- **`src/animation/scenes/array_scene.py`**:
  - `ArrayScene(BaseDSAScene)` (lines 7-126).
  - `action_two_pointers()` hardcodes target indices `len(arr)//2 - 1` and `len(arr)//2`, ignoring `pointers` dictionary parameter (lines 58-67).
  - `action_swap()` moves boxes in linear straight lines causing collision (lines 80-84).
  - Lacks index labels below array boxes; no auto-scaling for large arrays.
- **`src/animation/scenes/tree_scene.py`**:
  - `TreeScene(BaseDSAScene)` (lines 7-115).
  - Flawed DFS index counting (`valid_count = sum(1 for x in nodes_data[:idx] if x is not None)`) breaks when `None` nodes exist in preceding levels (lines 88-95).
  - `action_insert()` hardcodes inserting value `4` (line 110).
  - `tests/test_animation/test_manim_animation.py` line 111 passes `{"root": 42}` which is ignored because `TreeScene` expects `nodes`.
- **`src/animation/scenes/graph_scene.py`**:
  - `GraphScene(BaseDSAScene)` (lines 7-72).
  - Uses `manim.Graph(..., layout="spring")` which is non-deterministic (line 28). Undirected edges only; no edge traversal highlights.
- **`src/animation/scenes/hashmap_scene.py`**:
  - `HashmapScene(BaseDSAScene)` (lines 7-81).
  - `action_put()` hardcodes inserting `"C": 3` (line 46). Collision action doesn't show buckets or chaining.
- **`src/animation/scenes/stack_queue_scene.py`**:
  - `StackQueueScene(BaseDSAScene)` (lines 7-104).
  - Stack pop removes element `container[0]`, but visual ordering lacks Top/Bottom labels. Lacks container boundary graphics.
- **`src/animation/scenes/code_scene.py`**:
  - `CodeScene(BaseDSAScene)` (lines 10-98).
  - Uses `manim.Code` with line scrolling. Lacks variable state execution tracking panel.
- **`src/animation/scenes/complexity_scene.py`**:
  - `ComplexityScene(BaseDSAScene)` (lines 12-42).
  - Static text card; lacks growth curves or comparative axes.
- **`src/animation/scenes/title_scene.py`**:
  - `TitleScene(BaseDSAScene)` (lines 9-27).
  - Renders single centered text line; ignores `subtitle` parameter.

---

## 2. Logic Chain

1. **Observation**: `ManimRenderer.render()` writes `parameters` to `output_dir / "parameters.json"` and runs `manim render` with `cwd=output_dir`. `BaseDSAScene.__init__` invokes `load_params_from_json()` which reads `parameters.json` from `cwd`.
2. **Logic Step**: Parameter ingestion works seamlessly via disk file serialization, but scene subclasses unpack parameters using simple `.get(key, default)` calls without schema validation, alias normalization, or error handling.
3. **Observation**: In `ArrayScene`, `action_two_pointers` ignores `pointers` dict; `TreeScene` ignores `root`; `HashmapScene.action_put` hardcodes key `"C": 3`; `TreeScene.action_insert` hardcodes value `4`; `LinkedListScene.do_split` hardcodes mid-splitting.
4. **Logic Step**: Multiple scene templates contain hardcoded data assumptions and ignore passed custom parameters, directly violating Requirement R1 ("must cleanly parse and animate arbitrary custom input arguments").
5. **Observation**: Test suites and LLM prompt schemas pass different key names (e.g. `root` vs `nodes`, `left`/`right` pointers vs target indices).
6. **Logic Step**: Without unified parameter alias mapping and type validation, scene templates silently fall back to default arrays/values or crash during execution.

---

## 3. Caveats

- **Scope Limits**: Read-only codebase survey phase. No code modifications were made to `src/`.
- **Assumptions**: Assumed standard Manim CLI rendering mode via subprocess. Execution environment has Python 3.13 and Manim installed in virtual environment `.venv`.
- **Uninvestigated Areas**: Advanced Manim GPU acceleration options or custom C-extension render plugins.

---

## 4. Conclusion

The current Manim scene templates provide a functional rendering foundation but fail Requirement R1 due to hardcoded data operations, ignored parameter keys, missing layout auto-scaling, fragile indexing, and lack of parameter validation. Refactoring is required to establish a unified parameter normalization layer, robust schema validation, and flexible step-by-step sequence animation support across all 9 scene templates.

---

## 5. Verification Method

### 5.1 Inspection of Analysis Files
- Inspect `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_survey_1/analysis.md` for full scene-by-scene audit matrix and architectural recommendations.

### 5.2 Command Verification
- Run existing animation tests to verify current baseline rendering:
  ```bash
  pytest tests/test_animation/test_manim_animation.py
  pytest tests/pipeline/test_animation_node.py
  ```

### 5.3 Invalidation Conditions
- If `parameters.json` key names change without update to `ANIMATION_TYPE_MAP` or `BaseDSAScene`, renders will fall back to hardcoded defaults or raise KeyError/AttributeError.
