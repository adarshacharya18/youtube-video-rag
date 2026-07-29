# Phase 07: Test Infrastructure & Verification Analysis

## Executive Summary
This document provides a comprehensive test infrastructure and verification analysis for Phase 07 (Prompt Library & Management). It establishes the testing strategy, test fixture design, expected output contracts, and exact test suite specification for `tests/llm/test_prompt_loader.py` validating `src/core/llm/prompt_loader.py`.

---

## 1. Existing Test Infrastructure & Conventions

### 1.1 Directory Structure
The repository follows a clean, module-aligned test layout under `tests/`:
```
tests/
├── conftest.py               # Global fixtures (temp_data_dir, test_config, mock_logger)
├── core/                     # Unit tests for src/core (config, base, exceptions, logger)
├── fixtures/                 # Static test fixtures (e.g. ingestion problem markdown files)
├── ingestion/                # Unit & integration tests for parser/sanitizer
├── llm/                      # LLM layer tests
│   ├── __init__.py
│   ├── test_providers.py     # Provider tests (OpenAIClient, AnthropicClient)
│   └── test_prompt_loader.py # [Target file to be created in Phase 07]
├── models/                   # Validation tests for Pydantic V2 models
└── ...
```

### 1.2 Test Conventions & Coding Standards
From analyzing existing tests (`tests/llm/test_providers.py`, `tests/core/test_config.py`, `tests/ingestion/test_parser.py`):
1. **Type Annotations**: Test functions use return type annotations (`def test_...() -> None:`).
2. **Docstrings**: Every test function includes a descriptive single or multi-line docstring explaining the tested capability and assertion logic.
3. **Pytest Fixtures**:
   - Isolated filesystem testing via pytest's built-in `tmp_path` fixture.
   - Global configuration overrides via `monkeypatch` or custom fixtures in `conftest.py`.
   - Data factories and mock object generators.
4. **Assertions**:
   - Strict string matching (`assert output == expected_string`).
   - Exception type and message checking using `pytest.raises(ExcType, match=...)`.
   - Parametrization using `@pytest.mark.parametrize` for boundary testing.
5. **Dependencies**:
   - Python 3.13 / Pytest 9.1.1.
   - Requires `jinja2` (to be added to dependencies).

---

## 2. Test Strategy for `tests/llm/test_prompt_loader.py`

### 2.1 Testing Goals
1. **Engine Verification**: Ensure `PromptLoader` correctly initializes Jinja2 `Environment` with strict variable checking (`StrictUndefined` or appropriate error handling).
2. **Template Loading & Versioning**: Verify loading templates across versions (`v1`, `v2`) with automatic extension resolution (`.j2`).
3. **Strict String Match Assertions**: As mandated by Phase 07 Acceptance Criteria, actively render Jinja templates with mock variables and assert the rendered output strictly matches expected hardcoded strings.
4. **Error Handling**: Verify robust domain exception handling (`PromptNotFoundError`, `PromptRenderError`) when templates/versions are missing or contain Jinja syntax/undefined variable errors.
5. **Real Template Verification**: Verify that the actual repository templates (`educational_plan.j2` and `code_explanation.j2`) can be loaded and rendered without error.

---

## 3. Mock Templates & Test Fixtures Setup

### 3.1 `mock_prompt_dir` Pytest Fixture
To ensure isolated unit tests, we define a pytest fixture `mock_prompt_dir` using `tmp_path` to build a mock template hierarchy:

```python
import pytest
from pathlib import Path
from src.core.llm.prompt_loader import PromptLoader

@pytest.fixture
def mock_prompt_dir(tmp_path: Path) -> Path:
    """
    Creates an isolated temporary directory tree containing versioned Jinja2 prompt templates.
    
    Structure:
        tmp_path / "prompts" / "v1" / "educational_plan.j2"
        tmp_path / "prompts" / "v1" / "code_explanation.j2"
        tmp_path / "prompts" / "v1" / "syntax_error.j2"
        tmp_path / "prompts" / "v2" / "educational_plan.j2"
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
```

---

## 4. Hardcoded Canonical Expected Strings

For strict string matching assertions:

```python
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
    "- Analyze O(N) Time Complexity\n"
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
```

---

## 5. Required Test Suite Breakdown

The test suite in `tests/llm/test_prompt_loader.py` must contain the following detailed test cases:

### Suite 1: Initialization & Directory Inspection
1. `test_prompt_loader_init_valid_directory(mock_prompt_dir: Path) -> None`
   - Validates that `PromptLoader` initializes cleanly with a valid `template_dir`.
   - Asserts `loader.template_dir` matches `mock_prompt_dir`.

