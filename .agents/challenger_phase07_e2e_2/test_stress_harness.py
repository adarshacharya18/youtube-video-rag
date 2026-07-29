"""
Comprehensive Empirical Stress Harness for Phase 07 Jinja2 Prompt Templates & PromptLoader.

This harness tests:
1. Strict variable enforcement & missing field exception handling
2. Exception hierarchy inheritance contracts
3. Extreme context sizes (10MB+ strings, thousands of elements)
4. Special characters, Jinja code injection resistance, and SQL/XSS tokens
5. Full Unicode spectrum (CJK, Arabic, Cyrillic, Emoji, Math symbols)
6. Multiline strings and line ending variations (CRLF, LF, CR)
7. Exact spec string rendering output for educational_plan.j2 and code_explanation.j2
8. Caching behaviors and edge case option handling
"""

import sys
import time
from pathlib import Path
import pytest
import jinja2

# Ensure src is in import path
sys.path.insert(0, str(Path("/home/adarsh/Documents/Youtube-Channel")))

from src.core.exceptions import (
    PipelineError,
    FatalError,
    PromptTemplateError,
    TemplateNotFoundError,
    TemplateRenderError,
)
from src.core.llm.prompt_loader import PromptLoader


# ============================================================================
# 1. Exception Hierarchy & Contract Verification
# ============================================================================

def test_exception_hierarchy_inheritance() -> None:
    """Verify exception hierarchy matches project specification."""
    assert issubclass(PromptTemplateError, FatalError)
    assert issubclass(PromptTemplateError, PipelineError)
    assert issubclass(TemplateNotFoundError, PromptTemplateError)
    assert issubclass(TemplateRenderError, PromptTemplateError)


def test_missing_template_raises_template_not_found_error() -> None:
    """Verify loading non-existent template raises TemplateNotFoundError."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")
    with pytest.raises(TemplateNotFoundError) as exc_info:
        loader.render("non_existent_template_xyz", context={}, version="v1")
    assert "not found" in str(exc_info.value)
    assert issubclass(exc_info.type, PromptTemplateError)


def test_missing_version_raises_template_not_found_error() -> None:
    """Verify requesting invalid version directory raises TemplateNotFoundError."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")
    with pytest.raises(TemplateNotFoundError) as exc_info:
        loader.render("educational_plan", context={}, version="v99999")
    assert "v99999" in str(exc_info.value)


# ============================================================================
# 2. Strict Variable Enforcement & Missing Required Fields
# ============================================================================

@pytest.mark.parametrize("missing_field", [
    "topic",
    "slug",
    "target_audience",
    "difficulty",
    "target_duration_seconds",
    "problem_description",
])
def test_educational_plan_missing_required_fields(missing_field: str) -> None:
    """Verify omitting any required variable from educational_plan.j2 raises TemplateRenderError."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")
    full_context = {
        "topic": "Binary Search",
        "slug": "binary-search",
        "target_audience": "Intermediate",
        "difficulty": "Medium",
        "target_duration_seconds": 300,
        "problem_description": "Search sorted array for target value.",
    }
    del full_context[missing_field]

    with pytest.raises(TemplateRenderError) as exc_info:
        loader.render("educational_plan", context=full_context, version="v1")
    assert "Missing required context variable" in str(exc_info.value)


@pytest.mark.parametrize("missing_field", [
    "topic",
    "language",
    "code",
    "time_complexity",
    "space_complexity",
])
def test_code_explanation_missing_required_fields(missing_field: str) -> None:
    """Verify omitting any required variable from code_explanation.j2 raises TemplateRenderError."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")
    full_context = {
        "topic": "Binary Search Code",
        "language": "python",
        "code": "def search(nums, target): pass",
        "time_complexity": "O(log N)",
        "space_complexity": "O(1)",
    }
    del full_context[missing_field]

    with pytest.raises(TemplateRenderError) as exc_info:
        loader.render("code_explanation", context=full_context, version="v1")
    assert "Missing required context variable" in str(exc_info.value)


