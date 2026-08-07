# Parameter Schema Management & Alias Mapping Specification for BaseDSAScene

## Executive Summary
This report provides a detailed architectural specification for parameter schema management, dynamic `parameters.json` parsing, and alias mapping resolution for `BaseDSAScene` (`src/animation/scenes/base_scene.py`) in Milestone M0. 

Currently, scenes directly query `self.params.get(...)` with inconsistent key names (e.g., `array` vs `arr` vs `nodes` vs `elements`), non-standardized fallback defaults, and no type coercion or alias resolution. This specification designs a centralized, resilient parameter ingestion pipeline supporting:
1. **Multi-source parameter loading** (dict, file path, candidate fallback paths, environment variable).
2. **Canonical key normalization and alias resolution** (mapping `array` -> `input_array`, `speed` -> `step_duration`, `time_comp` -> `time_complexity`, etc.).
3. **Type coercion and safety validation** (coercing string ranges, numeric strings, scalar values).
4. **Clean default fallback mechanisms** for missing optional keys.
5. **Pydantic schema validation integration** via `parse_parameters()`.

---

## 1. Repository Audit of Existing Parameter Handling

A comprehensive audit of the workspace reveals the following current state of parameter handling:

### 1.1 Ingestion Points
- **`src/animation/renderer.py`**: `ManimRenderer.render()` serializes a dictionary of visual parameters into `parameters.json` inside an isolated output directory (`output_dir`) before invoking Manim CLI subprocess calls.
- **`src/animation/scenes/base_scene.py`**: `BaseDSAScene.load_params_from_json()` searches for `parameters.json` in candidate paths (`Path("parameters.json")` and `Path.cwd() / "parameters.json"`).
- **`src/pipeline/nodes/animation_generator_node.py`**: Constructs scene parameters from script visual cues and writes `parameters.json` to the temporary render directory.
- **Tests (`tests/pipeline/test_animation_node.py`)**: Tests verify that `BaseDSAScene` loads `parameters.json` from the current working directory.

### 1.2 Identified Limitations in Current `base_scene.py`
1. **No Alias Map**: Subclasses currently look up hardcoded keys (e.g. `self.params.get("array")`). If `parameters.json` contains `"input_array"` or `"arr"`, the scene fails to recognize it and silently falls back to hardcoded defaults.
2. **No Type Coercion**: Values like `"duration": "5.0"` or `"highlight_lines": "1-3"` are unparsed strings, requiring each scene method to duplicate `float(self.params.get("duration", 5.0))` or custom range split logic.
3. **Fragile Exception Rollback**: Parsing errors in JSON log warnings but do not provide a structured schema default state, leading to potential `KeyError` or `TypeError` during rendering.
4. **Lack of Uniform Access Method**: Scenes access `self.params` directly via `dict.get()`, bypassing validation logic.

---

## 2. Comprehensive Scene Parameter & Alias Mapping Inventory

An audit of all 9 scene templates (`array_scene.py`, `linkedlist_scene.py`, `stack_queue_scene.py`, `hashmap_scene.py`, `tree_scene.py`, `graph_scene.py`, `code_scene.py`, `complexity_scene.py`, `title_scene.py`) identified the following canonical parameter names, legacy keys, and requested aliases:

| Scene Template | Canonical Key | Registered Aliases | Type | Default Value | Description |
|---|---|---|---|---|---|
| **Common (BaseDSAScene)** | `title` | `text`, `header`, `name`, `problem_title` | `str` | `""` | Header title string displayed at corner/top |
| | `step_duration` | `duration`, `speed`, `time`, `total_duration`, `run_time` | `float` | `5.0` | Target scene or step animation duration in seconds |
| | `action` | `operation`, `type`, `anim_type`, `mode` | `str` | `"display"` | Animation sub-routine selector |
| **ArrayScene** | `input_array` | `array`, `arr`, `elements`, `data`, `values`, `items`, `list` | `list` | `[1, 2, 3, 4, 5]` | Sequence of elements to display |
| | `swap_indices` | `swap`, `swaps`, `swap_pair`, `indices_to_swap` | `list[int]` | `[0, -1]` | Pair of index positions to swap |
| | `highlight_indices` | `highlights`, `highlight`, `active_indices`, `targets` | `list[int]` | `[]` | Index positions to highlight |
| | `window_size` | `k`, `window`, `size`, `sliding_window_size` | `int` | `3` | Window frame size for sliding window |
| **LinkedListScene** | `nodes` | `node_values`, `input_list`, `values`, `elements`, `data` | `list` | `[1, 2, 3, 4, 5]` | Sequence of node values |
| | `pointers` | `pointer_map`, `ptrs`, `cursor_positions` | `dict` | `{}` | Dict of pointer labels to indices (e.g. `{"slow": 1, "fast": 3}`) |
| | `highlight_indices` | `highlights`, `highlight`, `active_nodes` | `list[int]` | `[]` | Node indices to highlight |
| **StackQueueScene** | `elements` | `items`, `input_elements`, `values`, `data`, `stack_elements`, `queue_elements` | `list` | `[1, 2, 3]` | Sequence of stack/queue items |
| | `container_type` | `type`, `structure_type`, `kind`, `mode` | `str` | `"stack"` | Container geometry ("stack" or "queue") |
| | `new_element` | `push_value`, `enqueue_value`, `item`, `val`, `element` | `Any` | `3` | Value to push or enqueue |
| **HashmapScene** | `entries` | `hashmap`, `map`, `data`, `key_value_pairs`, `items`, `dict_data` | `dict` | `{"A": 1, "B": 2, "C": 3}` | Key-value dictionary entries |
| | `highlight_key` | `key`, `target_key`, `active_key`, `search_key` | `str` | `"B"` | Key to highlight during lookup/get |
| **TreeScene** | `nodes` | `tree_nodes`, `values`, `tree_array`, `level_order`, `data` | `list` | `[1, 2, 3, None, 4, 5]` | 1D level-order array representation of tree (None for missing) |
| | `edges` | `links`, `connections`, `parent_child_links` | `list` | `[]` | Custom explicit edge pairings if auto-indexing is overridden |
| **GraphScene** | `vertices` | `nodes`, `node_list`, `vertex_list` | `list` | `[1, 2, 3, 4]` | List of graph vertex identifiers |
| | `edges` | `links`, `edge_list`, `connections` | `list[list]` | `[[1, 2], [2, 3], [3, 4], [4, 1]]` | Pairwise edge connections |
| | `traversal_path` | `path`, `visit_order`, `order`, `traversal` | `list` | `[1, 2, 3, 4]` | Sequence of visited vertices for BFS/DFS |
| **CodeScene** | `code` | `code_str`, `code_snippet`, `source_code`, `script`, `text` | `str` | `"# DSA Implementation\ndef solve():\n    pass"` | Raw source code string |
| | `language` | `lang`, `syntax` | `str` | `"python"` | Programming language syntax highlighter mode |
| | `highlight_lines` | `active_lines`, `lines_to_highlight`, `target_lines`, `lines` | `list[int]` | `[]` | Line numbers (1-indexed) to sequentially highlight |
| **ComplexityScene** | `time_complexity` | `time_comp`, `time`, `big_o_time` | `str` | `"O(N)"` | Time complexity string |
| | `space_complexity` | `space_comp`, `space`, `big_o_space` | `str` | `"O(1)"` | Space complexity string |
| **TitleScene** | `title` | `text`, `header`, `name`, `main_title` | `str` | `"Data Structures & Algorithms"` | Title card main text |
| | `subtitle` | `sub_text`, `category`, `description` | `str` | `""` | Subtitle text |

---

## 3. Parameter Loading & Search Candidate Architecture

`BaseDSAScene` must implement a multi-tiered candidate discovery order for `parameters.json`.