2. `test_prompt_loader_init_non_existent_directory(tmp_path: Path) -> None`
   - Attempts to instantiate `PromptLoader` with `tmp_path / "does_not_exist"`.
   - Asserts `PromptNotFoundError` or `ConfigurationError` is raised.

### Suite 2: Template Loading & Version Resolution
3. `test_get_template_v1_success(prompt_loader: PromptLoader) -> None`
   - Calls `prompt_loader.get_template("educational_plan.j2", version="v1")`.
   - Asserts returned object is a valid Jinja2 `Template`.

4. `test_get_template_without_extension(prompt_loader: PromptLoader) -> None`
   - Calls `prompt_loader.get_template("educational_plan", version="v1")` (omitting `.j2`).
   - Asserts that `.j2` extension is automatically appended and template is loaded correctly.

5. `test_get_template_different_versions(prompt_loader: PromptLoader) -> None`
   - Loads `educational_plan` from `v1` and `v2`.
   - Asserts the template sources are distinct.

6. `test_list_templates(prompt_loader: PromptLoader) -> None`
   - Calls `prompt_loader.list_templates(version="v1")`.
   - Asserts returned list contains `["code_explanation.j2", "educational_plan.j2", "syntax_error.j2"]` (sorted).

7. `test_list_versions(prompt_loader: PromptLoader) -> None`
   - Calls `prompt_loader.list_versions()`.
   - Asserts returned list contains `["v1", "v2"]`.

### Suite 3: Rendering with Mock Variables & Strict String Assertions
8. `test_render_educational_plan_v1_strict_string_match(prompt_loader: PromptLoader) -> None`
   - Renders `educational_plan.j2` with variables:
     ```python
     vars_data = {
         "topic": "Two Sum",
         "difficulty": "Easy",
         "learning_objectives": ["Understand Hash Map Approach", "Analyze O(N) Time Complexity"],
         "include_code_walkthrough": True,
     }
     ```
   - Asserts rendered string strictly equals `EXPECTED_EDUCATIONAL_PLAN_V1`.

9. `test_render_educational_plan_v1_conditional_false(prompt_loader: PromptLoader) -> None`
   - Renders with `include_code_walkthrough=False`.
   - Asserts rendered string strictly equals `EXPECTED_EDUCATIONAL_PLAN_V1_NO_WALKTHROUGH`.

10. `test_render_code_explanation_v1_strict_string_match(prompt_loader: PromptLoader) -> None`
    - Renders `code_explanation.j2` with problem title, python code snippet, time/space complexity.
    - Asserts rendered string strictly equals `EXPECTED_CODE_EXPLANATION_V1`.

11. `test_render_v2_template_version_override(prompt_loader: PromptLoader) -> None`
    - Renders `educational_plan` passing `version="v2"`.
    - Asserts rendered string strictly equals `EXPECTED_EDUCATIONAL_PLAN_V2`.

### Suite 4: Error Handling & Edge Cases
12. `test_render_missing_template_raises_prompt_not_found(prompt_loader: PromptLoader) -> None`
    - Calls `prompt_loader.render("non_existent_template", version="v1", variables={})`.
    - Asserts `PromptNotFoundError` is raised with descriptive message.

13. `test_render_missing_version_raises_prompt_not_found(prompt_loader: PromptLoader) -> None`
    - Calls `prompt_loader.render("educational_plan", version="v99", variables={})`.
    - Asserts `PromptNotFoundError` is raised.

14. `test_render_syntax_error_raises_prompt_render_error(prompt_loader: PromptLoader) -> None`
    - Calls `prompt_loader.render("syntax_error", version="v1", variables={})`.
    - Asserts `PromptRenderError` is raised with details on template syntax failure.

15. `test_render_undefined_variable_raises_prompt_render_error(prompt_loader: PromptLoader) -> None`
    - Renders `educational_plan` with missing required variable (e.g. `{}`).
    - Asserts `PromptRenderError` or `ValidationError` is raised due to undefined variable.

### Suite 5: Integration Test with Real Project Templates
16. `test_real_foundational_templates_exist_and_render() -> None`
    - Instantiates `PromptLoader` pointing to default repository template dir (`src/core/llm/prompts`).
    - Verifies real `v1/educational_plan.j2` and `v1/code_explanation.j2` exist and can render with valid sample context data.

---

## 6. Verification Plan & Test Execution Command

Once `src/core/llm/prompt_loader.py` and `tests/llm/test_prompt_loader.py` are implemented:
```bash
./.venv/bin/pytest tests/llm/test_prompt_loader.py -v --cov=src/core/llm/prompt_loader
```
Verification criteria:
- 100% of test cases pass cleanly.
- Strict string match assertions validate exact rendering output.
- Missing template & version error cases raise appropriate domain exceptions.
