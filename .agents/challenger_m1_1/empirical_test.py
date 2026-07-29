"""
Empirical Challenge Script for PromptLoader in Phase 07 M1.
Executes detailed edge cases and stress tests, logging results to stdout and returning status code.
"""

import sys
import os
import shutil
import tempfile
import threading
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.llm.prompt_loader import PromptLoader
from src.core.exceptions import (
    PipelineError,
    FatalError,
    PromptTemplateError,
    TemplateNotFoundError,
    TemplateRenderError,
)

class ChallengeRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
        self.temp_dir = Path(tempfile.mkdtemp())
        self._setup_fixtures()

    def _setup_fixtures(self):
        self.v1_dir = self.temp_dir / "v1"
        self.v2_dir = self.temp_dir / "v2"
        self.v1_dir.mkdir(parents=True, exist_ok=True)
        self.v2_dir.mkdir(parents=True, exist_ok=True)

        # Fixtures
        (self.v1_dir / "greeting.j2").write_text("Hello {{ name }}!")
        (self.v1_dir / "complex.j2").write_text(
            "{% macro format_item(item) %}"
            "{{ item.name | upper }}: {{ item.tags | join(', ') }}"
            "{% endmacro %}\n"
            "{% for item in items %}\n"
            "- {{ format_item(item) }} ({% if item.active %}Active{% else %}Inactive{% endif %})\n"
            "{% endfor %}"
        )
        (self.v1_dir / "empty.j2").write_text("  \n \t ")
        (self.v1_dir / "syntax_error.j2").write_text("Bad template {% if name %}")
        (self.v1_dir / "readme.txt").write_text("Ignore this file")

        (self.v2_dir / "greeting.j2").write_text("Welcome to v2, {{ name }}!")

    def cleanup(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def record(self, test_name: str, status: bool, details: str = ""):
        if status:
            self.passed += 1
            print(f"[PASS] {test_name}")
            self.results.append((test_name, "PASS", details))
        else:
            self.failed += 1
            print(f"[FAIL] {test_name}: {details}")
            self.results.append((test_name, "FAIL", details))

    def run_all(self):
        print("==================================================")
        print("   EMPIRICAL CHALLENGE SUITE FOR PROMPTLOADER     ")
        print("==================================================")

        self.test_01_exception_hierarchy()
        self.test_02_missing_template_file()
        self.test_03_missing_version_directory()
        self.test_04_missing_context_variable()
        self.test_05_missing_nested_attribute()
        self.test_06_syntax_error_load()
        self.test_07_syntax_error_render()
        self.test_08_empty_template_render()
        self.test_09_complex_jinja_control_flow()
        self.test_10_kwargs_context_precedence()
        self.test_11_version_override()
        self.test_12_caching_enabled()
        self.test_13_caching_disabled_leak_defect()
        self.test_14_custom_template_dir_types()
        self.test_15_list_templates()
        self.test_16_list_versions()
        self.test_17_path_traversal()
        self.test_18_multithreaded_concurrency()

        print("\n==================================================")
        print(f"RESULTS: Total: {self.passed + self.failed} | Passed: {self.passed} | Failed: {self.failed}")
        print("==================================================")
        return self.failed == 0

    # -----------------------------------------------------------------
    # Test Cases
    # -----------------------------------------------------------------
    def test_01_exception_hierarchy(self):
        try:
            assert issubclass(PromptTemplateError, FatalError)
            assert issubclass(PromptTemplateError, PipelineError)
            assert issubclass(TemplateNotFoundError, PromptTemplateError)
            assert issubclass(TemplateRenderError, PromptTemplateError)
            self.record("Test 01: Exception Hierarchy", True, "All exceptions inherit from FatalError / PromptTemplateError")
        except Exception as e:
            self.record("Test 01: Exception Hierarchy", False, str(e))

    def test_02_missing_template_file(self):
        loader = PromptLoader(template_dir=self.temp_dir)
        try:
            loader.load_template("non_existent_file")
            self.record("Test 02: Missing Template File", False, "Failed to raise TemplateNotFoundError")
        except TemplateNotFoundError as e:
            msg = str(e)
            assert "non_existent_file" in msg
            assert "v1" in msg
            self.record("Test 02: Missing Template File", True, f"Raised TemplateNotFoundError correctly: '{msg}'")
        except Exception as e:
            self.record("Test 02: Missing Template File", False, f"Wrong exception raised: {type(e).__name__}: {e}")

    def test_03_missing_version_directory(self):
        loader = PromptLoader(template_dir=self.temp_dir)
        try:
            loader.load_template("greeting", version="v999")
            self.record("Test 03: Missing Version Dir", False, "Failed to raise TemplateNotFoundError")
        except TemplateNotFoundError as e:
            msg = str(e)
            assert "v999" in msg
            self.record("Test 03: Missing Version Dir", True, f"Raised TemplateNotFoundError correctly: '{msg}'")
        except Exception as e:
            self.record("Test 03: Missing Version Dir", False, f"Wrong exception raised: {type(e).__name__}: {e}")

    def test_04_missing_context_variable(self):
        loader = PromptLoader(template_dir=self.temp_dir)
        try:
            loader.render("greeting", context={})
            self.record("Test 04: Missing Context Variable", False, "Failed to raise TemplateRenderError")
        except TemplateRenderError as e:
            msg = str(e)
            assert "Missing required context variable" in msg
            self.record("Test 04: Missing Context Variable", True, f"Raised TemplateRenderError under StrictUndefined: '{msg}'")
        except Exception as e:
            self.record("Test 04: Missing Context Variable", False, f"Wrong exception raised: {type(e).__name__}: {e}")

    def test_05_missing_nested_attribute(self):
        loader = PromptLoader(template_dir=self.temp_dir)
        try:
            loader.render("complex", context={"items": [{"name": "item1"}]}) # missing tags
            self.record("Test 05: Missing Nested Attribute", False, "Failed to raise TemplateRenderError")
        except TemplateRenderError as e:
            msg = str(e)
            assert "attribute 'tags'" in msg
            self.record("Test 05: Missing Nested Attribute", True, f"Raised TemplateRenderError: '{msg}'")
        except Exception as e:
            self.record("Test 05: Missing Nested Attribute", False, f"Wrong exception raised: {type(e).__name__}: {e}")

    def test_06_syntax_error_load(self):
        loader = PromptLoader(template_dir=self.temp_dir)
        try:
            loader.load_template("syntax_error")
            self.record("Test 06: Syntax Error on Load", False, "Failed to raise TemplateRenderError")
        except TemplateRenderError as e:
            msg = str(e)
            assert "Syntax error" in msg
            self.record("Test 06: Syntax Error on Load", True, f"Raised TemplateRenderError: '{msg}'")
        except Exception as e:
            self.record("Test 06: Syntax Error on Load", False, f"Wrong exception raised: {type(e).__name__}: {e}")

    def test_07_syntax_error_render(self):
        loader = PromptLoader(template_dir=self.temp_dir)
        try:
            loader.render("syntax_error", context={"name": "Alice"})
            self.record("Test 07: Syntax Error on Render", False, "Failed to raise TemplateRenderError")
        except TemplateRenderError as e:
            msg = str(e)
            assert "Syntax error" in msg
            self.record("Test 07: Syntax Error on Render", True, f"Raised TemplateRenderError: '{msg}'")
        except Exception as e:
            self.record("Test 07: Syntax Error on Render", False, f"Wrong exception raised: {type(e).__name__}: {e}")

    def test_08_empty_template_render(self):
        loader = PromptLoader(template_dir=self.temp_dir)
        try:
            loader.render("empty")
            self.record("Test 08: Empty Template Render", False, "Failed to raise TemplateRenderError")
        except TemplateRenderError as e:
            msg = str(e)
            assert "rendered to an empty string" in msg
            self.record("Test 08: Empty Template Render", True, f"Raised TemplateRenderError: '{msg}'")
        except Exception as e:
            self.record("Test 08: Empty Template Render", False, f"Wrong exception raised: {type(e).__name__}: {e}")

    def test_09_complex_jinja_control_flow(self):
        loader = PromptLoader(template_dir=self.temp_dir)
        context = {
            "items": [
                {"name": "dsa_array", "tags": ["array", "dsa"], "active": True},
                {"name": "dsa_tree", "tags": ["tree", "graph"], "active": False},
            ]
        }
        try:
            rendered = loader.render("complex", context=context)
            assert "DSA_ARRAY: array, dsa (Active)" in rendered
            assert "DSA_TREE: tree, graph (Inactive)" in rendered
            self.record("Test 09: Complex Control Flow & Macros", True, f"Rendered successfully:\n{rendered}")
        except Exception as e:
            self.record("Test 09: Complex Control Flow & Macros", False, f"Failed rendering complex template: {e}")

    def test_10_kwargs_context_precedence(self):
        loader = PromptLoader(template_dir=self.temp_dir)
        try:
            res = loader.render("greeting", context={"name": "ContextName"}, name="KwargName")
            assert res == "Hello KwargName!"
            self.record("Test 10: Kwargs Context Precedence", True, "Kwargs correctly override context dictionary")
        except Exception as e:
            self.record("Test 10: Kwargs Context Precedence", False, str(e))

    def test_11_version_override(self):
        loader = PromptLoader(template_dir=self.temp_dir, default_version="v1")
        try:
            res_v1 = loader.render("greeting", name="User")
            res_v2 = loader.render("greeting", name="User", version="v2")
            assert res_v1 == "Hello User!"
            assert res_v2 == "Welcome to v2, User!"
            self.record("Test 11: Version Override", True, f"v1: '{res_v1}' | v2: '{res_v2}'")
        except Exception as e:
            self.record("Test 11: Version Override", False, str(e))

    def test_12_caching_enabled(self):
        loader = PromptLoader(template_dir=self.temp_dir, cache_templates=True)
        try:
            t1 = loader.load_template("greeting")
            t2 = loader.load_template("greeting")
            assert t1 is t2
            assert len(loader._template_cache) == 1
            self.record("Test 12: Caching Enabled", True, "Template cached in _template_cache and identity preserved")
        except Exception as e:
            self.record("Test 12: Caching Enabled", False, str(e))

    def test_13_caching_disabled_leak_defect(self):
        loader = PromptLoader(template_dir=self.temp_dir, cache_templates=False)
        try:
            t1 = loader.load_template("greeting")
            t2 = loader.load_template("greeting")
            # PromptLoader's _template_cache is empty
            assert len(loader._template_cache) == 0

            # Check Jinja Environment's internal cache
            jinja_cache_active = loader.env.cache is not None
            if jinja_cache_active:
                self.record(
                    "Test 13: Caching Disabled (Defect Check)",
                    False,
                    "DEFECT FOUND: Setting cache_templates=False bypasses PromptLoader._template_cache but leaves Jinja2 Environment cache active (cache_size was not set to 0).",
                )
            else:
                self.record("Test 13: Caching Disabled", True, "Jinja2 Environment cache is properly disabled.")
        except Exception as e:
            self.record("Test 13: Caching Disabled", False, str(e))

    def test_14_custom_template_dir_types(self):
        try:
            loader_str = PromptLoader(template_dir=str(self.temp_dir))
            loader_path = PromptLoader(template_dir=self.temp_dir)
            assert loader_str.render("greeting", name="Str") == "Hello Str!"
            assert loader_path.render("greeting", name="Path") == "Hello Path!"
            self.record("Test 14: Custom template_dir Types", True, "Supports str and Path inputs")
        except Exception as e:
            self.record("Test 14: Custom template_dir Types", False, str(e))

    def test_15_list_templates(self):
        loader = PromptLoader(template_dir=self.temp_dir)
        try:
            templates = loader.list_templates("v1")
            expected = ["complex.j2", "empty.j2", "greeting.j2", "syntax_error.j2"]
            assert templates == expected
            assert "readme.txt" not in templates
            self.record("Test 15: List Templates", True, f"Listed templates: {templates}")
        except Exception as e:
            self.record("Test 15: List Templates", False, str(e))

    def test_16_list_versions(self):
        (self.temp_dir / ".git").mkdir(exist_ok=True)
        loader = PromptLoader(template_dir=self.temp_dir)
        try:
            versions = loader.list_versions()
            assert versions == ["v1", "v2"]
            assert ".git" not in versions
            self.record("Test 16: List Versions", True, f"Listed versions: {versions}")
        except Exception as e:
            self.record("Test 16: List Versions", False, str(e))

    def test_17_path_traversal(self):
        loader = PromptLoader(template_dir=self.temp_dir)
        try:
            loader.load_template("../outside_file")
            self.record("Test 17: Path Traversal Prevention", False, "Failed to block path traversal")
        except TemplateNotFoundError:
            self.record("Test 17: Path Traversal Prevention", True, "FileSystemLoader correctly blocked path traversal attempt")
        except Exception as e:
            self.record("Test 17: Path Traversal Prevention", False, f"Unexpected exception: {type(e).__name__}: {e}")

    def test_18_multithreaded_concurrency(self):
        loader = PromptLoader(template_dir=self.temp_dir, cache_templates=True)
        errors = []

        def worker(tid):
            try:
                for i in range(30):
                    res = loader.render("greeting", name=f"Thread-{tid}-{i}")
                    assert res == f"Hello Thread-{tid}-{i}!"
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            self.record("Test 18: Multithreaded Concurrency", False, f"Thread errors: {errors}")
        else:
            self.record("Test 18: Multithreaded Concurrency", True, "10 threads executed 300 render calls with 0 errors")

if __name__ == "__main__":
    runner = ChallengeRunner()
    success = runner.run_all()
    runner.cleanup()
    sys.exit(0 if success else 1)