```
┌────────────────────────────────────────────────────────┐
│  Caller passes param_path_or_dict (str, Path, dict)    │
└──────────────────────────┬─────────────────────────────┘
                           │ If Dict -> Use directly
                           ▼
┌────────────────────────────────────────────────────────┐
│  Candidate Search Path Order:                          │
│  1. Explicit json_path / param_path argument           │
│  2. Path("parameters.json") in execution directory     │
│  3. Path.cwd() / "parameters.json"                     │
│  4. os.getenv("MANIM_PARAMS_PATH")                     │
└──────────────────────────┬─────────────────────────────┘
                           │ If file found -> Read & Parse JSON
                           ▼
┌────────────────────────────────────────────────────────┐
│  Parameter Alias Resolver & Normalization Engine       │
└──────────────────────────┬─────────────────────────────┘
                           │ Normalize key names -> Populate self.params
                           ▼
┌────────────────────────────────────────────────────────┐
│  Type Coercion & Schema Default Fallback Layer         │
└────────────────────────────────────────────────────────┘
```

### Key Ingestion Protocol Rules:
1. **Direct Dictionary Passing**: `load_parameters(dict)` populates `self.params` immediately without filesystem I/O.
2. **File Path Candidate Verification**: Candidates are checked sequentially; the first existing readable file is loaded.
3. **Corrupt File Resilience**: If JSON decoding fails, log an `ERROR` message with the file path and error details, then populate `self.params` with empty dict `{}` and rely on default fallbacks.
4. **Idempotent Ingestion**: `setup()` and `construct()` call `load_parameters()` only if `self.params` is empty.

---

## 4. Alias Resolution Specification

### 4.1 Alias Map Definition
`BaseDSAScene` will maintain a central `GLOBAL_ALIAS_MAP` mapping any alias key to its canonical key name:

```python
GLOBAL_ALIAS_MAP: Dict[str, str] = {
    # Base/Common
    "duration": "step_duration",
    "speed": "step_duration",
    "time": "step_duration",
    "total_duration": "step_duration",
    "run_time": "step_duration",
    "operation": "action",
    "type": "action",
    "anim_type": "action",
    "mode": "action",
    "text": "title",
    "header": "title",
    "name": "title",
    "problem_title": "title",

    # Array
    "array": "input_array",
    "arr": "input_array",
    "data": "input_array",
    "values": "input_array",
    "items": "input_array",
    "list": "input_array",
    "swap": "swap_indices",
    "swaps": "swap_indices",
    "swap_pair": "swap_indices",
    "indices_to_swap": "swap_indices",
    "highlights": "highlight_indices",
    "highlight": "highlight_indices",
    "active_indices": "highlight_indices",
    "targets": "highlight_indices",
    "k": "window_size",
    "window": "window_size",
    "size": "window_size",
    "sliding_window_size": "window_size",

    # LinkedList
    "node_values": "nodes",
    "input_list": "nodes",
    "active_nodes": "highlight_indices",
    "pointer_map": "pointers",
    "ptrs": "pointers",
    "cursor_positions": "pointers",

    # StackQueue
    "stack_elements": "elements",
    "queue_elements": "elements",
    "input_elements": "elements",
    "structure_type": "container_type",
    "kind": "container_type",
    "push_value": "new_element",
    "enqueue_value": "new_element",
    "item": "new_element",
    "val": "new_element",
    "element": "new_element",

    # Hashmap
    "hashmap": "entries",
    "map": "entries",
    "key_value_pairs": "entries",
    "dict_data": "entries",
    "key": "highlight_key",
    "target_key": "highlight_key",
    "active_key": "highlight_key",
    "search_key": "highlight_key",

    # Tree
    "tree_nodes": "nodes",
    "tree_array": "nodes",
    "level_order": "nodes",
    "parent_child_links": "edges",

    # Graph
    "node_list": "vertices",
    "nodes_list": "vertices",
    "vertex_list": "vertices",
    "links": "edges",
    "edge_list": "edges",
    "connections": "edges",
    "path": "traversal_path",
    "visit_order": "traversal_path",
    "order": "traversal_path",
    "traversal": "traversal_path",

    # Code
    "code_str": "code",
    "code_snippet": "code",
    "source_code": "code",
    "script": "code",
    "lang": "language",
    "syntax": "language",
    "active_lines": "highlight_lines",
    "lines_to_highlight": "highlight_lines",
    "target_lines": "highlight_lines",
    "lines": "highlight_lines",

    # Complexity
    "time_comp": "time_complexity",
    "big_o_time": "time_complexity",
    "space_comp": "space_complexity",
    "big_o_space": "space_complexity",

    # Title
    "main_title": "title",
    "sub_text": "subtitle",
    "category": "subtitle",
}
```

