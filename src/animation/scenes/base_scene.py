"""Base DSA Scene Class supporting Manim rendering, schema validation, and ambient continuous waits."""

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union

logger = logging.getLogger(__name__)

# Graceful Manim Import Fallback
MANIM_AVAILABLE = False
there_and_back = None
try:
    import manim  # type: ignore # noqa: F401
    from manim import LEFT, UP, Scene, Text, there_and_back  # type: ignore

    MANIM_AVAILABLE = True
except ImportError:

    class Scene:  # type: ignore
        """Stub Scene base class when Manim is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def construct(self) -> None:
            pass

        def wait(self, duration: float = 1.0) -> None:
            pass

        def add(self, *mobjects: Any) -> None:
            pass

        def play(self, *args: Any, **kwargs: Any) -> None:
            pass


# Optional Pydantic Import
PYDANTIC_AVAILABLE = False
try:
    from pydantic import BaseModel
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = Any  # type: ignore

from src.animation.theme import DEFAULT_THEME, ThemeColors

# Canonical Alias Mapping for parameter key normalization
GLOBAL_ALIAS_MAP: Dict[str, str] = {
    # title aliases
    "header": "title",
    "topic": "title",
    "title_text": "title",
    "sub_title": "subtitle",
    # array aliases
    "data": "array",
    "arr": "array",
    "input_array": "array",
    "values": "array",
    "input": "array",
    "list": "array",
    # nodes aliases
    "nodes_data": "nodes",
    "node_list": "nodes",
    "vals": "nodes",
    "elements_list": "nodes",
    "tree": "nodes",
    "root": "nodes",
    "binary_tree": "nodes",
    "insert_value": "new_node",
    "val_to_insert": "new_node",
    "delete_node": "target_node",
    "target_val": "target_node",
    # code aliases
    "code_snippet": "code",
    "snippet": "code",
    "algorithm_code": "code",
    "source_code": "code",
    "lines": "code",
    # vertices aliases
    "nodes_graph": "vertices",
    "graph_nodes": "vertices",
    # edges aliases
    "edge_list": "edges",
    "graph_edges": "edges",
    "connections": "edges",
    # graph weights & properties aliases
    "graph_weights": "weights",
    "edge_weights": "weights",
    "is_directed": "directed",
    "directed_graph": "directed",
    "path": "traversal_path",
    # step_duration aliases
    "step_time": "step_duration",
    "duration_per_step": "step_duration",
    # time_complexity aliases
    "time": "time_complexity",
    "big_o_time": "time_complexity",
    "time_comp": "time_complexity",
    # space_complexity aliases
    "space": "space_complexity",
    "big_o_space": "space_complexity",
    "space_comp": "space_complexity",
    # highlight_lines aliases
    "active_lines": "highlight_lines",
    "lines_to_highlight": "highlight_lines",
    "highlighted_lines": "highlight_lines",
    # elements aliases
    "items": "elements",
    "stack_items": "elements",
    "queue_items": "elements",
    # entries aliases
    "key_values": "entries",
    "map": "entries",
    "kv_pairs": "entries",
    "hash_entries": "entries",
}

if PYDANTIC_AVAILABLE:
    class TreeSceneSchema(BaseModel):
        nodes: Optional[Union[List[Any], Dict[str, Any], int, str]] = None
        action: str = "display"
        duration: float = 5.0
        new_node: Optional[Any] = None
        target_node: Optional[Any] = None

    class GraphSceneSchema(BaseModel):
        vertices: Optional[List[Any]] = None
        edges: Optional[List[Any]] = None
        weights: Optional[Union[Dict[str, Any], List[Any]]] = None
        directed: bool = False
        layout: str = "kamada_kawai"
        action: str = "display"
        duration: float = 5.0
        traversal_path: Optional[List[Any]] = None
        shortest_path: Optional[List[Any]] = None
else:
    TreeSceneSchema = Any
    GraphSceneSchema = Any



class BaseDSAScene(Scene):
    """Abstract Base Class for all DSA Visual Scene Templates."""

    ALIAS_MAP: Dict[str, str] = GLOBAL_ALIAS_MAP

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.theme: ThemeColors = DEFAULT_THEME
        self.params: Dict[str, Any] = {}
        self.header_mobject: Optional[Any] = None
        self.load_parameters()

    def _resolve_aliases(
        self, raw_params: Dict[str, Any], custom_aliases: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Resolves alias key names into canonical parameter keys."""
        if not isinstance(raw_params, dict):
            raw_params = {}
        alias_map = dict(self.ALIAS_MAP)
        if custom_aliases and isinstance(custom_aliases, dict):
            alias_map.update(custom_aliases)

        resolved = dict(raw_params)
        for alias, canonical in alias_map.items():
            if alias in raw_params and canonical not in resolved:
                resolved[canonical] = raw_params[alias]
        return resolved

    def _coerce_type(self, val: Any, expected_type: Type, default: Any) -> Any:
        """Safely coerces val to expected_type, returning default on failure."""
        if isinstance(val, expected_type):
            return val
        try:
            if expected_type is int:
                return int(val)
            elif expected_type is float:
                return float(val)
            elif expected_type is str:
                return str(val)
            elif expected_type is list:
                if isinstance(val, (list, tuple, set)):
                    return list(val)
                return default
            elif expected_type is dict:
                if isinstance(val, dict):
                    return val
                return default
            elif expected_type is bool:
                if isinstance(val, str):
                    if val.lower() in ("true", "1", "yes"):
                        return True
                    elif val.lower() in ("false", "0", "no"):
                        return False
                return bool(val)
            else:
                return expected_type(val)
        except (ValueError, TypeError, OverflowError, ArithmeticError, Exception) as e:
            logger.warning("Failed to coerce parameter value %r to %s: %s", val, expected_type, e)
            return default

    def _validate_schema(self, data: Dict[str, Any], schema: Any) -> Dict[str, Any]:
        """Validates parameter dictionary against Pydantic schema or fallback validator."""
        if hasattr(schema, "model_validate"):
            try:
                validated_model = schema.model_validate(data)
                return validated_model.model_dump()
            except Exception as val_err:
                logger.warning("Pydantic schema model_validate warning: %s. Using raw parameters.", val_err)
                return data
        elif hasattr(schema, "parse_obj"):
            try:
                validated_model = schema.parse_obj(data)
                return validated_model.dict()
            except Exception as val_err:
                logger.warning("Pydantic schema parse_obj warning: %s. Using raw parameters.", val_err)
                return data
        elif callable(schema):
            try:
                res = schema(data)
                if isinstance(res, dict):
                    return res
            except Exception as val_err:
                logger.warning("Custom schema callable validation warning: %s", val_err)
                return data
        return data

    def load_parameters(
        self,
        param_path_or_dict: Optional[Union[str, Path, Dict[str, Any]]] = None,
        schema: Optional[Any] = None,
        custom_aliases: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Loads, resolves alias names, validates schema, and stores scene parameters."""
        raw_data: Dict[str, Any] = {}

        if isinstance(param_path_or_dict, dict):
            raw_data = dict(param_path_or_dict)
        elif isinstance(param_path_or_dict, (str, Path)):
            path = Path(param_path_or_dict)
            if path.exists() and path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        raw_data = data
                    else:
                        logger.warning("JSON root in %s is not a dictionary. Falling back to empty dict.", path)
                        raw_data = {}
                    logger.debug("Successfully loaded scene parameters from %s", path)
                except Exception as e:
                    logger.warning("Failed to parse scene parameters from %s: %s", path, e)
                    raw_data = {}
        else:
            candidates = [
                Path("parameters.json"),
                Path.cwd() / "parameters.json",
            ]
            for path in candidates:
                if path.exists() and path.is_file():
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, dict):
                            raw_data = data
                        else:
                            raw_data = {}
                        logger.debug("Successfully loaded scene parameters from %s", path)
                        break
                    except Exception as e:
                        logger.warning("Failed to parse scene parameters from %s: %s", path, e)
                        raw_data = {}

        if not isinstance(raw_data, dict):
            raw_data = {}

        # Alias resolution
        normalized = self._resolve_aliases(raw_data, custom_aliases)

        # Schema validation & type coercion
        if schema is not None:
            normalized = self._validate_schema(normalized, schema)

        self.params = normalized
        return self.params

    def load_params_from_json(self, json_path: Optional[str] = None) -> Dict[str, Any]:
        """Loads visual cue parameters from a JSON file (backwards compatible wrapper)."""
        return self.load_parameters(param_path_or_dict=json_path)

    def get_parameter(
        self, key: str, default: Any = None, expected_type: Optional[Type] = None
    ) -> Any:
        """Safe parameter access with alias resolution and optional type coercion.

        Args:
            key: Parameter key or alias to retrieve.
            default: Fallback value if parameter is not found.
            expected_type: Optional Python type for safe coercion (e.g. int, float, str, list, dict).
        """
        val = None
        found = False

        if key in self.params:
            val = self.params[key]
            found = True
        else:
            canonical = self.ALIAS_MAP.get(key)
            if canonical and canonical in self.params:
                val = self.params[canonical]
                found = True

        if not found:
            for alias, can in self.ALIAS_MAP.items():
                if can == key and alias in self.params:
                    val = self.params[alias]
                    found = True
                    break

        if not found or val is None:
            return default

        if expected_type is not None:
            val = self._coerce_type(val, expected_type, default)

        return val

    def get_step_runtime(
        self,
        total_steps: int,
        default_step_time: float = 1.0,
        complexity_factor: float = 1.0,
        min_step_time: float = 0.4,
        max_step_time: float = 3.0,
        target_duration: Optional[float] = None,
    ) -> float:
        """Calculates dynamic runtime for an animation step based on step count and complexity.

        Uses logarithmic sub-linear damping scaling to prevent rapid acceleration
        or illegible flickering as step count increases.
        """
        try:
            min_st = float(min_step_time)
            if not math.isfinite(min_st) or min_st < 0:
                min_st = 0.4
        except (ValueError, TypeError, OverflowError, ArithmeticError):
            min_st = 0.4

        try:
            max_st = float(max_step_time)
            if not math.isfinite(max_st) or max_st < 0:
                max_st = 3.0
        except (ValueError, TypeError, OverflowError, ArithmeticError):
            max_st = 3.0

        if min_st > max_st:
            min_st, max_st = max_st, min_st

        try:
            def_st = float(default_step_time)
            if not math.isfinite(def_st) or def_st < 0:
                def_st = 1.0
        except (ValueError, TypeError, OverflowError, ArithmeticError):
            def_st = 1.0

        try:
            comp_f = float(complexity_factor)
            if not math.isfinite(comp_f) or comp_f < 0:
                comp_f = 1.0
        except (ValueError, TypeError, OverflowError, ArithmeticError):
            comp_f = 1.0

        try:
            steps = int(total_steps)
        except (ValueError, TypeError, OverflowError, ArithmeticError):
            try:
                steps_f = float(total_steps)
                if math.isinf(steps_f) or math.isnan(steps_f):
                    steps = 0
                else:
                    steps = int(steps_f)
            except (ValueError, TypeError, OverflowError, ArithmeticError):
                steps = 0

        if steps <= 0:
            return max(min_st, min(def_st, max_st))

        duration = target_duration
        if duration is None:
            duration = self.get_parameter("duration", None, expected_type=float)

        if duration is not None:
            try:
                duration_val = float(duration)
                if not math.isfinite(duration_val) or duration_val < 0:
                    damped_factor = 1.0 + 0.3 * math.log(steps)
                    raw_step_time = (def_st / damped_factor) * comp_f
                else:
                    damped_factor = 1.0 + math.log(steps)
                    raw_step_time = (duration_val / damped_factor) * comp_f
            except (ValueError, TypeError, OverflowError, ArithmeticError):
                damped_factor = 1.0 + 0.3 * math.log(steps)
                raw_step_time = (def_st / damped_factor) * comp_f
        else:
            damped_factor = 1.0 + 0.3 * math.log(steps)
            raw_step_time = (def_st / damped_factor) * comp_f

        return max(min_st, min(raw_step_time, max_st))

    def animate_continuous_wait(
        self,
        duration: float = 1.0,
        pulse_targets: Optional[List[Any]] = None,
        mode: str = "pulse",
        rate_func: Any = None,
        scale_factor: float = 1.03,
        opacity_range: Tuple[float, float] = (0.85, 1.0),
    ) -> None:
        """Generates continuous ambient micro-motion during wait holds to avoid static freeze frames."""
        if not MANIM_AVAILABLE:
            return

        targets = pulse_targets or []
        if not targets and self.header_mobject is not None:
            targets = [self.header_mobject]
        if not targets and hasattr(self, "mobjects") and getattr(self, "mobjects", None):
            targets = getattr(self, "mobjects")[:3]

        if not targets:
            self.wait(duration)
            return

        saved_states = []
        for t in targets:
            state = {}
            if hasattr(t, "get_fill_opacity"):
                try:
                    val = t.get_fill_opacity()
                    if isinstance(val, (int, float)):
                        state["fill_opacity"] = float(val)
                except Exception:
                    pass
            if hasattr(t, "get_stroke_opacity"):
                try:
                    val = t.get_stroke_opacity()
                    if isinstance(val, (int, float)):
                        state["stroke_opacity"] = float(val)
                except Exception:
                    pass
            if "fill_opacity" not in state and "stroke_opacity" not in state and hasattr(t, "get_opacity"):
                try:
                    val = t.get_opacity()
                    if isinstance(val, (int, float)):
                        state["opacity"] = float(val)
                except Exception:
                    pass
            saved_states.append((t, state))

        try:
            rf = rate_func
            if rf is None and there_and_back is not None:
                rf = there_and_back

            if mode == "opacity":
                min_op, max_op = opacity_range
                anims = [t.animate.set_opacity(min_op) for t in targets if hasattr(t, "animate")]
            else:
                anims = [t.animate.scale(scale_factor) for t in targets if hasattr(t, "animate")]

            if anims:
                if rf is not None:
                    self.play(*anims, run_time=duration, rate_func=rf)
                else:
                    self.play(*anims, run_time=duration)
                return
        except Exception as err:
            logger.debug("Ambient animation fallback to standard wait due to exception: %s", err)
            self.wait(duration)
        finally:
            for t, state in saved_states:
                try:
                    if "fill_opacity" in state and hasattr(t, "set_fill"):
                        t.set_fill(opacity=state["fill_opacity"])
                    if "stroke_opacity" in state and hasattr(t, "set_stroke"):
                        t.set_stroke(opacity=state["stroke_opacity"])
                    if "opacity" in state and hasattr(t, "set_opacity"):
                        t.set_opacity(state["opacity"])
                except Exception:
                    pass

    def setup(self) -> None:
        """Manim setup lifecycle hook."""
        if hasattr(super(), "setup"):
            super().setup()
        if not self.params:
            self.load_parameters()

    def construct(self) -> None:
        """Standard Manim scene construct method called by Manim CLI."""
        if not self.params:
            self.load_parameters()
        self.setup_scene_header()
        self.construct_dsa_animation()

    def render_with_params(self, params: Dict[str, Any]) -> None:
        """Entry point called by dynamic wrapper script to pass parameters."""
        self.load_parameters(params)
        if MANIM_AVAILABLE:
            self.setup_scene_header()
            self.construct_dsa_animation()
        else:
            logger.info("Manim not installed: Skipping graphical construction.")

    def setup_scene_header(self) -> None:
        """Renders standard scene header title if present."""
        if not MANIM_AVAILABLE:
            return
        title_text = self.get_parameter("title", "")

        if title_text:
            self.header_mobject = Text(title_text, font_size=28, color=self.theme.PRIMARY_ACCENT)
            self.header_mobject.to_corner(UP + LEFT, buff=0.5)
            self.add(self.header_mobject)

    def construct_dsa_animation(self) -> None:
        """Override in concrete scene subclasses to build visual animations."""
        pass


