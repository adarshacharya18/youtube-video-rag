"""
Comprehensive empirical stress test suite for Phase 07 Milestone 2 templates.
Tests educational_plan.j2 and code_explanation.j2 under extreme, edge, and invalid conditions.
"""

import sys
from pathlib import Path
from typing import Any
import pytest

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.llm.prompt_loader import PromptLoader
from src.core.exceptions import TemplateRenderError, TemplateNotFoundError


def run_all_stress_tests():
    loader = PromptLoader()
    results = []

    def record(name: str, passed: bool, detail: str = ""):
        status = "PASSED" if passed else "FAILED"
        print(f"[{status}] {name}" + (f": {detail}" if detail else ""))
        results.append((name, passed, detail))

    print("==================================================")
    print("STARTING EMPIRICAL STRESS TESTS FOR PROMPT LOADER & TEMPLATES")
    print("==================================================")

    # 1. Target Audience Branching (educational_plan.j2)
    for audience in ["Beginner", "Intermediate", "Advanced", "CustomAudience", ""]:
        ctx = {
            "topic": "Graph BFS",
            "slug": "graph-bfs",
            "target_audience": audience,
            "difficulty": "Medium",
            "target_duration_seconds": 450,
            "problem_description": "Breadth first search on a graph.",
        }
        try:
            rendered = loader.render("educational_plan.j2", ctx)
            if audience == "Beginner":
                assert "Use plain-English explanations and relatable real-world analogies" in rendered
            elif audience == "Advanced":
                assert "Emphasize cache locality, memory overhead" in rendered
            else:
                assert "Balance clean visual intuition with precise Big-O" in rendered
            record(f"Target Audience Branching ('{audience}')", True)
        except Exception as e:
            record(f"Target Audience Branching ('{audience}')", False, str(e))

    # 2. Language Branching (code_explanation.j2)
    for lang in ["python", "cpp", "c++", "java", "rust", "Python", "JAVA"]:
        ctx = {
            "topic": "Binary Search",
            "language": lang,
            "code": "int search() { return 0; }",
            "time_complexity": "O(log N)",
            "space_complexity": "O(1)",
        }
        try:
            rendered = loader.render("code_explanation.j2", ctx)
            if lang == "python":
                assert "Language-Specific Nuances (Python)" in rendered
            elif lang in ["cpp", "c++"]:
                assert "Language-Specific Nuances (C++)" in rendered
            elif lang == "java":
                assert "Language-Specific Nuances (Java)" in rendered
            else:
                assert "Language-Specific Nuances:" in rendered
            record(f"Language Branching ('{lang}')", True)
        except Exception as e:
            record(f"Language Branching ('{lang}')", False, str(e))

    # 3. Missing Required Variables (educational_plan.j2)
    required_keys = ["topic", "slug", "target_audience", "difficulty", "target_duration_seconds", "problem_description"]
    base_ctx = {
        "topic": "Merge Sort",
        "slug": "merge-sort",
        "target_audience": "Intermediate",
        "difficulty": "Medium",
        "target_duration_seconds": 500,
        "problem_description": "Sort an array using divide and conquer.",
    }
    for key in required_keys:
        bad_ctx = {k: v for k, v in base_ctx.items() if k != key}
        try:
            loader.render("educational_plan.j2", bad_ctx)
            record(f"Missing Required Key in educational_plan ('{key}')", False, "Should have raised TemplateRenderError")
        except TemplateRenderError as e:
            assert f"Missing required context variable" in str(e) or key in str(e)
            record(f"Missing Required Key in educational_plan ('{key}')", True, f"Correctly caught: {e}")
        except Exception as e:
            record(f"Missing Required Key in educational_plan ('{key}')", False, f"Unexpected error type: {type(e)} {e}")

    # 4. Missing Required Variables (code_explanation.j2)
    code_req_keys = ["topic", "language", "code", "time_complexity", "space_complexity"]
    base_code_ctx = {
        "topic": "Merge Sort",
        "language": "python",
        "code": "def sort(): pass",
        "time_complexity": "O(N log N)",
        "space_complexity": "O(N)",
    }
    for key in code_req_keys:
        bad_ctx = {k: v for k, v in base_code_ctx.items() if k != key}
        try:
            loader.render("code_explanation.j2", bad_ctx)
            record(f"Missing Required Key in code_explanation ('{key}')", False, "Should have raised TemplateRenderError")
        except TemplateRenderError as e:
            assert f"Missing required context variable" in str(e) or key in str(e)
            record(f"Missing Required Key in code_explanation ('{key}')", True, f"Correctly caught: {e}")
        except Exception as e:
            record(f"Missing Required Key in code_explanation ('{key}')", False, f"Unexpected error type: {type(e)} {e}")

    # 5. Optional Variables Behavior & Edge Cases (educational_plan.j2)
    # Check None, [], {}, empty strings
    for opt_val in [None, [], {}]:
        ctx = {
            **base_ctx,
            "constraints": opt_val,
            "learning_objectives": opt_val,
            "rag_context": opt_val,
            "code_implementations": opt_val if isinstance(opt_val, dict) else {},
        }
        try:
            rendered = loader.render("educational_plan.j2", ctx)
            # Ensure optional sections are omitted when empty/None
            assert "=== CONSTRAINTS & LIMITS ===" not in rendered
            assert "=== TARGET LEARNING OBJECTIVES ===" not in rendered
            assert "=== KNOWLEDGE BASE CONTEXT (RAG) ===" not in rendered
            assert "=== REFERENCE CODE IMPLEMENTATIONS ===" not in rendered
            record(f"Educational Plan Optional Keys with value ({type(opt_val).__name__})", True)
        except Exception as e:
            record(f"Educational Plan Optional Keys with value ({type(opt_val).__name__})", False, str(e))

    # 6. Optional Variables Behavior (code_explanation.j2)
    for opt_val in [None, []]:
        ctx = {
            **base_code_ctx,
            "line_highlights": opt_val,
            "pitfalls": opt_val,
            "common_pitfalls": opt_val,
        }
        try:
            rendered = loader.render("code_explanation.j2", ctx)
            assert "=== KEY FOCUS LINES ===" not in rendered
            assert "=== COMMON PITFALLS & BUGS TO ADDRESS ===" not in rendered
            assert "- line_highlights: List of key line numbers []" in rendered
            record(f"Code Explanation Optional Keys with value ({type(opt_val).__name__})", True)
        except Exception as e:
            record(f"Code Explanation Optional Keys with value ({type(opt_val).__name__})", False, str(e))

    # 7. Complex Special Characters & Escaping
    complex_code = """#include <iostream>
#include <vector>
#include <map>

// Special chars: {{ foo }} {% if bar %} {# comment #}
/* Multi-line comment with backticks: `code` and quotes: "hello" 'world' */
template <typename T>
std::vector<std::pair<int, T>> solve(const std::string& input = "a < b && c > d") {
    if (input.empty()) return {};
    return {{1, T{}}};
}
"""
    complex_desc = "Problem statement with <vector<int>>, & reference, \"quotes\", 'singles', \n\n embedded newlines and {{ Jinja-like syntax }}."
    ctx_special = {
        "topic": "Complex Template <T> & Special Chars",
        "slug": "complex-template-t",
        "target_audience": "Advanced",
        "difficulty": "Hard",
        "target_duration_seconds": 900,
        "problem_description": complex_desc,
        "constraints": ["O(N) time where N <= 10^5", "Memory <= 256MB", "No std::allocator<void>"],
        "learning_objectives": ["Mastering std::vector<std::pair<int, int>>", "Handling & references"],
        "rag_context": ["C++20 template meta-programming notes: `template <typename T>`."],
        "code_implementations": {"cpp": complex_code},
    }
    try:
        rendered_plan = loader.render("educational_plan.j2", ctx_special)
        assert complex_code in rendered_plan
        assert complex_desc in rendered_plan
        record("Special Characters & Escaping (educational_plan.j2)", True)
    except Exception as e:
        record("Special Characters & Escaping (educational_plan.j2)", False, str(e))

    ctx_code_special = {
        "topic": "Complex Code Walkthrough",
        "language": "cpp",
        "code": complex_code,
        "time_complexity": "O(N log N)",
        "space_complexity": "O(N)",
        "line_highlights": [5, 8, 10],
        "pitfalls": ["Dangling & reference", "Invalid iterator arithmetic"],
    }
    try:
        rendered_code = loader.render("code_explanation.j2", ctx_code_special)
        assert complex_code in rendered_code
        assert "Dangling & reference" in rendered_code
        record("Special Characters & Escaping (code_explanation.j2)", True)
    except Exception as e:
        record("Special Characters & Escaping (code_explanation.j2)", False, str(e))

    # 8. Large Context Stress Test
    large_rag = [f"RAG Chunk #{i}: " + ("Detailed algorithmic explanation " * 50) for i in range(1, 31)]
    large_objectives = [f"Objective #{i}: Complete understanding of sub-problem {i}" for i in range(1, 25)]
    large_constraints = [f"Constraint #{i}: Parameter X_{i} must satisfy 0 <= X_{i} <= 10^{i}" for i in range(1, 20)]
    large_code_map = {
        f"lang_{i}": f"// Code for implementation in lang_{i}\nvoid run_{i}() {{ std::cout << {i} << std::endl; }}"
        for i in range(1, 10)
    }

    ctx_large = {
        "topic": "Massive Graph Neural Network Optimization",
        "slug": "gnn-optimization",
        "target_audience": "Advanced",
        "difficulty": "Hard",
        "target_duration_seconds": 1800,
        "problem_description": "Massive scale parallel execution on dynamic graphs.",
        "constraints": large_constraints,
        "learning_objectives": large_objectives,
        "rag_context": large_rag,
        "code_implementations": large_code_map,
    }
    try:
        rendered_large = loader.render("educational_plan.j2", ctx_large)
        assert "RAG Chunk #30:" in rendered_large
        assert "Objective #24:" in rendered_large
        assert "Constraint #19:" in rendered_large
        assert "Language: lang_9" in rendered_large
        print(f"Large context rendered size: {len(rendered_large)} chars")
        record("Large Context Stress Test (educational_plan.j2)", True)
    except Exception as e:
        record("Large Context Stress Test (educational_plan.j2)", False, str(e))

    # 9. Non-ASCII / Unicode Characters Test
    ctx_unicode = {
        "topic": "Dijkstra's Algorithm — 最短経路アルゴリズム Θ(E + V log V)",
        "slug": "dijkstras-algorithm-unicode",
        "target_audience": "Intermediate",
        "difficulty": "Medium",
        "target_duration_seconds": 600,
        "problem_description": "Find single-source shortest paths in a graph with non-negative edge weights w(u, v) ≥ 0.",
        "constraints": ["Edge weights w(u, v) ∈ [0, 10^9]", "Graph has |V| ≤ 10^5 nodes & |E| ≤ 3×10^5 edges"],
        "learning_objectives": ["Priority queue priority mutation (decrease-key)", "Complexity: O((V + E) log V)"],
        "rag_context": ["Graph notation: G = (V, E, w). Fibonacci heap yields O(E + V log V). 🚀"],
        "code_implementations": {
            "python": "# 🚀 Python implementation with heapq\nimport heapq\n\ndef dijkstra(adj, start):\n    dist = {start: 0}\n    pq = [(0, start)]\n    return dist\n"
        },
    }
    try:
        rendered_unicode = loader.render("educational_plan.j2", ctx_unicode)
        assert "最短経路アルゴリズム" in rendered_unicode
        assert "w(u, v) ≥ 0" in rendered_unicode
        assert "🚀" in rendered_unicode
        record("Unicode & Mathematical Symbols Stress Test (educational_plan.j2)", True)
    except Exception as e:
        record("Unicode & Mathematical Symbols Stress Test (educational_plan.j2)", False, str(e))

    # 10. Cache behavior & invalidation checks
    try:
        l1 = PromptLoader(cache_templates=True)
        t1 = l1.load_template("educational_plan.j2")
        t2 = l1.load_template("educational_plan.j2")
        assert t1 is t2, "Cached templates should be identical instance"

        l2 = PromptLoader(cache_templates=False)
        t3 = l2.load_template("educational_plan.j2")
        t4 = l2.load_template("educational_plan.j2")
        assert t3 is not t4, "Uncached templates should produce new instances"
        record("Template Cache Mechanics", True)
    except Exception as e:
        record("Template Cache Mechanics", False, str(e))

    print("==================================================")
    passed_count = sum(1 for _, p, _ in results if p)
    total_count = len(results)
    print(f"STRESS TEST SUMMARY: {passed_count}/{total_count} PASSED")
    print("==================================================")

    if passed_count < total_count:
        sys.exit(1)


if __name__ == "__main__":
    run_all_stress_tests()
