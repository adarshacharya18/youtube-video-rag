"""
Empirical Challenge & Stress Test Suite for PromptLoader (Phase 07 M1)
"""

import sys
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
import unittest

# Ensure project root is in sys.path
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

class TestPromptLoaderEmpirical(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.v1_dir = self.temp_dir / "v1"
        self.v2_dir = self.temp_dir / "v2"
        self.v1_dir.mkdir(parents=True, exist_ok=True)
        self.v2_dir.mkdir(parents=True, exist_ok=True)

        # Create basic v1 templates
        (self.v1_dir / "simple.j2").write_text("Hello {{ name }}!")
        (self.v1_dir / "complex.j2").write_text(
            "{% for item in items %}\n"
            "Item {{ loop.index }}: {{ item.name | upper }} - status: {% if item.active %}ACTIVE{% else %}INACTIVE{% endif %}\n"
            "{% endfor %}"
        )
        (self.v1_dir / "empty.j2").write_text("   \n\t  ")
        (self.v1_dir / "syntax_error.j2").write_text("Hello {% if name %}{{ name }}")
        (self.v1_dir / "non_j2_file.txt").write_text("Ignore me")

        # Create basic v2 template
        (self.v2_dir / "simple.j2").write_text("Welcome v2 {{ name }}!")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # 1. Exception Hierarchy & Type Verification
    # -------------------------------------------------------------
    def test_exception_inheritance(self):
        """Verify exception class hierarchy matching requirements."""
        self.assertTrue(issubclass(PromptTemplateError, FatalError))
        self.assertTrue(issubclass(PromptTemplateError, PipelineError))
        self.assertTrue(issubclass(TemplateNotFoundError, PromptTemplateError))
        self.assertTrue(issubclass(TemplateRenderError, PromptTemplateError))

    # -------------------------------------------------------------
    # 2. Missing Templates & Versions
    # -------------------------------------------------------------
    def test_missing_template_file(self):
        """Verify TemplateNotFoundError raised when template file does not exist."""
        loader = PromptLoader(template_dir=self.temp_dir, default_version="v1")
        with self.assertRaises(TemplateNotFoundError) as ctx:
            loader.load_template("non_existent_template")
        self.assertIn("non_existent_template", str(ctx.exception))
        self.assertIn("v1", str(ctx.exception))

    def test_missing_version_directory(self):
        """Verify TemplateNotFoundError raised when requested version dir does not exist."""
        loader = PromptLoader(template_dir=self.temp_dir)
        with self.assertRaises(TemplateNotFoundError) as ctx:
            loader.load_template("simple", version="v999")
        self.assertIn("v999", str(ctx.exception))

    def test_render_missing_template(self):
        """Verify render raises TemplateNotFoundError when template is missing."""
        loader = PromptLoader(template_dir=self.temp_dir)
        with self.assertRaises(TemplateNotFoundError):
            loader.render("missing_template", context={"name": "test"})

    # -------------------------------------------------------------
    # 3. Context Variables & Syntax Errors (Strict Undefined)
    # -------------------------------------------------------------
    def test_missing_context_variable(self):
        """Verify TemplateRenderError raised when context variable is missing (StrictUndefined)."""
        loader = PromptLoader(template_dir=self.temp_dir)
        with self.assertRaises(TemplateRenderError) as ctx:
            loader.render("simple", context={})
        self.assertIn("Missing required context variable", str(ctx.exception))

    def test_missing_nested_attribute(self):
        """Verify TemplateRenderError raised when nested attribute is missing."""
        loader = PromptLoader(template_dir=self.temp_dir)
        with self.assertRaises(TemplateRenderError) as ctx:
            loader.render("complex", context={"items": [{"missing_name": "foo"}]})
        self.assertIn("Missing required context variable", str(ctx.exception))
        self.assertIn("attribute 'name'", str(ctx.exception))

    def test_invalid_jinja_syntax_on_load(self):
        """Verify TemplateRenderError raised on syntax error during load_template."""
        loader = PromptLoader(template_dir=self.temp_dir)
        with self.assertRaises(TemplateRenderError) as ctx:
            loader.load_template("syntax_error")
        self.assertIn("Syntax error", str(ctx.exception))

    def test_invalid_jinja_syntax_on_render(self):
        """Verify TemplateRenderError raised on syntax error during render."""
        loader = PromptLoader(template_dir=self.temp_dir)
        with self.assertRaises(TemplateRenderError) as ctx:
            loader.render("syntax_error", context={"name": "Alice"})
        self.assertIn("Syntax error", str(ctx.exception))

    def test_empty_template_rendering(self):
        """Verify TemplateRenderError raised when rendered template is empty/whitespace."""
        loader = PromptLoader(template_dir=self.temp_dir)
        with self.assertRaises(TemplateRenderError) as ctx:
            loader.render("empty")
        self.assertIn("rendered to an empty string", str(ctx.exception))

    # -------------------------------------------------------------
    # 4. Complex Jinja Control Flow & Filters
    # -------------------------------------------------------------
    def test_complex_rendering(self):
        """Verify complex Jinja logic (loops, conditionals, filters)."""
        loader = PromptLoader(template_dir=self.temp_dir)
        context = {
            "items": [
                {"name": "alpha", "active": True},
                {"name": "beta", "active": False},
            ]
        }
        output = loader.render("complex", context=context)
        expected = "Item 1: ALPHA - status: ACTIVE\nItem 2: BETA - status: INACTIVE"
        self.assertEqual(output, expected)

    def test_rendering_with_kwargs_and_context_merge(self):
        """Verify rendering supports dict context, kwargs, and kwargs overriding context dict."""
        loader = PromptLoader(template_dir=self.temp_dir)
        res1 = loader.render("simple", context={"name": "Alice"})
        self.assertEqual(res1, "Hello Alice!")

        res2 = loader.render("simple", name="Bob")
        self.assertEqual(res2, "Hello Bob!")

        # kwargs overrides context dict
        res3 = loader.render("simple", context={"name": "Alice"}, name="Charlie")
        self.assertEqual(res3, "Hello Charlie!")

    def test_version_override_in_render(self):
        """Verify version argument in render loads correct version template."""
        loader = PromptLoader(template_dir=self.temp_dir, default_version="v1")
        res_v1 = loader.render("simple", name="World")
        res_v2 = loader.render("simple", name="World", version="v2")

        self.assertEqual(res_v1, "Hello World!")
        self.assertEqual(res_v2, "Welcome v2 World!")

    # -------------------------------------------------------------
    # 5. Caching & Custom template_dir Behavior
    # -------------------------------------------------------------
    def test_caching_enabled(self):
        """Verify template cache returns identical object in _template_cache when cache_templates=True."""
        loader = PromptLoader(template_dir=self.temp_dir, cache_templates=True)
        t1 = loader.load_template("simple")
        t2 = loader.load_template("simple")
        self.assertIs(t1, t2)
        self.assertEqual(len(loader._template_cache), 1)

    def test_caching_disabled_prompt_loader_cache_bypass(self):
        """
        Verify that setting cache_templates=False bypasses PromptLoader's _template_cache,
        though Jinja2 internal LRUCache still retains objects unless cache_size=0 is passed to Environment.
        """
        loader = PromptLoader(template_dir=self.temp_dir, cache_templates=False)
        t1 = loader.load_template("simple")
        t2 = loader.load_template("simple")
        # _template_cache is empty because cache_templates is False
        self.assertEqual(len(loader._template_cache), 0)

    def test_caching_disabled_jinja_env_leak_defect(self):
        """
        EMPIRICAL BUG BUG-01:
        Verify whether cache_templates=False or enable_cache=False fails to disable Jinja2's
        internal Environment cache because cache_size is not configured on Environment.
        """
        loader = PromptLoader(template_dir=self.temp_dir, cache_templates=False)
        self.assertIsNotNone(loader.env.cache, "Jinja2 Environment cache is NOT None when cache_templates=False!")

    def test_enable_cache_alias(self):
        """Verify enable_cache keyword argument acts as alias for cache_templates."""
        loader = PromptLoader(template_dir=self.temp_dir, enable_cache=False)
        self.assertFalse(loader.cache_templates)
        self.assertFalse(loader.enable_cache)
        self.assertEqual(len(loader._template_cache), 0)

    def test_custom_template_dir_as_str_and_path(self):
        """Verify template_dir accepts both str and Path."""
        loader_str = PromptLoader(template_dir=str(self.temp_dir))
        self.assertIsInstance(loader_str.template_dir, Path)
        self.assertEqual(loader_str.render("simple", name="Str"), "Hello Str!")

        loader_path = PromptLoader(template_dir=self.temp_dir)
        self.assertEqual(loader_path.render("simple", name="Path"), "Hello Path!")

    # -------------------------------------------------------------
    # 6. Listing Templates & Versions
    # -------------------------------------------------------------
    def test_list_templates(self):
        """Verify list_templates returns sorted list of .j2 filenames, ignoring non-.j2."""
        loader = PromptLoader(template_dir=self.temp_dir)
        templates_v1 = loader.list_templates("v1")
        self.assertEqual(templates_v1, ["complex.j2", "empty.j2", "simple.j2", "syntax_error.j2"])
        self.assertNotIn("non_j2_file.txt", templates_v1)

        templates_non_existent = loader.list_templates("v999")
        self.assertEqual(templates_non_existent, [])

    def test_list_versions(self):
        """Verify list_versions lists directories and ignores hidden dirs."""
        (self.temp_dir / ".hidden_dir").mkdir(exist_ok=True)
        loader = PromptLoader(template_dir=self.temp_dir)
        versions = loader.list_versions()
        self.assertEqual(versions, ["v1", "v2"])

    def test_list_versions_non_existent_dir(self):
        """Verify list_versions handles non-existent template directory gracefully."""
        loader = PromptLoader(template_dir=self.temp_dir / "does_not_exist")
        self.assertEqual(loader.list_versions(), [])
        self.assertEqual(loader.list_templates("v1"), [])

    # -------------------------------------------------------------
    # 7. Path Traversal & Slash Resolution
    # -------------------------------------------------------------
    def test_template_name_with_j2_extension(self):
        """Verify specifying .j2 in template_name works seamlessly."""
        loader = PromptLoader(template_dir=self.temp_dir)
        res = loader.render("simple.j2", name="J2Ext")
        self.assertEqual(res, "Hello J2Ext!")

    def test_template_name_with_slash(self):
        """Verify template_name with slash bypasses version prefixing."""
        loader = PromptLoader(template_dir=self.temp_dir)
        res = loader.render("v2/simple", name="Slash")
        self.assertEqual(res, "Welcome v2 Slash!")

    def test_path_traversal_prevention(self):
        """Verify Jinja2 FileSystemLoader blocks relative path traversal outside template_dir."""
        loader = PromptLoader(template_dir=self.temp_dir)
        with self.assertRaises(TemplateNotFoundError):
            loader.load_template("../outside_template")

    # -------------------------------------------------------------
    # 8. Thread Safety & Multithreaded Access
    # -------------------------------------------------------------
    def test_concurrent_render_and_cache(self):
        """Verify concurrent threads calling render and load_template work without errors."""
        loader = PromptLoader(template_dir=self.temp_dir, cache_templates=True)
        exceptions = []

        def worker(thread_id):
            try:
                for i in range(50):
                    res = loader.render("simple", name=f"Thread-{thread_id}-{i}")
                    assert res == f"Hello Thread-{thread_id}-{i}!"
                    res_c = loader.render("complex", context={
                        "items": [{"name": f"item{i}", "active": i % 2 == 0}]
                    })
                    assert f"ITEM{i}" in res_c
            except Exception as e:
                exceptions.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(exceptions), 0, f"Thread exceptions: {exceptions}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
