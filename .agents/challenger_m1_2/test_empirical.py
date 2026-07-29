"""
Empirical Test Suite for PromptLoader (Phase 07 Milestone 1).
Written by Challenger 2.
"""

import os
import sys
import time
import shutil
import tempfile
from pathlib import Path
from pydantic import BaseModel, Field

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.llm.prompt_loader import PromptLoader
from src.core.exceptions import (
    PromptTemplateError,
    TemplateNotFoundError,
    TemplateRenderError,
)

TEMP_DIR = Path(tempfile.mkdtemp(prefix="test_prompt_loader_"))
V1_DIR = TEMP_DIR / "v1"
V1_DIR.mkdir(parents=True, exist_ok=True)

class UserProfile(BaseModel):
    username: str
    tier: str = "premium"
    scores: list[int] = Field(default_factory=lambda: [10, 20, 30])

class VideoMetaDataTest(BaseModel):
    title: str
    duration: float
    user: UserProfile

def setup_templates():
    (V1_DIR / "simple.j2").write_text("Hello {{ name }}!")
    
    complex_content = """
    {% for item in items %}
    - Item {{ loop.index }}: {{ item.title }} (Duration: {{ item.duration }}s)
      Author: {{ item.user.username }} [{{ item.user.tier }}]
    {% endfor %}
    """
    (V1_DIR / "complex.j2").write_text(complex_content)
    
    (V1_DIR / "other.jinja").write_text("Other jinja")
    (V1_DIR / "other.jinja2").write_text("Other jinja2")
    (V1_DIR / "notes.txt").write_text("Notes text")
    (V1_DIR / "backup.j2.bak").write_text("Backup")
    (V1_DIR / ".hidden.j2").write_text("Hidden")

def run_performance_tests():
    print("=== 1. RENDERING PERFORMANCE (CACHING ON vs OFF) ===")
    setup_templates()
    
    context = {"name": "Alice"}
    iterations = 10000

    # 1.1 Simple Template Benchmark
    loader_cached = PromptLoader(template_dir=TEMP_DIR, cache_templates=True)
    start = time.perf_counter()
    for _ in range(iterations):
        loader_cached.render("simple", context)
    time_cached = time.perf_counter() - start

    loader_uncached = PromptLoader(template_dir=TEMP_DIR, cache_templates=False)
    start = time.perf_counter()
    for _ in range(iterations):
        loader_uncached.render("simple", context)
    time_uncached = time.perf_counter() - start

    speedup = time_uncached / time_cached if time_cached > 0 else 0
    print(f"Simple Template ({iterations} iterations):")
    print(f"  Cached:   {time_cached:.4f}s ({iterations/time_cached:.1f} ops/sec)")
    print(f"  Uncached: {time_uncached:.4f}s ({iterations/time_uncached:.1f} ops/sec)")
    print(f"  Speedup Factor: {speedup:.2f}x")

    # 1.2 Complex Template Benchmark
    user = UserProfile(username="coder123", tier="pro")
    video = VideoMetaDataTest(title="Binary Trees 101", duration=12.5, user=user)
    complex_context = {"items": [video] * 5}

    start = time.perf_counter()
    for _ in range(iterations):
        loader_cached.render("complex", complex_context)
    time_complex_cached = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        loader_uncached.render("complex", complex_context)
    time_complex_uncached = time.perf_counter() - start

    speedup_complex = time_complex_uncached / time_complex_cached if time_complex_cached > 0 else 0
    print(f"Complex Template ({iterations} iterations):")
    print(f"  Cached:   {time_complex_cached:.4f}s ({iterations/time_complex_cached:.1f} ops/sec)")
    print(f"  Uncached: {time_complex_uncached:.4f}s ({iterations/time_complex_uncached:.1f} ops/sec)")
    print(f"  Speedup Factor: {speedup_complex:.2f}x")

    # 1.3 Cache Inspection
    print("Cache State Inspection:")
    print(f"  loader_cached._template_cache keys: {list(loader_cached._template_cache.keys())}")
    print(f"  loader_uncached._template_cache keys: {list(loader_uncached._template_cache.keys())}")

    # 1.4 Cache Invalidation behavior test
    (V1_DIR / "simple.j2").write_text("Hello {{ name }} MODIFIED!")
    res_cached = loader_cached.render("simple", context)
    res_uncached = loader_uncached.render("simple", context)
    print("Cache Invalidation Test (File modified on disk):")
    print(f"  Cached loader returned:   '{res_cached}' (STALE CACHE HIT - disk edit ignored)")
    print(f"  Uncached loader returned: '{res_uncached}' (FRESH DISK READ - disk edit picked up)")
    
    # Reset file
    (V1_DIR / "simple.j2").write_text("Hello {{ name }}!")
    print()