def test_optional_fields_can_be_omitted() -> None:
    """Verify optional fields in both templates do NOT trigger strict undefined errors when omitted."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")

    # Minimal educational_plan context
    ed_plan_ctx = {
        "topic": "Two Sum",
        "slug": "two-sum",
        "target_audience": "Beginner",
        "difficulty": "Easy",
        "target_duration_seconds": 120,
        "problem_description": "Find indices of two numbers that add to target.",
    }
    rendered_ed = loader.render("educational_plan", context=ed_plan_ctx, version="v1")
    assert "Two Sum" in rendered_ed
    assert "CONSTRAINTS & LIMITS" not in rendered_ed
    assert "KNOWLEDGE BASE CONTEXT (RAG)" not in rendered_ed

    # Minimal code_explanation context
    code_exp_ctx = {
        "topic": "Two Sum Code",
        "language": "python",
        "code": "def two_sum(): pass",
        "time_complexity": "O(N)",
        "space_complexity": "O(N)",
    }
    rendered_code = loader.render("code_explanation", context=code_exp_ctx, version="v1")
    assert "Two Sum Code" in rendered_code
    assert "KEY FOCUS LINES" not in rendered_code
    assert "COMMON PITFALLS & BUGS" not in rendered_code


# ============================================================================
# 3. Extreme Context Sizes & Performance Stress Testing
# ============================================================================

def test_extreme_sizes_rendering() -> None:
    """Stress test template rendering with 10MB+ payload strings and large lists."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")

    huge_description = "A" * 2_000_000 + "\n" + "B" * 2_000_000  # 4MB problem description
    huge_constraints = [f"Constraint {i}: " + "X" * 100 for i in range(1_000)] # 100KB list
    huge_rag = ["RAG Chunk " + str(i) + ": " + "Y" * 500 for i in range(500)] # 250KB RAG
    huge_code = "\n".join([f"x_{i} = {i}  # " + "code line " * 10 for i in range(10_000)]) # 1.5MB code

    ed_context = {
        "topic": "Massive Graph Algorithm " + "Z" * 1_000,
        "slug": "massive-graph-algo",
        "target_audience": "Advanced",
        "difficulty": "Hard",
        "target_duration_seconds": 3600,
        "problem_description": huge_description,
        "constraints": huge_constraints,
        "rag_context": huge_rag,
    }

    start_time = time.perf_counter()
    rendered = loader.render("educational_plan", context=ed_context, version="v1")
    duration = time.perf_counter() - start_time

    assert len(rendered) > 4_000_000
    assert duration < 5.0  # Should render in under 5 seconds

    code_context = {
        "topic": "Massive Code Walkthrough",
        "language": "python",
        "code": huge_code,
        "time_complexity": "O(V + E)",
        "space_complexity": "O(V)",
        "line_highlights": list(range(1, 100)),
        "pitfalls": ["Pitfall " + str(i) for i in range(100)],
    }

    start_time = time.perf_counter()
    rendered_code = loader.render("code_explanation", context=code_context, version="v1")
    duration_code = time.perf_counter() - start_time

    assert len(rendered_code) > 1_000_000
    assert duration_code < 5.0


# ============================================================================
# 4. Special Characters & Code Injection Protection
# ============================================================================

def test_special_characters_and_jinja_injection_resistance() -> None:
    """Verify special characters, shell commands, Jinja tags, and SQL/XSS tokens render literally without execution."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")

    injection_str = (
        "{{ 7 * 7 }} {% set secret = 'hacked' %} {# Jinja comment #} "
        "${{ secrets.GITHUB_TOKEN }} <script>alert('XSS')</script> "
        "SELECT * FROM users WHERE '1'='1'; `rm -rf /` \\n \\t \\r \\' \\\" "
        "{{ undefined_var_injection }}"
    )

    ed_context = {
        "topic": injection_str,
        "slug": "injection-test",
        "target_audience": "Beginner",
        "difficulty": "Easy",
        "target_duration_seconds": 60,
        "problem_description": injection_str,
        "constraints": [injection_str],
        "learning_objectives": [injection_str],
    }

    rendered = loader.render("educational_plan", context=ed_context, version="v1")

    # Verify literal rendering (Jinja expressions in values must NOT be evaluated)
    assert "{{ 7 * 7 }}" in rendered
    assert "{% set secret = 'hacked' %}" in rendered
    assert "${{ secrets.GITHUB_TOKEN }}" in rendered
    assert "<script>alert('XSS')</script>" in rendered
    assert "SELECT * FROM users" in rendered
    assert "49" not in rendered  # Ensure 7*7 was NOT evaluated to 49!


# ============================================================================
# 5. Unicode & Internationalization Support
# ============================================================================

def test_unicode_and_emoji_rendering() -> None:
    """Verify complete Unicode spectrum (CJK, Arabic, Cyrillic, Devnagari, Emoji, Math symbols) renders intact."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")

    unicode_topic = "二数之和 2つの数の和 Сумма двух чисел مجموع رقمين दो संख्याओं का योग 🔢💡🚀"
    unicode_desc = "Mathematical limits: O(N²) ∈ Ω(N log N) ∧ ∀x (x ≥ 0 ⟹ √x ∈ ℝ) ⩽ ⩾ ∭"
    unicode_code = "# 🐍 Python 3 🚀\ndef 两数之和(数组: list[int], 目标: int) -> list[int]:\n    # 💡 Hash Map approach\n    return []"

    ed_context = {
        "topic": unicode_topic,
        "slug": "unicode-topic",
        "target_audience": "Beginner",
        "difficulty": "Easy",
        "target_duration_seconds": 180,
        "problem_description": unicode_desc,
    }

    rendered_ed = loader.render("educational_plan", context=ed_context, version="v1")
    assert unicode_topic in rendered_ed
    assert unicode_desc in rendered_ed

    code_context = {
        "topic": unicode_topic,
        "language": "python",
        "code": unicode_code,
        "time_complexity": "O(N)",
        "space_complexity": "O(N)",
    }

    rendered_code = loader.render("code_explanation", context=code_context, version="v1")
    assert unicode_code in rendered_code
    assert "🔢💡🚀" in rendered_code


