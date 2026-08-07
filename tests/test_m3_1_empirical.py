"""Empirical Verification & Stress Test Suite for M3 CodeScene and ComplexityScene.

Tests edge cases, parameter combinations, invalid parameters, and extreme durations for:
- src/animation/scenes/code_scene.py (CodeScene)
- src/animation/scenes/complexity_scene.py (ComplexityScene)
"""

from pathlib import Path
import pytest

from src.animation.scenes.code_scene import CodeScene, CodeSceneParameters
from src.animation.scenes.complexity_scene import ComplexityScene, ComplexitySceneParameters


# ==========================================================
# 1. CodeScene Unit & Parsing Empirical Stress Tests
# ==========================================================

class TestCodeSceneParsingUnit:
    """Unit stress tests for CodeScene helper methods and parameter schema."""

    def test_parse_highlight_lines_variations(self):
        scene = CodeScene()
        
        # Scenario 1: None / empty
        scene.load_parameters({})
        assert scene._parse_highlight_lines() == []

        # Scenario 2: List of mixed types (int, float, invalid str)
        scene.load_parameters({"highlight_lines": [1, 3.0, "5", "invalid", None]})
        assert scene._parse_highlight_lines() == [1, 3, 5]

        # Scenario 3: Range string e.g. "3-7"
        scene.load_parameters({"highlight_lines": "3-7"})
        assert scene._parse_highlight_lines() == [3, 4, 5, 6, 7]

        # Scenario 4: Single int / float / string digit
        scene.load_parameters({"highlight_lines": 4})
        assert scene._parse_highlight_lines() == [4]

        scene.load_parameters({"highlight_lines": "12"})
        assert scene._parse_highlight_lines() == [12]

        # Scenario 5: Alias 'lines' parameter fallback
        scene.load_parameters({"lines": "1-3"})
        assert scene._parse_highlight_lines() == [1, 2, 3]

        # Scenario 6: Malformed range strings
        scene.load_parameters({"highlight_lines": "10-5"})  # reverse range -> empty list
        assert scene._parse_highlight_lines() == []

        scene.load_parameters({"highlight_lines": "abc-def"})
        assert scene._parse_highlight_lines() == []

    def test_parse_variables_variations(self):
        scene = CodeScene()

        # Scenario 1: None / empty
        scene.load_parameters({})
        assert scene._parse_variables() == {}

        # Scenario 2: Dict input
        scene.load_parameters({"variables": {"x": 10, "arr": [1, 2]}})
        assert scene._parse_variables() == {"x": 10, "arr": [1, 2]}

        # Scenario 3: List of dicts input (takes first element)
        scene.load_parameters({"variables": [{"a": 1, "b": 2}, {"a": 3, "b": 4}]})
        assert scene._parse_variables() == {"a": 1, "b": 2}

        # Scenario 4: Alias fallback 'variable_states' and 'watch_variables'
        scene.load_parameters({"variable_states": {"ptr": "0x1234"}})
        assert scene._parse_variables() == {"ptr": "0x1234"}

        scene.load_parameters({"watch_variables": {"count": 42}})
        assert scene._parse_variables() == {"count": 42}

    def test_parse_captions_variations(self):
        scene = CodeScene()

        # Scenario 1: None
        scene.load_parameters({})
        assert scene._parse_captions() == []

        # Scenario 2: List of strings/ints
        scene.load_parameters({"captions": ["Step 1", 2, "Step 3"]})
        assert scene._parse_captions() == ["Step 1", "2", "Step 3"]

        # Scenario 3: Single string
        scene.load_parameters({"captions": "Single caption note"})
        assert scene._parse_captions() == ["Single caption note"]

        # Scenario 4: Dict of line -> caption mapping
        scene.load_parameters({"captions": {2: "Line 2 exec", 1: "Line 1 exec"}})
        assert scene._parse_captions() == ["Line 1 exec", "Line 2 exec"]


# ==========================================================
# 2. ComplexityScene Unit & Growth Function Stress Tests
# ==========================================================

class TestComplexitySceneUnit:
    """Unit stress tests for ComplexityScene growth function mapping and schema."""

    def test_growth_function_mapping(self):
        scene = ComplexityScene()

        # Standard notations
        f_o1 = scene._get_growth_function("O(1)")
        assert f_o1(10.0) == 1.0

        f_ologn = scene._get_growth_function("O(log N)")
        assert f_ologn(10.0) > 0

        f_on = scene._get_growth_function("O(N)")
        assert f_on(5.0) == 5.0

        f_onlogn = scene._get_growth_function("O(N log N)")
        assert f_onlogn(10.0) > 0

        f_on2 = scene._get_growth_function("O(N^2)")
        assert f_on2(10.0) == 8.0

        f_o2n = scene._get_growth_function("O(2^N)")
        assert f_o2n(5.0) > 0

        f_ve = scene._get_growth_function("O(V + E)")
        assert f_ve(10.0) == 12.0

        # Custom / unknown notation fallback (should return identity f(x)=x)
        f_custom = scene._get_growth_function("O(N^3 + 5)")
        assert f_custom(7.0) == 7.0

        f_complex = scene._get_growth_function("O(V \\log V + E)")
        assert f_complex(5.0) > 0


# ==========================================================
# 3. Manim End-to-End Rendering Empirical Verification
# ==========================================================