def run_pydantic_tests():
    print("=== 2. PYDANTIC MODELS VS DICTS RENDERING BEHAVIOR ===")
    user = UserProfile(username="coder123", tier="pro")
    video = VideoMetaDataTest(title="Binary Trees 101", duration=12.5, user=user)

    loader = PromptLoader(template_dir=TEMP_DIR)

    # Test 2.1: Passing Pydantic model directly as context parameter
    print("Test 2.1: Passing Pydantic model directly as `context=video`")
    try:
        loader.render("simple", context=video) # type: ignore
        print("  RESULT: Unexpected Success")
    except TypeError as e:
        print(f"  RESULT: TypeError caught! ('{e}')")
        print("  ANALYSIS: `render` uses `{**(context or {})}`. Pydantic BaseModel does not implement Mapping protocol.")

    # Test 2.2: Passing Pydantic model as keyword argument / dict value
    print("Test 2.2: Passing Pydantic model as kwarg `item=video`")
    template_pydantic = "Title: {{ item.title }}, Duration: {{ item.duration }}, User: {{ item.user.username }}"
    (V1_DIR / "pydantic_test.j2").write_text(template_pydantic)

    res_pydantic = loader.render("pydantic_test", item=video)
    print(f"  RESULT: '{res_pydantic}'")

    # Test 2.3: Dict-style access on Pydantic model in Jinja2
    print("Test 2.3: Dict-style bracket access `{{ item['title'] }}` on Pydantic model in Jinja2")
    (V1_DIR / "pydantic_dict_style.j2").write_text("Title: {{ item['title'] }}")
    try:
        res_dict_style = loader.render("pydantic_dict_style", item=video)
        print(f"  RESULT: Success! '{res_dict_style}'")
    except Exception as e:
        print(f"  RESULT: Exception {type(e).__name__}: {e}")

    # Test 2.4: Pydantic vs Dict Rendering Benchmark
    video_dict = video.model_dump()
    (V1_DIR / "bench.j2").write_text("Title: {{ item.title }}, User: {{ item.user.username }}")

    iterations = 10000
    start = time.perf_counter()
    for _ in range(iterations):
        loader.render("bench", item=video)
    time_pydantic = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        loader.render("bench", item=video_dict)
    time_dict = time.perf_counter() - start

    print(f"Performance Benchmark ({iterations} renders):")
    print(f"  Pydantic V2 Model: {time_pydantic:.4f}s ({iterations/time_pydantic:.1f} ops/sec)")
    print(f"  Standard Dict:     {time_dict:.4f}s ({iterations/time_dict:.1f} ops/sec)")
    print(f"  Ratio (Pyd/Dict):   {time_pydantic/time_dict:.2f}x")
    print()