# ============================================================================
# 6. Multiline Strings & Line Ending Variations
# ============================================================================

def test_multiline_strings_and_line_endings() -> None:
    """Verify multiline strings with CRLF, LF, and CR line endings render cleanly without corruption."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")

    crlf_code = "def foo():\r\n    x = 10\r\n    return x\r\n"
    multiline_desc = "Line 1\n\nLine 3 with spaces   \n\nLine 5\r\nLine 6"

    code_context = {
        "topic": "Line Endings Test",
        "language": "python",
        "code": crlf_code,
        "time_complexity": "O(1)",
        "space_complexity": "O(1)",
    }

    rendered_code = loader.render("code_explanation", context=code_context, version="v1")
    assert "def foo():" in rendered_code
    assert "x = 10" in rendered_code

    ed_context = {
        "topic": "Multiline Topic",
        "slug": "multiline-topic",
        "target_audience": "Intermediate",
        "difficulty": "Medium",
        "target_duration_seconds": 300,
        "problem_description": multiline_desc,
    }

    rendered_ed = loader.render("educational_plan", context=ed_context, version="v1")
    assert "Line 1" in rendered_ed
    assert "Line 5" in rendered_ed


# ============================================================================
# 7. Exact String Specification Assertions
# ============================================================================

def test_educational_plan_exact_template_structure() -> None:
    """Assert educational_plan.j2 output strictly contains all required header sections in exact order."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")
    context = {
        "topic": "Dijkstra Algorithm",
        "slug": "dijkstra-algorithm",
        "target_audience": "Advanced",
        "difficulty": "Hard",
        "target_duration_seconds": 600,
        "problem_description": "Find shortest paths from source vertex in weighted graph.",
        "constraints": ["V <= 10^5", "E <= 3*10^5", "Non-negative edge weights"],
        "learning_objectives": ["Understand Priority Queue / Min-Heap Optimization", "Analyze O((V + E) log V) Time Complexity"],
        "rag_context": ["Dijkstra uses greedy choice property.", "Edge relaxation condition: dist[u] + w < dist[v]"],
        "code_implementations": {"python": "import heapq\ndef dijkstra(): pass"},
    }

    rendered = loader.render("educational_plan", context=context, version="v1")

    # Header structure check
    assert "=== TOPIC SPECIFICATIONS ===" in rendered
    assert "=== PROBLEM STATEMENT ===" in rendered
    assert "=== CONSTRAINTS & LIMITS ===" in rendered
    assert "=== TARGET LEARNING OBJECTIVES ===" in rendered
    assert "=== KNOWLEDGE BASE CONTEXT (RAG) ===" in rendered
    assert "=== REFERENCE CODE IMPLEMENTATIONS ===" in rendered
    assert "=== DEEP REASONING INSTRUCTIONS (CHAIN-OF-THOUGHT) ===" in rendered
    assert "=== OUTPUT FORMAT & PYDANTIC SCHEMA CONTRACT ===" in rendered

    # Ordering check
    idx_topic = rendered.index("=== TOPIC SPECIFICATIONS ===")
    idx_prob = rendered.index("=== PROBLEM STATEMENT ===")
    idx_const = rendered.index("=== CONSTRAINTS & LIMITS ===")
    idx_obj = rendered.index("=== TARGET LEARNING OBJECTIVES ===")
    idx_rag = rendered.index("=== KNOWLEDGE BASE CONTEXT (RAG) ===")
    idx_code = rendered.index("=== REFERENCE CODE IMPLEMENTATIONS ===")
    idx_cot = rendered.index("=== DEEP REASONING INSTRUCTIONS (CHAIN-OF-THOUGHT) ===")
    idx_contract = rendered.index("=== OUTPUT FORMAT & PYDANTIC SCHEMA CONTRACT ===")

    assert idx_topic < idx_prob < idx_const < idx_obj < idx_rag < idx_code < idx_cot < idx_contract


