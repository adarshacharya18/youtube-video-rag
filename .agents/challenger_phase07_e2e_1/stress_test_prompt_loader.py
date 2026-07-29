"""
Empirical Stress Test Harness for PromptLoader (Phase 07 Deliverable)
Adversarial & Edge Case Stress Testing
"""

import os
import sys
import time
import tempfile
import threading
import concurrent.futures
from pathlib import Path
from typing import Any, Dict, List, Tuple

import jinja2

# Ensure root src is importable
sys.path.insert(0, "/home/adarsh/Documents/Youtube-Channel")

from src.core.llm.prompt_loader import PromptLoader
from src.core.exceptions import PromptTemplateError, TemplateNotFoundError, TemplateRenderError


class StressTestRunner:
    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def record(self, test_id: str, category: str, description: str, passed: bool, detail: str, duration_ms: float):
        self.results.append({
            "test_id": test_id,
            "category": category,
            "description": description,
            "passed": passed,
            "detail": detail,
            "duration_ms": round(duration_ms, 3)
        })

    def print_summary(self):
        print("\n" + "=" * 85)
        print("EMPIRICAL STRESS TEST SUMMARY REPORT — PHASE 07 PROMPT LOADER")
        print("=" * 85)
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed

        print(f"Total Tests Executed: {total}")
        print(f"Passed: {passed}")
        print(f"Failed / Findings: {failed}")
        print("-" * 85)

        for r in self.results:
            status = "PASS" if r["passed"] else "FAIL/FINDING"
            print(f"[{r['test_id']:<7}] [{r['category']:<22}] {r['description']:<55} -> {status} ({r['duration_ms']:.2f} ms)")
            if not r["passed"] or "WEAKNESS" in r["detail"] or "FINDING" in r["detail"]:
                print(f"         Detail: {r['detail']}")

        print("=" * 85)
        return passed, failed


