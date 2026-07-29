"""
Unit and integration tests for PromptLoader.

Validates Jinja2 template loading, version resolution, strict string match rendering,
exception handling (TemplateNotFoundError, TemplateRenderError), caching, and real project
template integration.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
import jinja2
import pytest

from src.core.exceptions import (
    FatalError,
    PromptTemplateError,
    TemplateNotFoundError,
    TemplateRenderError,
)
from src.core.llm.prompt_loader import PromptLoader


# ============================================================================
# Canonical Expected Hardcoded Strings for Strict Output Matching
# ============================================================================

EXPECTED_EDUCATIONAL_PLAN_V1 = (
    "SYSTEM PROMPT: Educational Plan Generation (v1)\n"
    "Topic: Two Sum\n"
    "Difficulty: Easy\n"
    "Objectives:\n"
    "- Understand Hash Map Approach\n"
    "- Analyze O(N) Time Complexity\n"
    "Requirement: Include step-by-step code walkthrough."
)

EXPECTED_EDUCATIONAL_PLAN_V1_NO_WALKTHROUGH = (
    "SYSTEM PROMPT: Educational Plan Generation (v1)\n"
    "Topic: Two Sum\n"
    "Difficulty: Easy\n"
    "Objectives:\n"
    "- Understand Hash Map Approach\n"
    "- Analyze O(N) Time Complexity"
)

EXPECTED_CODE_EXPLANATION_V1 = (
    "SYSTEM PROMPT: Code Explanation (v1)\n"
    "Problem: Two Sum\n"
    "Language: python\n"
    "Code:\n"
    "```python\n"
    "def two_sum(nums, target):\n"
    "    seen = {}\n"
    "    for i, num in enumerate(nums):\n"
    "        diff = target - num\n"
    "        if diff in seen:\n"
    "            return [seen[diff], i]\n"
    "        seen[num] = i\n"
    "```\n"
    "Time Complexity: O(N)\n"
    "Space Complexity: O(N)"
)

EXPECTED_EDUCATIONAL_PLAN_V2 = (
    "SYSTEM PROMPT: Educational Plan Generation (v2 - Streamlined)\n"
    "Topic: TWO SUM\n"
    "Difficulty Level: Easy"
)


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def mock_prompt_dir(tmp_path: Path) -> Path:
    """
    Creates an isolated temporary directory tree containing versioned Jinja2 prompt templates.
    """
    base_dir = tmp_path / "prompts"
    v1_dir = base_dir / "v1"
    v2_dir = base_dir / "v2"
    v1_dir.mkdir(parents=True, exist_ok=True)
    v2_dir.mkdir(parents=True, exist_ok=True)

    # v1 educational_plan.j2
    (v1_dir / "educational_plan.j2").write_text(
        "SYSTEM PROMPT: Educational Plan Generation (v1)\n"
        "Topic: {{ topic }}\n"
        "Difficulty: {{ difficulty }}\n"
        "Objectives:\n"
        "{% for obj in learning_objectives %}\n"
        "- {{ obj }}\n"
        "{% endfor %}\n"
        "{% if include_code_walkthrough %}\n"
        "Requirement: Include step-by-step code walkthrough.\n"
        "{% endif %}",
        encoding="utf-8",
    )

    # v1 code_explanation.j2
    (v1_dir / "code_explanation.j2").write_text(
        "SYSTEM PROMPT: Code Explanation (v1)\n"
        "Problem: {{ problem_title }}\n"
        "Language: {{ language }}\n"
        "Code:\n"
        "```{{ language }}\n"
        "{{ code_snippet }}\n"
        "```\n"
        "Time Complexity: {{ complexity_time }}\n"
        "Space Complexity: {{ complexity_space }}",
        encoding="utf-8",
    )

    # v1 syntax_error.j2
    (v1_dir / "syntax_error.j2").write_text(
        "Broken Template: {% if unclosed_tag %}\nNo end block here",
        encoding="utf-8",
    )

    # v1 empty_output.j2
    (v1_dir / "empty_output.j2").write_text(
        "{# This template outputs nothing #}\n   \n",
        encoding="utf-8",
    )

    # v2 educational_plan.j2
    (v2_dir / "educational_plan.j2").write_text(
        "SYSTEM PROMPT: Educational Plan Generation (v2 - Streamlined)\n"
        "Topic: {{ topic | upper }}\n"
        "Difficulty Level: {{ difficulty }}",
        encoding="utf-8",
    )

    return base_dir


@pytest.fixture
def prompt_loader(mock_prompt_dir: Path) -> PromptLoader:
    """Returns a PromptLoader instance pointed to mock_prompt_dir."""
    return PromptLoader(template_dir=mock_prompt_dir)


# ============================================================================
# Suite 1: Initialization & Directory Inspection
# ============================================================================

def test_prompt_loader_init_with_path(mock_prompt_dir: Path) -> None:
    """Validate PromptLoader initialization with a Path object."""
    loader = PromptLoader(template_dir=mock_prompt_dir)
    assert loader.template_dir == mock_prompt_dir
    assert loader.default_version == "v1"
    assert loader.cache_templates is True
    assert loader.enable_cache is True


def test_prompt_loader_init_with_string_path(mock_prompt_dir: Path) -> None:
    """Validate PromptLoader initialization with a string path."""
    loader = PromptLoader(template_dir=str(mock_prompt_dir))
    assert loader.template_dir == mock_prompt_dir


def test_prompt_loader_init_default_dir() -> None:
    """Validate PromptLoader fallback default template directory initialization."""
    loader = PromptLoader()
    assert isinstance(loader.template_dir, Path)
    assert loader.template_dir == Path("src/core/llm/prompts")


def test_prompt_loader_init_cache_options(mock_prompt_dir: Path) -> None:
    """Validate PromptLoader initialization with disabled cache settings."""
    loader = PromptLoader(template_dir=mock_prompt_dir, cache_templates=False)
    assert loader.cache_templates is False
    assert loader.enable_cache is False

    loader_alias = PromptLoader(template_dir=mock_prompt_dir, enable_cache=False)
    assert loader_alias.cache_templates is False
    assert loader_alias.enable_cache is False


def test_prompt_loader_init_config_resolution() -> None:
    """Validate PromptLoader template_dir resolution from configuration objects."""
    # Test config with config.prompts.template_dir
    mock_cfg1 = MagicMock()
    mock_cfg1.prompts.template_dir = "/cfg/path1"
    with patch("src.core.llm.prompt_loader.load_config", return_value=mock_cfg1):
        loader1 = PromptLoader()
        assert loader1.template_dir == Path("/cfg/path1")

    # Test config with config.llm.prompts.template_dir
    mock_cfg2 = MagicMock(spec=["llm"])
    mock_cfg2.llm = MagicMock()
    mock_cfg2.llm.prompts.template_dir = "/cfg/path2"
    with patch("src.core.llm.prompt_loader.load_config", return_value=mock_cfg2):
        loader2 = PromptLoader()
        assert loader2.template_dir == Path("/cfg/path2")

    # Test config with neither attribute
    mock_cfg3 = MagicMock(spec=[])
    with patch("src.core.llm.prompt_loader.load_config", return_value=mock_cfg3):
        loader3 = PromptLoader()
        assert loader3.template_dir == Path("src/core/llm/prompts")

    # Test config raise exception fallback
    with patch("src.core.llm.prompt_loader.load_config", side_effect=RuntimeError("Config error")):
        loader4 = PromptLoader()
        assert loader4.template_dir == Path("src/core/llm/prompts")


# ============================================================================
# Suite 2: Template Loading & Version Resolution
# ============================================================================

def test_load_template_v1_success(prompt_loader: PromptLoader) -> None:
    """Verify loading a template with explicit version and extension."""
    template = prompt_loader.load_template("educational_plan.j2", version="v1")
    assert isinstance(template, jinja2.Template)


def test_load_template_auto_appends_j2_extension(prompt_loader: PromptLoader) -> None:
    """Verify automatic .j2 extension resolution when omitted."""
    template = prompt_loader.load_template("educational_plan", version="v1")
    assert isinstance(template, jinja2.Template)


def test_get_template_alias(prompt_loader: PromptLoader) -> None:
    """Verify get_template behaves identically as load_template alias."""
    template = prompt_loader.get_template("educational_plan", version="v1")
    assert isinstance(template, jinja2.Template)


def test_template_caching(mock_prompt_dir: Path) -> None:
    """Verify template caching returns identical Jinja2 Template instances when enabled."""
    cached_loader = PromptLoader(template_dir=mock_prompt_dir, cache_templates=True)
    t1 = cached_loader.load_template("educational_plan", version="v1")
    t2 = cached_loader.load_template("educational_plan", version="v1")
    assert t1 is t2

    uncached_loader = PromptLoader(template_dir=mock_prompt_dir, cache_templates=False)
    t3 = uncached_loader.load_template("educational_plan", version="v1")
    t4 = uncached_loader.load_template("educational_plan", version="v1")
    assert t3 is not t4


def test_load_template_different_versions(prompt_loader: PromptLoader) -> None:
    """Verify loading templates across versions retrieves version-specific templates."""
    t_v1 = prompt_loader.load_template("educational_plan", version="v1")
    t_v2 = prompt_loader.load_template("educational_plan", version="v2")

    res_v1 = t_v1.render(
        topic="Two Sum",
        difficulty="Easy",
        learning_objectives=[],
        include_code_walkthrough=False,
    )
    res_v2 = t_v2.render(topic="Two Sum", difficulty="Easy")

    assert "v1" in res_v1
    assert "v2 - Streamlined" in res_v2


def test_resolve_template_path_behavior(prompt_loader: PromptLoader) -> None:
    """Verify relative template path resolution internal logic."""
    assert prompt_loader._resolve_template_path("educational_plan") == "v1/educational_plan.j2"
    assert prompt_loader._resolve_template_path("educational_plan.j2") == "v1/educational_plan.j2"
    assert prompt_loader._resolve_template_path("educational_plan", version="v2") == "v2/educational_plan.j2"
    assert prompt_loader._resolve_template_path("custom/educational_plan.j2", version="v1") == "custom/educational_plan.j2"


# ============================================================================
# Suite 3: Template & Version Listing
# ============================================================================

def test_list_templates_v1(prompt_loader: PromptLoader) -> None:
    """Verify list_templates returns sorted list of template filenames for a version."""
    templates = prompt_loader.list_templates(version="v1")
    assert templates == [
        "code_explanation.j2",
        "educational_plan.j2",
        "empty_output.j2",
        "syntax_error.j2",
    ]


def test_list_templates_non_existent_version(prompt_loader: PromptLoader) -> None:
    """Verify list_templates returns an empty list for missing version directories."""
    assert prompt_loader.list_templates(version="v99") == []


def test_list_versions(prompt_loader: PromptLoader) -> None:
    """Verify list_versions returns sorted list of version directories."""
    assert prompt_loader.list_versions() == ["v1", "v2"]


def test_list_versions_non_existent_dir(tmp_path: Path) -> None:
    """Verify list_versions returns empty list if root template dir does not exist."""
    loader = PromptLoader(template_dir=tmp_path / "non_existent")
    assert loader.list_versions() == []


# ============================================================================
# Suite 4: Strict String Match Rendering
# ============================================================================

def test_render_educational_plan_v1_strict_string_match(prompt_loader: PromptLoader) -> None:
    """Verify render output strictly equals EXPECTED_EDUCATIONAL_PLAN_V1."""
    context = {
        "topic": "Two Sum",
        "difficulty": "Easy",
        "learning_objectives": [
            "Understand Hash Map Approach",
            "Analyze O(N) Time Complexity",
        ],
        "include_code_walkthrough": True,
    }
    rendered = prompt_loader.render("educational_plan", context=context, version="v1")
    assert rendered == EXPECTED_EDUCATIONAL_PLAN_V1


def test_render_educational_plan_v1_conditional_false_strict_string_match(
    prompt_loader: PromptLoader,
) -> None:
    """Verify render output strictly equals EXPECTED_EDUCATIONAL_PLAN_V1_NO_WALKTHROUGH when conditional is False."""
    context = {
        "topic": "Two Sum",
        "difficulty": "Easy",
        "learning_objectives": [
            "Understand Hash Map Approach",
            "Analyze O(N) Time Complexity",
        ],
        "include_code_walkthrough": False,
    }
    rendered = prompt_loader.render("educational_plan", context=context, version="v1")
    assert rendered == EXPECTED_EDUCATIONAL_PLAN_V1_NO_WALKTHROUGH


def test_render_code_explanation_v1_strict_string_match(prompt_loader: PromptLoader) -> None:
    """Verify render output strictly equals EXPECTED_CODE_EXPLANATION_V1."""
    code_snippet = (
        "def two_sum(nums, target):\n"
        "    seen = {}\n"
        "    for i, num in enumerate(nums):\n"
        "        diff = target - num\n"
        "        if diff in seen:\n"
        "            return [seen[diff], i]\n"
        "        seen[num] = i"
    )
    context = {
        "problem_title": "Two Sum",
        "language": "python",
        "code_snippet": code_snippet,
        "complexity_time": "O(N)",
        "complexity_space": "O(N)",
    }
    rendered = prompt_loader.render("code_explanation", context=context, version="v1")
    assert rendered == EXPECTED_CODE_EXPLANATION_V1


def test_render_v2_educational_plan_strict_string_match(prompt_loader: PromptLoader) -> None:
    """Verify render output strictly equals EXPECTED_EDUCATIONAL_PLAN_V2 for v2 template."""
    context = {
        "topic": "Two Sum",
        "difficulty": "Easy",
    }
    rendered = prompt_loader.render("educational_plan", context=context, version="v2")
    assert rendered == EXPECTED_EDUCATIONAL_PLAN_V2


def test_render_accepts_context_dict_and_kwargs(prompt_loader: PromptLoader) -> None:
    """Verify render merges context dict with keyword arguments."""
    context = {
        "topic": "Two Sum",
        "difficulty": "Easy",
        "learning_objectives": ["Understand Hash Map Approach", "Analyze O(N) Time Complexity"],
    }
    rendered = prompt_loader.render(
        "educational_plan",
        context=context,
        version="v1",
        include_code_walkthrough=True,
    )
    assert rendered == EXPECTED_EDUCATIONAL_PLAN_V1


# ============================================================================
# Suite 5: Exception Handling & Boundary Conditions
# ============================================================================

def test_load_missing_template_raises_template_not_found_error(
    prompt_loader: PromptLoader,
) -> None:
    """Verify loading missing template raises TemplateNotFoundError inheriting from PromptTemplateError."""
    with pytest.raises(TemplateNotFoundError) as exc_info:
        prompt_loader.load_template("non_existent_template", version="v1")

    assert issubclass(TemplateNotFoundError, PromptTemplateError)
    assert issubclass(TemplateNotFoundError, FatalError)
    assert "non_existent_template" in str(exc_info.value)
    assert "not found" in str(exc_info.value)


def test_load_missing_version_raises_template_not_found_error(
    prompt_loader: PromptLoader,
) -> None:
    """Verify loading template from a non-existent version directory raises TemplateNotFoundError."""
    with pytest.raises(TemplateNotFoundError) as exc_info:
        prompt_loader.load_template("educational_plan", version="v99")

    assert "v99" in str(exc_info.value)


def test_load_syntax_error_template_raises_template_render_error(
    prompt_loader: PromptLoader,
) -> None:
    """Verify loading a template with Jinja syntax errors raises TemplateRenderError."""
    with pytest.raises(TemplateRenderError) as exc_info:
        prompt_loader.load_template("syntax_error", version="v1")

    assert issubclass(TemplateRenderError, PromptTemplateError)
    assert issubclass(TemplateRenderError, FatalError)
    assert "Syntax error" in str(exc_info.value)


def test_load_template_generic_jinja_error_raises_template_render_error(
    prompt_loader: PromptLoader,
) -> None:
    """Verify generic jinja2.TemplateError during get_template raises TemplateRenderError."""
    with patch.object(prompt_loader.env, "get_template", side_effect=jinja2.TemplateError("Generic error")):
        with pytest.raises(TemplateRenderError) as exc_info:
            prompt_loader.load_template("educational_plan", version="v1")

        assert "Failed to load template" in str(exc_info.value)


def test_render_undefined_variable_raises_template_render_error(
    prompt_loader: PromptLoader,
) -> None:
    """Verify rendering a template with missing required context variables raises TemplateRenderError."""
    with pytest.raises(TemplateRenderError) as exc_info:
        # educational_plan.j2 requires 'topic', 'difficulty', etc.
        prompt_loader.render("educational_plan", context={}, version="v1")

    assert "Missing required context variable" in str(exc_info.value)


def test_render_empty_output_raises_template_render_error(
    prompt_loader: PromptLoader,
) -> None:
    """Verify rendering a template that evaluates to an empty string raises TemplateRenderError."""
    with pytest.raises(TemplateRenderError) as exc_info:
        prompt_loader.render("empty_output", context={}, version="v1")

    assert "rendered to an empty string" in str(exc_info.value)


def test_render_missing_template_raises_template_not_found_error(
    prompt_loader: PromptLoader,
) -> None:
    """Verify render passes through TemplateNotFoundError when template file is absent."""
    with pytest.raises(TemplateNotFoundError):
        prompt_loader.render("missing_template", context={}, version="v1")


def test_render_syntax_error_in_render_raises_template_render_error(
    prompt_loader: PromptLoader,
) -> None:
    """Verify Jinja2 TemplateSyntaxError during template rendering raises TemplateRenderError."""
    mock_tmpl = MagicMock()
    mock_tmpl.render.side_effect = jinja2.TemplateSyntaxError("Syntax error during render", 5)
    with patch.object(prompt_loader, "load_template", return_value=mock_tmpl):
        with pytest.raises(TemplateRenderError) as exc_info:
            prompt_loader.render("educational_plan", context={}, version="v1")

        assert "Syntax error in template" in str(exc_info.value)


def test_render_generic_jinja_error_raises_template_render_error(
    prompt_loader: PromptLoader,
) -> None:
    """Verify generic jinja2.TemplateError during rendering raises TemplateRenderError."""
    mock_tmpl = MagicMock()
    mock_tmpl.render.side_effect = jinja2.TemplateError("Generic render error")
    with patch.object(prompt_loader, "load_template", return_value=mock_tmpl):
        with pytest.raises(TemplateRenderError) as exc_info:
            prompt_loader.render("educational_plan", context={}, version="v1")

        assert "Failed to render template" in str(exc_info.value)


# ============================================================================
# Suite 6: Real Project Templates Integration
# ============================================================================

def test_real_educational_plan_template_exists_and_renders() -> None:
    """Verify real repository educational_plan.j2 template exists and renders correctly."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")
    context = {
        "topic": "Two Sum",
        "slug": "two-sum",
        "target_audience": "Beginner",
        "difficulty": "Easy",
        "target_duration_seconds": 180,
        "problem_description": "Given an array of integers nums and an integer target, return indices of two numbers.",
        "constraints": ["2 <= nums.length <= 10^4", "-10^9 <= nums[i] <= 10^9"],
        "learning_objectives": ["Understand Hash Map Approach"],
    }
    rendered = loader.render("educational_plan", context=context, version="v1")

    assert isinstance(rendered, str)
    assert len(rendered) > 100
    assert "Two Sum" in rendered
    assert "two-sum" in rendered
    assert "Beginner" in rendered
    assert "Easy" in rendered
    assert "180 seconds" in rendered
    assert "2 <= nums.length <= 10^4" in rendered


def test_real_code_explanation_template_exists_and_renders() -> None:
    """Verify real repository code_explanation.j2 template exists and renders correctly."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")
    context = {
        "topic": "Two Sum Hash Map",
        "language": "python",
        "code": "def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        if target - num in seen:\n            return [seen[target - num], i]\n        seen[num] = i",
        "time_complexity": "O(N)",
        "space_complexity": "O(N)",
        "line_highlights": [3, 4],
        "pitfalls": ["Index out of bounds", "Duplicate elements"],
    }
    rendered = loader.render("code_explanation", context=context, version="v1")

    assert isinstance(rendered, str)
    assert len(rendered) > 100
    assert "Two Sum Hash Map" in rendered
    assert "python" in rendered
    assert "O(N)" in rendered
    assert "Line 3:" in rendered
    assert "Index out of bounds" in rendered