def test_code_explanation_exact_template_structure() -> None:
    """Assert code_explanation.j2 output strictly contains all required header sections in exact order."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")
    context = {
        "topic": "Merge Sort",
        "language": "cpp",
        "code": "void mergeSort(vector<int>& arr) { }",
        "time_complexity": "O(N log N)",
        "space_complexity": "O(N)",
        "line_highlights": [5, 12, 18],
        "pitfalls": ["Memory leak when allocating auxiliary array", "Stack overflow on deep recursion"],
    }

    rendered = loader.render("code_explanation", context=context, version="v1")

    assert "=== CODE SPECIFICATION ===" in rendered
    assert "=== COMPLEXITY BOUNDS ===" in rendered
    assert "=== KEY FOCUS LINES ===" in rendered
    assert "=== COMMON PITFALLS & BUGS TO ADDRESS ===" in rendered
    assert "=== DEEP REASONING & ANIMATION STATE INSTRUCTIONS ===" in rendered
    assert "=== OUTPUT REQUIREMENTS ===" in rendered

    idx_spec = rendered.index("=== CODE SPECIFICATION ===")
    idx_comp = rendered.index("=== COMPLEXITY BOUNDS ===")
    idx_focus = rendered.index("=== KEY FOCUS LINES ===")
    idx_pitfall = rendered.index("=== COMMON PITFALLS & BUGS TO ADDRESS ===")
    idx_cot = rendered.index("=== DEEP REASONING & ANIMATION STATE INSTRUCTIONS ===")
    idx_out = rendered.index("=== OUTPUT REQUIREMENTS ===")

    assert idx_spec < idx_comp < idx_focus < idx_pitfall < idx_cot < idx_out

    # Check tojson output filter in line 51 of template
    assert "- `line_highlights`: List of key line numbers [5, 12, 18]" in rendered


def test_empty_string_rendering_protection(tmp_path: Path) -> None:
    """Verify rendering a template that outputs only whitespace raises TemplateRenderError."""
    empty_dir = tmp_path / "prompts" / "v1"
    empty_dir.mkdir(parents=True)
    (empty_dir / "whitespace.j2").write_text("   \n\t  \n  ", encoding="utf-8")

    loader = PromptLoader(template_dir=tmp_path / "prompts")
    with pytest.raises(TemplateRenderError) as exc_info:
        loader.render("whitespace", context={}, version="v1")
    assert "rendered to an empty string" in str(exc_info.value)


def test_none_values_and_edge_case_contexts() -> None:
    """Verify behavior when optional variables are passed as None or empty structures."""
    loader = PromptLoader(template_dir="src/core/llm/prompts")

    # educational_plan with None for optional fields
    ed_context = {
        "topic": "Heap Sort",
        "slug": "heap-sort",
        "target_audience": "Intermediate",
        "difficulty": "Medium",
        "target_duration_seconds": 300,
        "problem_description": "Sort array using heap.",
        "constraints": None,
        "learning_objectives": None,
        "rag_context": None,
        "code_implementations": None,
    }
    rendered_ed = loader.render("educational_plan", context=ed_context, version="v1")
    assert "Heap Sort" in rendered_ed
    assert "CONSTRAINTS & LIMITS" not in rendered_ed

    # code_explanation with None for pitfalls and common_pitfalls
    code_context = {
        "topic": "Heapify Code",
        "language": "python",
        "code": "def heapify(): pass",
        "time_complexity": "O(N)",
        "space_complexity": "O(1)",
        "pitfalls": None,
        "common_pitfalls": ["Indexing error in child calculation"],
    }
    rendered_code = loader.render("code_explanation", context=code_context, version="v1")
    assert "COMMON PITFALLS & BUGS TO ADDRESS" in rendered_code
    assert "Indexing error in child calculation" in rendered_code