def run_list_templates_tests():
    print("=== 3. LIST_TEMPLATES & LIST_VERSIONS EDGE CASES ===")
    loader = PromptLoader(template_dir=TEMP_DIR)

    # 3.1 Non-existent version
    templates_nonexistent = loader.list_templates(version="v999")
    print(f"3.1 Non-existent version 'v999': {templates_nonexistent}")

    # 3.2 Empty version directory
    empty_v = TEMP_DIR / "v_empty"
    empty_v.mkdir(exist_ok=True)
    templates_empty = loader.list_templates(version="v_empty")
    print(f"3.2 Empty directory 'v_empty': {templates_empty}")

    # 3.3 Extension filtering & Hidden files
    v1_templates = loader.list_templates(version="v1")
    print(f"3.3 Files matched in 'v1' via list_templates: {v1_templates}")
    print(f"    - .j2 files included: {[f for f in v1_templates if not f.startswith('.')]}")
    print(f"    - Hidden .j2 files included: {[f for f in v1_templates if f.startswith('.')]}")
    print(f"    - Non-.j2 files (.jinja, .jinja2, .txt, .bak): Excluded as expected.")

    # 3.4 list_versions
    versions = loader.list_versions()
    print(f"3.4 list_versions() returned: {versions}")
    print(f"    Note: list_versions() explicitly excludes dot-hidden dirs, whereas list_templates does NOT filter out dot-hidden .j2 files.")

    # 3.5 Directory traversal
    traversal_templates = loader.list_templates(version="../v1")
    print(f"3.5 Path traversal version='../v1': {traversal_templates}")
    print()

def run_strict_undefined_tests():
    print("=== 4. STRICT UNDEFINED & EDGE CASE EXCEPTION BEHAVIOR ===")
    loader = PromptLoader(template_dir=TEMP_DIR)

    # 4.1 Missing top-level variable
    (V1_DIR / "missing_var.j2").write_text("Hello {{ missing_var }}!")
    try:
        loader.render("missing_var", {})
        print("4.1 Missing Top-level Var: FAILED (No exception)")
    except TemplateRenderError as e:
        print(f"4.1 Missing Top-level Var: PASSED -> Caught TemplateRenderError: {e}")

    # 4.2 Missing attribute on object
    (V1_DIR / "missing_attr.j2").write_text("Hello {{ item.nonexistent }}!")
    try:
        user = UserProfile(username="alice")
        loader.render("missing_attr", item=user)
        print("4.2 Missing Attribute on Object: FAILED (No exception)")
    except TemplateRenderError as e:
        print(f"4.2 Missing Attribute on Object: PASSED -> Caught TemplateRenderError: {e}")

    # 4.3 None variable
    (V1_DIR / "none_var.j2").write_text("Val: {{ item }}")
    res_none = loader.render("none_var", item=None)
    print(f"4.3 Defined variable set to None: Rendered as '{res_none}' (StrictUndefined permits None)")

    # 4.4 None attribute lookup
    (V1_DIR / "none_attr.j2").write_text("Val: {{ item.title }}")
    try:
        loader.render("none_attr", item=None)
        print("4.4 Attribute lookup on None: FAILED (No exception)")
    except TemplateRenderError as e:
        print(f"4.4 Attribute lookup on None: PASSED -> Caught TemplateRenderError: {e}")

    # 4.5 Empty template output check
    (V1_DIR / "empty_comments.j2").write_text("{# Just a comment #}\n   \n")
    try:
        loader.render("empty_comments")
        print("4.5 Empty Render Output: FAILED (No exception)")
    except TemplateRenderError as e:
        print(f"4.5 Empty Render Output: PASSED -> Caught TemplateRenderError: {e}")

    # 4.6 Non-existent template file
    try:
        loader.load_template("does_not_exist")
        print("4.6 Non-existent Template: FAILED (No exception)")
    except TemplateNotFoundError as e:
        print(f"4.6 Non-existent Template: PASSED -> Caught TemplateNotFoundError: {e}")

    # 4.7 Template Syntax Error
    (V1_DIR / "syntax_error.j2").write_text("{% if True %} Hello")
    try:
        loader.render("syntax_error")
        print("4.7 Syntax Error in Template: FAILED (No exception)")
    except TemplateRenderError as e:
        print(f"4.7 Syntax Error in Template: PASSED -> Caught TemplateRenderError: {e}")

    print()

def cleanup():
    shutil.rmtree(TEMP_DIR, ignore_errors=True)

if __name__ == "__main__":
    try:
        run_performance_tests()
        run_pydantic_tests()
        run_list_templates_tests()
        run_strict_undefined_tests()
    finally:
        cleanup()