### 4.2 Resolution Logic & Order
When parameters are loaded:
1. Every input key is checked against `GLOBAL_ALIAS_MAP`.
2. If key is an alias (e.g. `"arr"`), its canonical key (`"input_array"`) is populated with the value.
3. Both canonical key and legacy key are preserved in `self.params` to prevent breaking existing scene code that accesses `self.params.get("array")` directly.
4. When `get_parameter(key, default)` is invoked, it checks:
   - Canonical key name in `self.params`.
   - Primary requested `key` in `self.params`.
   - Any registered alias for `key` in `self.params`.
   - Fallback `default` value.

---

## 5. Type Coercion, Safety Validation & Missing Key Fallback

To prevent runtime errors in Manim animations (such as passing a string `"5"` to `run_time` or an invalid string `"1-4"` to `highlight_lines`), `get_parameter()` performs type coercion:

### 5.1 Type Coercion Matrix
- **Float Coercion**: `expected_type=float` converts string numbers (`"5.0"`, `"5"`) or integers (`5`) to `float`. On conversion failure, logs a warning and returns the fallback default float.
- **Int Coercion**: `expected_type=int` converts float or string numbers to `int`.
- **List Coercion**:
  - `expected_type=list`: Converts single scalar items (`5` -> `[5]`).
  - Converts range strings (`"1-4"` -> `[1, 2, 3, 4]`).
  - Converts comma-separated strings (`"1,2,3"` -> `[1, 2, 3]`).
- **Dict Coercion**: Ensures `entries` or `pointers` returns a valid `dict`, returning empty dict `{}` if `None` or invalid.

### 5.2 Missing Optional Key Handling Protocol
If an optional parameter key is absent or `None`:
1. Do NOT raise an exception.
2. Return the explicit `default` parameter provided to `get_parameter(key, default=...)`.
3. If no default is provided to `get_parameter()`, look up the canonical default from scene schema.
4. Ensure default fallback values match expected types (e.g. empty list `[]` for indices, empty dict `{}` for maps, standard duration `5.0` for step duration).

---

## 6. Proposed Implementation Specification for `base_scene.py`

Below is the concrete design specification to be implemented in `src/animation/scenes/base_scene.py`:

```python
"""Base DSA Scene Class supporting Manim rendering and parameter schema management."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Graceful Manim Import Fallback
MANIM_AVAILABLE = False
try:
    import manim  # type: ignore # noqa: F401
    from manim import LEFT, UP, Scene, Text  # type: ignore

    MANIM_AVAILABLE = True
except ImportError:

    class Scene:  # type: ignore
        """Stub Scene base class when Manim is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def construct(self) -> None:
            pass


from src.animation.theme import DEFAULT_THEME, ThemeColors

GLOBAL_ALIAS_MAP: Dict[str, str] = {
    # Common
    "duration": "step_duration",
    "speed": "step_duration",
    "time": "step_duration",
    "total_duration": "step_duration",
    "run_time": "step_duration",
    "operation": "action",
    "type": "action",
    "anim_type": "action",
    "mode": "action",
    "text": "title",
    "header": "title",
    "name": "title",
    # Array
    "array": "input_array",
    "arr": "input_array",
    "data": "input_array",
    "values": "input_array",
    "items": "input_array",
    "list": "input_array",
    "swap": "swap_indices",
    "swaps": "swap_indices",
    "highlights": "highlight_indices",
    "highlight": "highlight_indices",
    "k": "window_size",
    "window": "window_size",
    # LinkedList
    "node_values": "nodes",
    "input_list": "nodes",
    "active_nodes": "highlight_indices",
    "pointer_map": "pointers",
    "ptrs": "pointers",
    # StackQueue
    "stack_elements": "elements",
    "queue_elements": "elements",
    "input_elements": "elements",
    "push_value": "new_element",
    "enqueue_value": "new_element",
    "item": "new_element",
    "val": "new_element",
    "element": "new_element",
    "structure_type": "container_type",
    "kind": "container_type",
    # Hashmap
    "hashmap": "entries",
    "map": "entries",
    "dict_data": "entries",
    "key": "highlight_key",
    "target_key": "highlight_key",
    "search_key": "highlight_key",
    # Tree
    "tree_nodes": "nodes",
    "tree_array": "nodes",
    "level_order": "nodes",
    "links": "edges",
    # Graph
    "node_list": "vertices",
    "nodes_list": "vertices",
    "vertex_list": "vertices",
    "edge_list": "edges",
    "connections": "edges",
    "path": "traversal_path",
    "visit_order": "traversal_path",
    # Code
    "code_str": "code",
    "code_snippet": "code",
    "source_code": "code",
    "script": "code",
    "lang": "language",
    "syntax": "language",
    "lines": "highlight_lines",
    "active_lines": "highlight_lines",
    "lines_to_highlight": "highlight_lines",
    # Complexity
    "time_comp": "time_complexity",
    "big_o_time": "time_complexity",
    "space_comp": "space_complexity",
    "big_o_space": "space_complexity",
}


class BaseDSAScene(Scene):
    """Abstract Base Class for all DSA Visual Scene Templates."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.theme: ThemeColors = DEFAULT_THEME
        self.params: Dict[str, Any] = {}
        self.load_parameters()

    def load_parameters(
        self,
        param_path_or_dict: Optional[Union[str, Path, Dict[str, Any]]] = None,
        schema: Optional[Type[BaseModel]] = None,
        aliases: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Loads, normalizes, and validates parameters from dict or JSON path.
        """
        raw_params: Dict[str, Any] = {}

        if isinstance(param_path_or_dict, dict):
            raw_params = dict(param_path_or_dict)
        else:
            candidates: List[Path] = []
            if param_path_or_dict:
                candidates.append(Path(param_path_or_dict))
            candidates.extend(
                [
                    Path("parameters.json"),
                    Path.cwd() / "parameters.json",
                ]
            )
            env_path = os.getenv("MANIM_PARAMS_PATH")
            if env_path:
                candidates.append(Path(env_path))

            for path in candidates:
                if path.exists() and path.is_file():
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            raw_params = json.load(f)
                        logger.debug("Successfully loaded scene parameters from %s", path)
                        break
                    except Exception as e:
                        logger.warning("Failed to parse scene parameters from %s: %s", path, e)

        alias_map = dict(GLOBAL_ALIAS_MAP)
        if aliases:
            alias_map.update(aliases)

        normalized: Dict[str, Any] = {}
        # Copy original raw keys first
        for k, v in raw_params.items():
            normalized[k] = v

        # Populate canonical keys from aliases
        for k, v in raw_params.items():
            canonical_key = alias_map.get(k)
            if canonical_key and (canonical_key not in normalized or normalized[canonical_key] is None):
                normalized[canonical_key] = v

        self.params = normalized

        if schema is not None:
            self.parse_parameters(schema)

        return self.params

    def load_params_from_json(self, json_path: Optional[str] = None) -> Dict[str, Any]:
        """Backward-compatible wrapper for load_parameters."""
        return self.load_parameters(param_path_or_dict=json_path)

    def get_parameter(
        self,
        key: str,
        default: Any = None,
        expected_type: Optional[Type] = None,
    ) -> Any:
        """
        Retrieves parameter value with alias lookup and type coercion.
        """
        canonical_key = GLOBAL_ALIAS_MAP.get(key, key)
        val = None

        if key in self.params and self.params[key] is not None:
            val = self.params[key]
        elif canonical_key in self.params and self.params[canonical_key] is not None:
            val = self.params[canonical_key]
        else:
            val = default

        if val is None:
            return default

        if expected_type is float:
            try:
                return float(val)
            except (ValueError, TypeError):
                logger.warning("Could not coerce parameter '%s' value %r to float.", key, val)
                return default if default is not None else 0.0
        elif expected_type is int:
            try:
                return int(val)
            except (ValueError, TypeError):
                logger.warning("Could not coerce parameter '%s' value %r to int.", key, val)
                return default if default is not None else 0
        elif expected_type is list:
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                if "-" in val:
                    try:
                        start, end = map(int, val.split("-"))
                        return list(range(start, end + 1))
                    except ValueError:
                        pass
                if "," in val:
                    return [s.strip() for s in val.split(",")]
                try:
                    return [int(val)]
                except ValueError:
                    return [val]
            return [val]

        return val

    def parse_parameters(self, schema: Type[BaseModel]) -> BaseModel:
        """Pydantic model validation helper."""
        return schema(**self.params)

    def setup(self) -> None:
        """Manim setup lifecycle hook."""
        if hasattr(super(), "setup"):
            super().setup()
        if not self.params:
            self.load_parameters()

    def construct(self) -> None:
        """Standard Manim scene construct method."""
        if not self.params:
            self.load_parameters()
        self.setup_scene_header()
        self.construct_dsa_animation()

    def render_with_params(self, params: Dict[str, Any]) -> None:
        """Entry point for dynamic parameters."""
        self.load_parameters(param_path_or_dict=params)
        if MANIM_AVAILABLE:
            self.setup_scene_header()
            self.construct_dsa_animation()
        else:
            logger.info("Manim not installed: Skipping graphical construction.")

    def setup_scene_header(self) -> None:
        """Renders standard scene header title if present."""
        if not MANIM_AVAILABLE:
            return
        title_text = self.get_parameter("title", default="")
        if title_text:
            header = Text(title_text, font_size=28, color=self.theme.PRIMARY_ACCENT)
            header.to_corner(UP + LEFT, buff=0.5)
            self.add(header)

    def construct_dsa_animation(self) -> None:
        """Override in concrete scene subclasses."""
        pass
```