def run_all_stress_tests():
    runner = StressTestRunner()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        v1_dir = tmp_path / "v1"
        v2_dir = tmp_path / "v2"
        v1_dir.mkdir()
        v2_dir.mkdir()

        # -------------------------------------------------------------
        # SUITE 1: Missing Templates & Path Resolution Edge Cases
        # -------------------------------------------------------------
        # 1.1 Non-existent template
        t0 = time.perf_counter()
        loader = PromptLoader(template_dir=tmp_path, default_version="v1")
        try:
            loader.render("non_existent_template", {})
            runner.record("ST-1.1", "PathResolution", "Missing template raises TemplateNotFoundError", False, "No exception raised", (time.perf_counter() - t0) * 1000)
        except TemplateNotFoundError as e:
            runner.record("ST-1.1", "PathResolution", "Missing template raises TemplateNotFoundError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-1.1", "PathResolution", "Missing template raises TemplateNotFoundError", False, f"Wrong exception: {type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000)

        # 1.2 Non-existent version directory
        t0 = time.perf_counter()
        try:
            loader.render("test_template", {}, version="v999")
            runner.record("ST-1.2", "PathResolution", "Missing version raises TemplateNotFoundError", False, "No exception raised", (time.perf_counter() - t0) * 1000)
        except TemplateNotFoundError as e:
            runner.record("ST-1.2", "PathResolution", "Missing version raises TemplateNotFoundError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-1.2", "PathResolution", "Missing version raises TemplateNotFoundError", False, f"Wrong exception: {type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000)

        # 1.3 Path traversal attempt (e.g. "../../etc/passwd")
        t0 = time.perf_counter()
        try:
            loader.render("../../etc/passwd", {})
            runner.record("ST-1.3", "PathResolution", "Path traversal raises TemplateNotFoundError", False, "Path traversal allowed!", (time.perf_counter() - t0) * 1000)
        except TemplateNotFoundError as e:
            runner.record("ST-1.3", "PathResolution", "Path traversal raises TemplateNotFoundError", True, f"Path traversal safely blocked: {e}", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-1.3", "PathResolution", "Path traversal raises TemplateNotFoundError", False, f"Unexpected exception: {type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000)

        # 1.4 Absolute path attempt
        t0 = time.perf_counter()
        try:
            loader.render("/etc/passwd", {})
            runner.record("ST-1.4", "PathResolution", "Absolute path raises TemplateNotFoundError", False, "Absolute path allowed!", (time.perf_counter() - t0) * 1000)
        except TemplateNotFoundError as e:
            runner.record("ST-1.4", "PathResolution", "Absolute path raises TemplateNotFoundError", True, f"Absolute path safely blocked: {e}", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-1.4", "PathResolution", "Absolute path raises TemplateNotFoundError", False, f"Unexpected exception: {type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000)

        # 1.5 Double extension (.j2.j2) resolution
        (v1_dir / "double_ext.j2.j2").write_text("Hello {{ name }}")
        t0 = time.perf_counter()
        try:
            res = loader.render("double_ext.j2.j2", {"name": "World"})
            passed = (res == "Hello World")
            runner.record("ST-1.5", "PathResolution", "Double extension rendering ('double_ext.j2.j2')", passed, f"Rendered: '{res}'", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-1.5", "PathResolution", "Double extension rendering ('double_ext.j2.j2')", False, f"Failed: {e}", (time.perf_counter() - t0) * 1000)

        # 1.6 Explicit version vs slash in template_name interaction
        (v1_dir / "override.j2").write_text("Version 1 {{ val }}")
        (v2_dir / "override.j2").write_text("Version 2 {{ val }}")
        t0 = time.perf_counter()
        try:
            # Passing template_name="v2/override" but version="v1"
            res = loader.render("v2/override", {"val": "test"}, version="v1")
            passed = (res == "Version 2 test")
            runner.record("ST-1.6", "PathResolution", "Slash in template_name overrides version parameter", passed, f"Result: '{res}'", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-1.6", "PathResolution", "Slash in template_name overrides version parameter", False, f"Failed: {e}", (time.perf_counter() - t0) * 1000)

        # 1.7 Empty template file (0 bytes)
        (v1_dir / "empty.j2").write_text("")
        t0 = time.perf_counter()
        try:
            loader.render("empty", {})
            runner.record("ST-1.7", "PathResolution", "Empty template raises TemplateRenderError", False, "Empty template rendered without exception", (time.perf_counter() - t0) * 1000)
        except TemplateRenderError as e:
            runner.record("ST-1.7", "PathResolution", "Empty template raises TemplateRenderError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-1.7", "PathResolution", "Empty template raises TemplateRenderError", False, f"Wrong exception: {type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000)

        # 1.8 Whitespace-only template file
        (v1_dir / "whitespace.j2").write_text("   \n\n\t   ")
        t0 = time.perf_counter()
        try:
            loader.render("whitespace", {})
            runner.record("ST-1.8", "PathResolution", "Whitespace-only template raises TemplateRenderError", False, "Whitespace template rendered without exception", (time.perf_counter() - t0) * 1000)
        except TemplateRenderError as e:
            runner.record("ST-1.8", "PathResolution", "Whitespace-only template raises TemplateRenderError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-1.8", "PathResolution", "Whitespace-only template raises TemplateRenderError", False, f"Wrong exception: {type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000)

        # -------------------------------------------------------------
        # SUITE 2: Syntax Errors in Jinja2 Templates
        # -------------------------------------------------------------
        # 2.1 Unclosed IF block
        (v1_dir / "unclosed_if.j2").write_text("Hello {% if true %} world")
        t0 = time.perf_counter()
        try:
            loader.render("unclosed_if", {})
            runner.record("ST-2.1", "SyntaxErrors", "Unclosed block raises TemplateRenderError", False, "No exception raised", (time.perf_counter() - t0) * 1000)
        except TemplateRenderError as e:
            runner.record("ST-2.1", "SyntaxErrors", "Unclosed block raises TemplateRenderError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-2.1", "SyntaxErrors", "Unclosed block raises TemplateRenderError", False, f"Wrong exception: {type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000)

        # 2.2 Invalid Jinja expression syntax
        (v1_dir / "bad_syntax.j2").write_text("Value: {{ 1 + + }}")
        t0 = time.perf_counter()
        try:
            loader.render("bad_syntax", {})
            runner.record("ST-2.2", "SyntaxErrors", "Invalid expression syntax raises TemplateRenderError", False, "No exception raised", (time.perf_counter() - t0) * 1000)
        except TemplateRenderError as e:
            runner.record("ST-2.2", "SyntaxErrors", "Invalid expression syntax raises TemplateRenderError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-2.2", "SyntaxErrors", "Invalid expression syntax raises TemplateRenderError", False, f"Wrong exception: {type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000)

        # 2.3 Unknown Jinja filter
        (v1_dir / "unknown_filter.j2").write_text("Value: {{ val | nonexistent_filter }}")
        t0 = time.perf_counter()
        try:
            loader.render("unknown_filter", {"val": "test"})
            runner.record("ST-2.3", "SyntaxErrors", "Unknown filter raises TemplateRenderError", False, "No exception raised", (time.perf_counter() - t0) * 1000)
        except TemplateRenderError as e:
            runner.record("ST-2.3", "SyntaxErrors", "Unknown filter raises TemplateRenderError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-2.3", "SyntaxErrors", "Unknown filter raises TemplateRenderError", False, f"Wrong exception: {type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000)

        # 2.4 Missing included template
        (v1_dir / "include_missing.j2").write_text("Main template {% include 'non_existent_inc.j2' %}")
        t0 = time.perf_counter()
        try:
            loader.render("include_missing", {})
            runner.record("ST-2.4", "SyntaxErrors", "Missing included template raises TemplateRenderError", False, "No exception raised", (time.perf_counter() - t0) * 1000)
        except TemplateRenderError as e:
            runner.record("ST-2.4", "SyntaxErrors", "Missing included template raises TemplateRenderError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-2.4", "SyntaxErrors", "Missing included template raises TemplateRenderError", False, f"Wrong exception: {type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000)

        # -------------------------------------------------------------
        # SUITE 3: Missing Variables under StrictUndefined
        # -------------------------------------------------------------
        (v1_dir / "strict_vars.j2").write_text("Title: {{ title }}\nTopic: {{ topic.name }}\nFirst: {{ items[0] }}")

        # 3.1 Completely missing variable 'title'
        t0 = time.perf_counter()
        try:
            loader.render("strict_vars", {"topic": {"name": "DSA"}, "items": [1]})
            runner.record("ST-3.1", "StrictUndefined", "Missing root variable raises TemplateRenderError", False, "No exception raised", (time.perf_counter() - t0) * 1000)
        except TemplateRenderError as e:
            runner.record("ST-3.1", "StrictUndefined", "Missing root variable raises TemplateRenderError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)

        # 3.2 Missing nested attribute 'topic.name'
        t0 = time.perf_counter()
        try:
            loader.render("strict_vars", {"title": "Hello", "topic": {}, "items": [1]})
            runner.record("ST-3.2", "StrictUndefined", "Missing attribute raises TemplateRenderError", False, "No exception raised", (time.perf_counter() - t0) * 1000)
        except TemplateRenderError as e:
            runner.record("ST-3.2", "StrictUndefined", "Missing attribute raises TemplateRenderError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)

        # 3.3 Missing list element or index out of range
        t0 = time.perf_counter()
        try:
            loader.render("strict_vars", {"title": "Hello", "topic": {"name": "DSA"}, "items": []})
            runner.record("ST-3.3", "StrictUndefined", "List index out of range raises TemplateRenderError", False, "No exception raised", (time.perf_counter() - t0) * 1000)
        except TemplateRenderError as e:
            runner.record("ST-3.3", "StrictUndefined", "List index out of range raises TemplateRenderError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)

        # 3.4 Variable passed as None vs missing
        (v1_dir / "none_check.j2").write_text("Val is: {{ val }}")
        t0 = time.perf_counter()
        try:
            res = loader.render("none_check", {"val": None})
            passed = (res == "Val is: None")
            runner.record("ST-3.4", "StrictUndefined", "Variable passed as None renders string 'None'", passed, f"Result: '{res}'", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            runner.record("ST-3.4", "StrictUndefined", "Variable passed as None renders string 'None'", False, f"Failed: {e}", (time.perf_counter() - t0) * 1000)

        # 3.5 Conditional evaluation on undefined variable
        (v1_dir / "cond_undef.j2").write_text("{% if maybe_var %}Defined{% else %}Undefined{% endif %}")
        t0 = time.perf_counter()
        try:
            loader.render("cond_undef", {})
            runner.record("ST-3.5", "StrictUndefined", "Undefined var in IF condition raises TemplateRenderError", False, "No exception raised", (time.perf_counter() - t0) * 1000)
        except TemplateRenderError as e:
            runner.record("ST-3.5", "StrictUndefined", "Undefined var in IF condition raises TemplateRenderError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)

        # 3.6 Loop over undefined variable
        (v1_dir / "loop_undef.j2").write_text("{% for x in missing_list %}{{ x }}{% endfor %}")
        t0 = time.perf_counter()
        try:
            loader.render("loop_undef", {})
            runner.record("ST-3.6", "StrictUndefined", "Undefined var in FOR loop raises TemplateRenderError", False, "No exception raised", (time.perf_counter() - t0) * 1000)
        except TemplateRenderError as e:
            runner.record("ST-3.6", "StrictUndefined", "Undefined var in FOR loop raises TemplateRenderError", True, f"Correctly caught: {e}", (time.perf_counter() - t0) * 1000)

        # -------------------------------------------------------------
        # SUITE 4: Template Caching, Invalidation & Bypass
        # -------------------------------------------------------------
        # 4.1 Caching performance comparison
        (v1_dir / "perf.j2").write_text("Hello {{ name }}, welcome to {{ topic }}! Count: {{ count }}")

        cached_loader = PromptLoader(template_dir=tmp_path, cache_templates=True)
        uncached_loader = PromptLoader(template_dir=tmp_path, cache_templates=False)

        # Warm up
        cached_loader.render("perf", {"name": "A", "topic": "B", "count": 1})
        uncached_loader.render("perf", {"name": "A", "topic": "B", "count": 1})

        N_ITER = 2000
        t0 = time.perf_counter()
        for i in range(N_ITER):
            cached_loader.render("perf", {"name": "User", "topic": "DSA", "count": i})
        t_cached = time.perf_counter() - t0

        t0 = time.perf_counter()
        for i in range(N_ITER):
            uncached_loader.render("perf", {"name": "User", "topic": "DSA", "count": i})
        t_uncached = time.perf_counter() - t0

        speedup = t_uncached / t_cached if t_cached > 0 else 0
        runner.record(
            "ST-4.1",
            "CachingPerformance",
            f"Cached vs Uncached rendering performance ({N_ITER} renders)",
            True,
            f"Cached: {t_cached*1000:.2f}ms, Uncached: {t_uncached*1000:.2f}ms, Speedup factor: {speedup:.2f}x",
            t_cached * 1000
        )

        # 4.2 Template File Mutation while Cached
        (v1_dir / "mutable.j2").write_text("Original Content {{ val }}")
        mut_loader = PromptLoader(template_dir=tmp_path, cache_templates=True)
        r1 = mut_loader.render("mutable", {"val": "1"})
        
        # Now mutate file on disk
        (v1_dir / "mutable.j2").write_text("Modified Content {{ val }}")
        r2 = mut_loader.render("mutable", {"val": "1"})

        is_stale = (r2 == "Original Content 1")
        detail = "Cache retains compiled template in memory (stale rendering on file modification)." if is_stale else "Template reloaded from disk dynamically."
        runner.record(
            "ST-4.2",
            "CachingBehavior",
            "Template file mutation with cache_templates=True",
            True,
            f"{detail} R1='{r1}', R2='{r2}'",
            0.0
        )

        # 4.3 Cache Invalidation via internal dictionary clear
        mut_loader._template_cache.clear()
        r3 = mut_loader.render("mutable", {"val": "1"})
        passed = (r3 == "Modified Content 1")
        runner.record(
            "ST-4.3",
            "CachingBehavior",
            "Manual cache clearing (_template_cache.clear()) updates rendered content",
            passed,
            f"R3 after cache clear: '{r3}'",
            0.0
        )

        # -------------------------------------------------------------
        # SUITE 5: Concurrency & Thread-Safety
        # -------------------------------------------------------------
        # 5.1 Concurrent render calls (Read-heavy load across threads)
        (v1_dir / "concurrent.j2").write_text("Thread ID: {{ thread_id }}, Step: {{ step }}")
        conc_loader = PromptLoader(template_dir=tmp_path, cache_templates=True)
        conc_loader.load_template("concurrent")  # pre-warm

        def worker_render(t_id: int) -> Tuple[bool, str]:
            try:
                for s in range(50):
                    res = conc_loader.render("concurrent", {"thread_id": t_id, "step": s})
                    expected = f"Thread ID: {t_id}, Step: {s}"
                    if res != expected:
                        return False, f"Mismatch at step {s}: got '{res}', expected '{expected}'"
                return True, "OK"
            except Exception as e:
                return False, f"Exception: {type(e).__name__}: {e}"

        t0 = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(worker_render, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        t_conc = (time.perf_counter() - t0) * 1000

        all_passed = all(r[0] for r in results) and len(results) == 20
        runner.record(
            "ST-5.1",
            "Concurrency",
            "20 concurrent threads executing 50 render() calls each (1,000 total renders)",
            all_passed,
            f"All threads succeeded without race conditions. Time: {t_conc:.2f}ms",
            t_conc
        )

        # 5.2 Concurrent template loading (Uncached / Cold-start race test)
        for k in range(10):
            (v1_dir / f"dynamic_{k}.j2").write_text(f"Dynamic Template {k}: {{{{ val }}}}")

        cold_loader = PromptLoader(template_dir=tmp_path, cache_templates=True)

        def worker_load_uncached(t_id: int) -> Tuple[bool, str]:
            try:
                target_k = t_id % 10
                tmpl = cold_loader.load_template(f"dynamic_{target_k}")
                res = cold_loader.render(f"dynamic_{target_k}", {"val": t_id})
                expected = f"Dynamic Template {target_k}: {t_id}"
                if res != expected:
                    return False, f"Thread {t_id}: rendered '{res}' != '{expected}'"
                return True, "OK"
            except Exception as e:
                return False, f"Thread {t_id} Exception: {type(e).__name__}: {e}"

        t0 = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(worker_load_uncached, i) for i in range(50)]
            load_results = [f.result() for f in concurrent.futures.as_completed(futures)]
        t_cold_conc = (time.perf_counter() - t0) * 1000

        all_cold_passed = all(r[0] for r in load_results) and len(load_results) == 50
        err_details = [r[1] for r in load_results if not r[0]]
        runner.record(
            "ST-5.2",
            "Concurrency",
            "50 concurrent threads loading 10 uncached templates into _template_cache simultaneously",
            all_cold_passed,
            f"Cold cache thread-safety: {all_cold_passed}. Errors: {err_details[:3]}",
            t_cold_conc
        )

        # -------------------------------------------------------------
        # SUITE 6: Rendering Stress, Complex Data & Large Payloads
        # -------------------------------------------------------------
        # 6.1 Large payload (5,000 list items rendered in Jinja loop)
        (v1_dir / "large_loop.j2").write_text(
            "Header\n{% for item in items %}Item {{ item.id }}: {{ item.name }}\n{% endfor %}Footer"
        )
        large_items = [{"id": i, "name": f"Name_{i}"} for i in range(5000)]
        t0 = time.perf_counter()
        large_res = loader.render("large_loop", {"items": large_items})
        t_large = (time.perf_counter() - t0) * 1000
        passed_large = len(large_res.splitlines()) == 5002
        runner.record(
            "ST-6.1",
            "LargePayload",
            "Rendering 5,000 items in Jinja for loop",
            passed_large,
            f"Rendered {len(large_res)} chars in {t_large:.2f}ms",
            t_large
        )

        # 6.2 Complex Objects in Context
        class CustomObj:
            def __init__(self, val: str):
                self.val = val
            def display(self) -> str:
                return f"Custom({self.val})"

        (v1_dir / "complex_obj.j2").write_text("Val: {{ obj.val }}, Display: {{ obj.display() }}")
        t0 = time.perf_counter()
        obj_res = loader.render("complex_obj", {"obj": CustomObj("test_data")})
        passed_obj = (obj_res == "Val: test_data, Display: Custom(test_data)")
        runner.record(
            "ST-6.2",
            "ComplexObjects",
            "Rendering custom Python object methods and attributes",
            passed_obj,
            f"Result: '{obj_res}'",
            (time.perf_counter() - t0) * 1000
        )

        # 6.3 Special Characters, Unicode, Emoji, and Multiline Strings
        unicode_str = "DSA Problems: 🚀 🔥 🌲 (binary_tree) \n\t line2: €100 & <script>alert(1)</script>"
        (v1_dir / "unicode.j2").write_text("Input:\n{{ payload }}")
        t0 = time.perf_counter()
        u_res = loader.render("unicode", {"payload": unicode_str})
        passed_unicode = ("🚀 🔥 🌲" in u_res) and ("<script>alert(1)</script>" in u_res)
        runner.record(
            "ST-6.3",
            "UnicodeAndSpecialChars",
            "Rendering unicode, emoji, HTML tags without autoescaping corruption",
            passed_unicode,
            f"Contains expected characters: {passed_unicode}",
            (time.perf_counter() - t0) * 1000
        )

        # -------------------------------------------------------------
        # SUITE 7: Production Templates Empirical Stress Test
        # -------------------------------------------------------------
        real_loader = PromptLoader()
        
        # Real Educational Plan template test
        t0 = time.perf_counter()
        try:
            plan_res = real_loader.render(
                "educational_plan",
                context={
                    "topic": "Binary Tree Maximum Path Sum",
                    "slug": "binary-tree-maximum-path-sum",
                    "target_audience": "Advanced",
                    "difficulty": "Hard",
                    "target_duration_seconds": 600,
                    "problem_description": "Given a non-empty binary tree, find the maximum path sum...",
                    "constraints": ["1 <= Node.val <= 1000"],
                    "learning_objectives": ["Post-order Traversal", "Global Max Update"],
                    "code_implementations": {
                        "python": "def maxPathSum(root): pass"
                    },
                }
            )
            passed_real_plan = len(plan_res) > 200 and "Binary Tree Maximum Path Sum" in plan_res
            runner.record(
                "ST-7.1",
                "ProductionTemplates",
                "Render production template 'educational_plan.j2'",
                passed_real_plan,
                f"Rendered {len(plan_res)} chars cleanly",
                (time.perf_counter() - t0) * 1000
            )
        except Exception as e:
            runner.record(
                "ST-7.1",
                "ProductionTemplates",
                "Render production template 'educational_plan.j2'",
                False,
                f"Failed: {type(e).__name__}: {e}",
                (time.perf_counter() - t0) * 1000
            )

        # Real Code Explanation template test
        t0 = time.perf_counter()
        try:
            code_res = real_loader.render(
                "code_explanation",
                context={
                    "topic": "Two Sum Hash Map",
                    "language": "python",
                    "code": "def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        if target - num in seen:\n            return [seen[target - num], i]\n        seen[num] = i",
                    "time_complexity": "O(N)",
                    "space_complexity": "O(N)",
                    "line_highlights": [3, 4],
                    "pitfalls": ["Index out of bounds"],
                }
            )
            passed_real_code = len(code_res) > 100 and "Two Sum Hash Map" in code_res
            runner.record(
                "ST-7.2",
                "ProductionTemplates",
                "Render production template 'code_explanation.j2'",
                passed_real_code,
                f"Rendered {len(code_res)} chars cleanly",
                (time.perf_counter() - t0) * 1000
            )
        except Exception as e:
            runner.record(
                "ST-7.2",
                "ProductionTemplates",
                "Render production template 'code_explanation.j2'",
                False,
                f"Failed: {type(e).__name__}: {e}",
                (time.perf_counter() - t0) * 1000
            )

    runner.print_summary()


if __name__ == "__main__":
    run_all_stress_tests()