EMPIRICAL_STRESS_RENDER_TESTS = [
    # --- CodeScene Stress Cases ---
    (
        "M3_STRESS_CD_01_EMPTY_CODE",
        "src/animation/scenes/code_scene.py",
        "CodeScene",
        {"code": "", "highlight_lines": [], "duration": 2.0},
    ),
    (
        "M3_STRESS_CD_02_LONG_CODE_AUTOSCROLL",
        "src/animation/scenes/code_scene.py",
        "CodeScene",
        {
            "code": "\n".join([f"def line_{i}():\n    return {i}" for i in range(1, 12)]),  # 22 lines total
            "highlight_lines": [2, 10, 18, 20],
            "action": "auto_scroll",
            "duration": 4.0,
        },
    ),
    (
        "M3_STRESS_CD_03_EMPTY_VARS_WATCHER",
        "src/animation/scenes/code_scene.py",
        "CodeScene",
        {
            "code": "a = 1\nb = 2",
            "highlight_lines": [1, 2],
            "variables": {},
            "action": "variable_watcher",
            "duration": 3.0,
        },
    ),
    (
        "M3_STRESS_CD_04_EXTREME_SHORT_DURATION",
        "src/animation/scenes/code_scene.py",
        "CodeScene",
        {
            "code": "val = 42",
            "highlight_lines": [1],
            "duration": 0.1,
        },
    ),
    (
        "M3_STRESS_CD_05_OUT_OF_BOUNDS_LINES",
        "src/animation/scenes/code_scene.py",
        "CodeScene",
        {
            "code": "x = 10\ny = 20",
            "highlight_lines": [100, -5, 999],
            "duration": 3.0,
        },
    ),

    # --- ComplexityScene Stress Cases ---
    (
        "M3_STRESS_CX_01_CUSTOM_BIGO",
        "src/animation/scenes/complexity_scene.py",
        "ComplexityScene",
        {
            "time_complexity": "O(N^3 + \\log N)",
            "space_complexity": "O(N!)",
            "action": "dual_complexity",
            "duration": 3.0,
        },
    ),
    (
        "M3_STRESS_CX_02_EMPTY_CURVES_LIST",
        "src/animation/scenes/complexity_scene.py",
        "ComplexityScene",
        {
            "curves": [],
            "action": "growth_curves",
            "duration": 3.0,
        },
    ),
    (
        "M3_STRESS_CX_03_MANY_CURVES",
        "src/animation/scenes/complexity_scene.py",
        "ComplexityScene",
        {
            "curves": ["O(1)", "O(log N)", "O(N)", "O(N log N)", "O(N^2)", "O(2^N)"],
            "action": "growth_curves",
            "duration": 4.0,
        },
    ),
    (
        "M3_STRESS_CX_04_CURVE_TRACER_CUSTOM",
        "src/animation/scenes/complexity_scene.py",
        "ComplexityScene",
        {
            "curves": ["O(N log N)"],
            "action": "curve_tracer",
            "duration": 3.5,
        },
    ),
    (
        "M3_STRESS_CX_05_COMPARISON_BARS",
        "src/animation/scenes/complexity_scene.py",
        "ComplexityScene",
        {
            "curves": ["O(N)", "O(N^2)"],
            "action": "comparison_bars",
            "duration": 3.0,
        },
    ),
    (
        "M3_STRESS_CX_06_EXTREME_SHORT_DURATION",
        "src/animation/scenes/complexity_scene.py",
        "ComplexityScene",
        {
            "time_complexity": "O(1)",
            "duration": 0.1,
        },
    ),
    (
        "M3_STRESS_CX_07_INVALID_ACTION_FALLBACK",
        "src/animation/scenes/complexity_scene.py",
        "ComplexityScene",
        {
            "action": "non_existent_action_mode",
            "duration": 3.0,
        },
    ),
]


@pytest.mark.parametrize(
    "test_id,scene_file,class_name,params",
    EMPIRICAL_STRESS_RENDER_TESTS,
    ids=[tc[0] for tc in EMPIRICAL_STRESS_RENDER_TESTS],
)
def test_empirical_scene_rendering_stress(
    tmp_path, test_id, scene_file, class_name, params, manim_renderer, video_prober, frame_extractor, motion_analyzer
):
    """
    Renders each stress test case through ManimRenderer and asserts:
    1. Output MP4 exists and is > 100 bytes.
    2. Video probe shows nb_frames > 1 and duration > 0.05s.
    3. Motion analyzer confirms frame animation progression (max_delta > 0.001).
    """
    scene_script = Path(scene_file).resolve()
    out_dir = tmp_path / f"renders_{test_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_filename = f"{test_id.lower()}.mp4"

    rendered_video = manim_renderer.render(
        scene_script=scene_script,
        class_name=class_name,
        output_dir=out_dir,
        output_filename=out_filename,
        parameters=params,
    )

    # 1. File exists and non-empty
    assert rendered_video.exists(), f"Rendered file missing for {test_id}"
    assert rendered_video.stat().st_size > 100, f"Rendered file empty for {test_id}"

    # 2. Probe video
    nb_frames, duration = video_prober(rendered_video)
    assert nb_frames > 1, f"Expected >1 frame for {test_id}, got {nb_frames}"
    assert duration > 0.05, f"Expected duration >0.05s for {test_id}, got {duration}s"

    # 3. Motion analysis (for duration >= 1.0s)
    req_dur = float(params.get("duration", 3.0))
    if req_dur >= 1.0:
        frames_dir = tmp_path / f"frames_{test_id.lower()}"
        frames = frame_extractor(rendered_video, frames_dir, fps=5)
        assert len(frames) >= 2, f"Expected at least 2 frames for {test_id}"

        motion_deltas = [
            motion_analyzer(frames[i], frames[i + 1])
            for i in range(len(frames) - 1)
        ]
        max_delta = max(motion_deltas)
        assert max_delta > 0.001, f"Expected motion delta > 0.001 for {test_id}, got {max_delta:.6f}"