---

## 7. Verification & Test Strategy

To verify the implementation of this specification in M0, the following test scenarios must be executed in `tests/test_animation/test_parameter_schema.py`:

1. **Direct Dict Ingestion Test**: Pass raw dict to `load_parameters()`; assert `self.params` contains dict content.
2. **File Ingestion Test**: Write `parameters.json` to temporary directory; call `load_parameters()`; assert correct JSON parsing.
3. **Alias Resolution Test**:
   - Pass `{"arr": [10, 20], "speed": 3.5}` to `load_parameters()`.
   - Assert `get_parameter("input_array")` returns `[10, 20]`.
   - Assert `get_parameter("step_duration")` returns `3.5`.
   - Assert legacy access `get_parameter("array")` returns `[10, 20]`.
4. **Type Coercion Test**:
   - Pass `{"duration": "4.5", "highlight_lines": "2-5"}`.
   - Assert `get_parameter("duration", expected_type=float)` returns `4.5` (float).
   - Assert `get_parameter("highlight_lines", expected_type=list)` returns `[2, 3, 4, 5]`.
5. **Missing Key Fallback Test**:
   - Call `get_parameter("non_existent_key", default="fallback_val")`.
   - Assert returns `"fallback_val"` without raising exception.
6. **Corrupt File Rollback Test**:
   - Write corrupt JSON string (`"{invalid_json"`) to `parameters.json`.
   - Call `load_parameters()`; assert warning is logged and defaults are returned.

---

## Conclusion
This specification establishes a unified, alias-aware, fault-tolerant parameter ingestion pipeline for `BaseDSAScene`. Implementation of this design in M0 will allow all downstream scenes in M1-M3 to seamlessly parse custom problem arguments from `parameters.json` without code duplication or runtime failure.
