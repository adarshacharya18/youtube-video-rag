"""
Unit test suite for BaseDSAScene parameter schema, alias resolution, logarithmic educational timing, and ambient wait animation helper.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import math
import pytest

from src.animation.scenes.base_scene import (
    BaseDSAScene,
    GLOBAL_ALIAS_MAP,
    MANIM_AVAILABLE,
)

try:
    from pydantic import BaseModel
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


class SampleArraySchema(BaseModel if PYDANTIC_AVAILABLE else object):  # type: ignore
    array: List[int]
    title: Optional[str] = "Array Visualization"
    duration: float = 5.0


def test_global_alias_map_canonical_coverage():
    """Verify that GLOBAL_ALIAS_MAP contains canonical names specified in task requirements."""
    canonical_targets = {
        "array",
        "nodes",
        "code",
        "vertices",
        "edges",
        "step_duration",
        "time_complexity",
        "space_complexity",
        "highlight_lines",
        "elements",
        "entries",
    }
    present_canonicals = set(GLOBAL_ALIAS_MAP.values())
    for target in canonical_targets:
        assert target in present_canonicals, f"Canonical parameter name '{target}' missing from GLOBAL_ALIAS_MAP"


def test_alias_resolution_in_load_parameters():
    """Verify that parameter loading maps alternative key aliases to canonical names."""
    scene = BaseDSAScene()
    raw_params = {
        "data": [10, 20, 30],
        "node_list": ["N1", "N2"],
        "snippet": "def foo(): pass",
        "active_lines": [1, 2],
        "time": "O(N)",
        "space": "O(1)",
        "items": ["A", "B"],
        "key_values": {"k1": "v1"},
        "step_time": 1.5,
    }
    loaded = scene.load_parameters(raw_params)

    assert scene.get_parameter("array") == [10, 20, 30]
    assert scene.get_parameter("nodes") == ["N1", "N2"]
    assert scene.get_parameter("code") == "def foo(): pass"
    assert scene.get_parameter("highlight_lines") == [1, 2]
    assert scene.get_parameter("time_complexity") == "O(N)"
    assert scene.get_parameter("space_complexity") == "O(1)"
    assert scene.get_parameter("elements") == ["A", "B"]
    assert scene.get_parameter("entries") == {"k1": "v1"}
    assert scene.get_parameter("step_duration") == 1.5


def test_custom_alias_override_and_extension():
    """Verify custom_aliases can extend or override default alias mapping."""
    scene = BaseDSAScene()
    raw_params = {"my_custom_array": [5, 4, 3, 2, 1]}
    custom_map = {"my_custom_array": "array"}
    scene.load_parameters(raw_params, custom_aliases=custom_map)

    assert scene.get_parameter("array") == [5, 4, 3, 2, 1]
    assert scene.get_parameter("my_custom_array") == [5, 4, 3, 2, 1]


def test_get_parameter_type_coercion():
    """Verify safe type coercion for parameter access."""
    scene = BaseDSAScene()
    scene.params = {
        "step_duration": "2.5",
        "count": "42",
        "values": (1, 2, 3),
        "invalid_num": "not_a_number",
        "flag_str": "true",
    }

    # Coercion to float
    assert scene.get_parameter("step_duration", default=1.0, expected_type=float) == 2.5
    # Coercion to int
    assert scene.get_parameter("count", default=0, expected_type=int) == 42
    # Invalid coercion falls back to default
    assert scene.get_parameter("invalid_num", default=10, expected_type=int) == 10
    # Coercion tuple -> list
    assert scene.get_parameter("values", default=[], expected_type=list) == [1, 2, 3]
    # Coercion str -> bool
    assert scene.get_parameter("flag_str", default=False, expected_type=bool) is True


def test_load_params_from_json_backwards_compatibility(tmp_path):
    """Verify backwards-compatible load_params_from_json calls load_parameters correctly."""
    param_file = tmp_path / "parameters.json"
    param_file.write_text(json.dumps({"arr": [100, 200], "header": "Test Header"}), encoding="utf-8")

    scene = BaseDSAScene()
    result = scene.load_params_from_json(str(param_file))

    assert result["array"] == [100, 200]
    assert scene.get_parameter("array") == [100, 200]
    assert scene.get_parameter("title") == "Test Header"


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
def test_pydantic_schema_validation():
    """Verify parameters can be validated against a Pydantic schema."""
    scene = BaseDSAScene()
    raw_params = {"data": [1, 2, 3], "title": "Pydantic Test", "duration": "4.5"}
    scene.load_parameters(raw_params, schema=SampleArraySchema)

    assert scene.get_parameter("array") == [1, 2, 3]
    assert scene.get_parameter("title") == "Pydantic Test"
    assert scene.get_parameter("duration") == 4.5


def test_pydantic_schema_validation_fallback_on_error():
    """Verify that invalid schema fields log a warning and gracefully fall back to normalized dict."""
    scene = BaseDSAScene()
    raw_params = {"data": "invalid_array_type", "title": "Fallback Test"}
    
    # Should not raise exception, falls back to normalized dictionary
    scene.load_parameters(raw_params, schema=SampleArraySchema)
    assert scene.params.get("array") == "invalid_array_type"


def test_logarithmic_step_runtime_calculations():
    """Verify logarithmic sub-linear damping timing calculation in get_step_runtime."""
    scene = BaseDSAScene()
    scene.params = {"duration": 5.0}

    # Zero or negative step count returns clamped default
    assert scene.get_step_runtime(0, default_step_time=1.0) == 1.0
    assert scene.get_step_runtime(-5, default_step_time=1.0) == 1.0

    # Sub-linear damping scaling comparison:
    # Linear division for 20 steps with 5s duration would be 5/20 = 0.25s.
    # Logarithmic damping formula produces a significantly larger readable step time.
    runtime_5 = scene.get_step_runtime(5)
    runtime_20 = scene.get_step_runtime(20)
    runtime_100 = scene.get_step_runtime(100)

    # 1. Step runtimes remain above min_step_time (0.4s)
    assert runtime_5 >= 0.4
    assert runtime_20 >= 0.4
    assert runtime_100 >= 0.4

    # 2. 20 steps runtime is much higher than rigid linear 5.0/20 = 0.25s
    assert runtime_20 > 0.25

    # 3. Logarithmic damping is sub-linear (runtime decreases smoothly, not precipitous 1/N crash)
    assert runtime_5 >= runtime_20 >= runtime_100

    # Test complexity factor scaling
    runtime_normal = scene.get_step_runtime(10, complexity_factor=1.0)
    runtime_complex = scene.get_step_runtime(10, complexity_factor=1.5)
    assert runtime_complex >= runtime_normal

    # Test custom target_duration parameter
    runtime_target = scene.get_step_runtime(10, target_duration=10.0)
    runtime_default_target = scene.get_step_runtime(10, target_duration=5.0)
    assert runtime_target >= runtime_default_target

    # Test clamping limits
    runtime_clamped_max = scene.get_step_runtime(1, max_step_time=2.0)
    assert runtime_clamped_max <= 2.0

    runtime_clamped_min = scene.get_step_runtime(1000, min_step_time=0.5)
    assert runtime_clamped_min >= 0.5


def test_animate_continuous_wait_stub_and_manim():
    """Verify animate_continuous_wait runs without errors in stub mode and with targets."""
    scene = BaseDSAScene()
    scene.load_parameters({"title": "Ambient Test", "duration": 2.0})

    # Call with default args
    scene.animate_continuous_wait(duration=0.5)

    # Call with mode pulse and opacity
    scene.animate_continuous_wait(duration=0.5, mode="pulse", scale_factor=1.05)
    scene.animate_continuous_wait(duration=0.5, mode="opacity", opacity_range=(0.8, 1.0))

    if MANIM_AVAILABLE:
        scene.setup_scene_header()
        assert scene.header_mobject is not None
        scene.animate_continuous_wait(duration=0.5, pulse_targets=[scene.header_mobject])


def test_render_with_params():
    """Verify render_with_params entry point loads params and runs construction lifecycle safely."""
    scene = BaseDSAScene()
    params = {"title": "Dynamic Render Test", "data": [1, 2, 3, 4], "duration": 3.0}
    scene.render_with_params(params)

    assert scene.get_parameter("array") == [1, 2, 3, 4]
    assert scene.get_parameter("title") == "Dynamic Render Test"


def test_non_dict_json_roots(tmp_path):
    """Verify non-dict JSON root values (lists, strings, numbers, null) fall back gracefully to empty dict."""
    scene = BaseDSAScene()
    for root_content in ["[1, 2, 3]", '"just a string"', "12345", "null"]:
        json_file = tmp_path / f"test_root_{abs(hash(root_content))}.json"
        json_file.write_text(root_content, encoding="utf-8")
        res = scene.load_parameters(str(json_file))
        assert isinstance(res, dict)
        assert res == {}

    # Direct non-dict parameter call
    assert scene.load_parameters([1, 2, 3]) == {}
    assert scene.load_parameters("not_a_path") == {}


def test_string_step_counts_in_get_step_runtime():
    """Verify string step counts and malformed numeric parameters are safely handled in get_step_runtime."""
    scene = BaseDSAScene()

    # Valid string step count
    runtime_str = scene.get_step_runtime("10")
    runtime_int = scene.get_step_runtime(10)
    assert math.isclose(runtime_str, runtime_int)

    # Invalid string step count falls back to bounds check
    runtime_invalid = scene.get_step_runtime("invalid_steps")
    assert 0.4 <= runtime_invalid <= 3.0

    # Malformed complexity factor and min/max timing strings
    runtime_bad_comp = scene.get_step_runtime(10, complexity_factor="invalid")
    assert 0.4 <= runtime_bad_comp <= 3.0

    runtime_bad_bounds = scene.get_step_runtime(10, min_step_time="bad", max_step_time="bad")
    assert 0.4 <= runtime_bad_bounds <= 3.0


def test_float_infinity_integer_conversion():
    """Verify float infinity and NaN values return defaults without raising OverflowError or ValueError."""
    scene = BaseDSAScene()
    scene.params["inf_key"] = float("inf")
    scene.params["nan_key"] = float("nan")

    val_inf = scene.get_parameter("inf_key", default=99, expected_type=int)
    assert val_inf == 99

    val_nan = scene.get_parameter("nan_key", default=99, expected_type=int)
    assert val_nan == 99

    # Runtime check with float inf step count
    runtime_inf = scene.get_step_runtime(float("inf"))
    assert 0.4 <= runtime_inf <= 3.0


def test_invalid_custom_aliases_handling():
    """Verify non-dict custom_aliases parameter does not crash alias resolution."""
    scene = BaseDSAScene()
    raw_params = {"data": [1, 2, 3]}

    # Pass non-dict custom_aliases strings or lists
    res_str = scene.load_parameters(raw_params, custom_aliases="invalid_aliases")
    assert res_str.get("array") == [1, 2, 3]

    res_list = scene.load_parameters(raw_params, custom_aliases=["a", "b"])
    assert res_list.get("array") == [1, 2, 3]


def test_non_destructive_opacity_restoration():
    """Verify animate_continuous_wait in opacity mode explicitly restores initial Mobject opacity."""
    scene = BaseDSAScene()
    if MANIM_AVAILABLE:
        from manim import Text, Square
        txt = Text("Opacity Restoration Test")
        sq = Square(side_length=1.5)
        scene.add(txt, sq)

        init_fill_txt = txt.get_fill_opacity()
        init_fill_sq = sq.get_fill_opacity()
        init_stroke_sq = sq.get_stroke_opacity()

        for _ in range(5):
            scene.animate_continuous_wait(
                duration=0.1, pulse_targets=[txt, sq], mode="opacity", opacity_range=(0.7, 0.95)
            )

        assert math.isclose(txt.get_fill_opacity(), init_fill_txt, abs_tol=1e-4)
        assert math.isclose(sq.get_fill_opacity(), init_fill_sq, abs_tol=1e-4)
        assert math.isclose(sq.get_stroke_opacity(), init_stroke_sq, abs_tol=1e-4)

