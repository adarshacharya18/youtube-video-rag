# Challenge Report — PromptLoader Empirical Stress Test (Phase 07 M1)

**Challenger**: Challenger 2  
**Date**: 2026-07-29  
**Target Module**: `src/core/llm/prompt_loader.py`  
**Overall Risk Assessment**: LOW  

---

## 1. Executive Summary

Empirical testing was conducted on `PromptLoader` using Python 3.13.7 in an isolated environment (`test_empirical.py`). Tests evaluated rendering performance with caching enabled vs disabled, Pydantic model vs dictionary context resolution, `list_templates` edge cases, path traversal, and strict undefined behavior.

`PromptLoader` performs reliably, accurately enforces Jinja2 `StrictUndefined` variable checks, properly translates Jinja2 exceptions into domain exceptions (`TemplateNotFoundError`, `TemplateRenderError`), and exhibits strong rendering throughput (~160,000 ops/sec).

---

## 2. Empirical Test Results

### 2.1 Rendering Performance & Caching Mechanics

| Scenario | Iterations | Caching Enabled | Caching Disabled | Speedup / Impact |
|---|---|---|---|---|
| Simple Template (`simple.j2`) | 10,000 | 0.0619s (161,570 ops/sec) | 0.0812s (123,157 ops/sec) | 1.31x speedup |
| Complex Template (`complex.j2`) | 10,000 | 0.1441s (69,418 ops/sec) | 0.1459s (68,531 ops/sec) | 1.01x speedup |

**Cache Mechanics Observations**:
1. `PromptLoader` stores compiled `jinja2.Template` instances in `self._template_cache` when `cache_templates=True`.
2. **Stale Cache Behavior**: Modifying a `.j2` file on disk after loading it with `cache_templates=True` continues to return the old, cached template contents indefinitely. There is currently no file modification time (mtime) checking or `clear_cache()` method on `PromptLoader`.

---

### 2.2 Pydantic Models vs Dicts Rendering Behavior

| Input Type | Invocation Style | Result | Observations |
|---|---|---|---|
| Pydantic BaseModel | Direct `context=model` | `TypeError: 'VideoMetaDataTest' object is not a mapping` | `render()` executes `{**(context or {})}` which requires Python `Mapping` interface. |
| Pydantic BaseModel | Kwarg `item=model` | Success (`'Title: Binary Trees 101...'`) | Jinja2 resolves `{{ item.title }}` via Python `getattr()`. |
| Pydantic BaseModel | Bracket access `{{ item['title'] }}` | Success (`'Title: Binary Trees 101'`) | Jinja2 falls back gracefully to attribute lookup for Pydantic V2 models. |
| Dict Object | Kwarg `item=dict_obj` | Success | Standard dictionary key resolution. |

**Performance Comparison (10,000 renders)**:
- Pydantic V2 Model: 0.0608s (~164,600 ops/sec)
- Standard Dict: 0.0711s (~140,680 ops/sec)
- Ratio: 0.85x (Pydantic attribute access is faster or on par with Python dict key lookup in Python 3.13).

---

### 2.3 `list_templates` & `list_versions` Edge Cases

| Test Case | Inputs | Result | Status / Observation |
|---|---|---|---|
| Non-existent version | `list_templates(version="v999")` | `[]` | Pass (Gracefully returns empty list) |
| Empty directory | `list_templates(version="v_empty")` | `[]` | Pass (Gracefully returns empty list) |
| Extension filtering | Directory with `.j2`, `.jinja`, `.jinja2`, `.txt`, `.bak` | Only `.j2` matched | Pass (Excludes non-`.j2` extensions) |
| Dot-hidden `.j2` files | Directory with `.hidden.j2` | Included (`['.hidden.j2', ...]`) | Minor Inconsistency (`list_versions` ignores hidden dirs, `list_templates` does not filter out hidden `.j2` files) |
| Path Traversal | `list_templates(version="../v1")` | `[...]` | Path traversal resolved relative to `template_dir` |

---

### 2.4 Strict Undefined & Edge Case Exceptions

| Scenario | Trigger Input | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|---|
| Undefined Variable | `{{ missing_var }}` | Raise `TemplateRenderError` | `TemplateRenderError` raised wrapping `StrictUndefined` | Pass |
| Missing Object Attribute | `{{ item.nonexistent }}` | Raise `TemplateRenderError` | `TemplateRenderError` raised wrapping `AttributeError` | Pass |
| Variable set to `None` | `{{ item }}` with `item=None` | Render `"None"` | Rendered `"Val: None"` | Pass |
| Attribute on `None` | `{{ item.title }}` with `item=None` | Raise `TemplateRenderError` | `TemplateRenderError` raised wrapping `UndefinedError` | Pass |
| Empty Render Output | Template rendering to whitespace/comment | Raise `TemplateRenderError` | `TemplateRenderError` raised ("rendered to an empty string") | Pass |
| Missing Template | Non-existent `.j2` file | Raise `TemplateNotFoundError` | `TemplateNotFoundError` raised | Pass |
| Syntax Error | `{% if True %} Hello` | Raise `TemplateRenderError` | `TemplateRenderError` raised wrapping `TemplateSyntaxError` | Pass |

---

## 3. Findings & Recommendations

### Finding 1: Direct Pydantic Context Unpacking Limitation (Low Severity)
Calling `loader.render("template_name", context=pydantic_instance)` raises `TypeError` because `PromptLoader.render()` performs `{**(context or {}), **kwargs}`.  
*Mitigation / Guidance*: Callers passing a Pydantic model as the root context must either pass `context=model.model_dump()` or pass it as a named keyword argument (`item=model`).

### Finding 2: Lack of Cache Invalidation / Clearing Method (Low Severity)
In-memory caching (`_template_cache`) stores compiled `jinja2.Template` objects indefinitely. If template files are edited during runtime, `PromptLoader` will continue serving stale templates until the process restarts.  
*Mitigation / Guidance*: Consider adding a `clear_cache()` method or checking file `mtime` if dynamic template reloads are needed in development.

### Finding 3: `list_templates` Dot-File Filtering (Low Severity)
`list_versions()` excludes dot-hidden directories (`not d.name.startswith(". ")`), whereas `list_templates()` uses `glob("*.j2")` which includes dot-hidden files like `.hidden.j2`.  
*Mitigation / Guidance*: In a future refactoring, `list_templates` can filter out `filename.startswith(".")` for consistency.

---

## 4. Conclusion & Verdict

The implementation of `PromptLoader` is robust, performant, and meets all requirements specified for Phase 07 Milestone 1.

**Verdict**: `APPROVE`
