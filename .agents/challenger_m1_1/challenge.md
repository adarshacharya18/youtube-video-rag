# Adversarial Challenge Report: Phase 07 M1 PromptLoader

## Challenge Summary

**Overall risk assessment**: MEDIUM

An empirical stress-test suite consisting of 18 isolated test cases was constructed and executed against `PromptLoader` in `src/core/llm/prompt_loader.py`. While 17 out of 18 test cases passed (verifying robust exception handling, strict variable enforcement, complex control flow, version resolution, path traversal security, and multithreaded concurrency), 1 empirical defect was identified regarding template caching behavior when caching is disabled.

---

## Challenges

### [Medium] Challenge 1: `cache_templates=False` fails to disable Jinja2 internal Environment cache

- **Assumption challenged**: Setting `cache_templates=False` (or `enable_cache=False`) on `PromptLoader` disables template caching completely to allow hot-reloading prompt files from disk.
- **Attack scenario**: A developer or pipeline setting `PromptLoader(cache_templates=False)` modifies prompt templates on disk (or re-renders updated `.j2` files in development/testing mode). Because `PromptLoader` initializes `jinja2.Environment` without setting `cache_size=0`, Jinja2's internal LRU cache (`env.cache`) remains active with its default size of 400. `env.get_template()` returns the cached template object from Jinja2's internal cache, ignoring file modifications unless file mtime changes across clock ticks.
- **Blast radius**: Developers or pipeline stages attempting to hot-reload prompt templates during iterative prompt engineering or testing will observe stale cached prompts being rendered despite passing `cache_templates=False`.
- **Mitigation**: In `src/core/llm/prompt_loader.py`, update `jinja2.Environment` instantiation to explicitly pass `cache_size`:
  ```python
  self.env = jinja2.Environment(
      loader=jinja2.FileSystemLoader(str(self.template_dir)),
      undefined=jinja2.StrictUndefined,
      trim_blocks=True,
      lstrip_blocks=True,
      autoescape=False,
      cache_size=400 if self.cache_templates else 0,
  )
  ```

---

## Stress Test Results

| Test Case | Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|---|
| **Test 01** | Exception Class Hierarchy | Inheritance from `FatalError` & `PromptTemplateError` | `TemplateNotFoundError` & `TemplateRenderError` inherit from `PromptTemplateError(FatalError)` | **PASS** |
| **Test 02** | Missing Template File | Raise `TemplateNotFoundError` | `TemplateNotFoundError` raised with full template path | **PASS** |
| **Test 03** | Missing Version Directory | Raise `TemplateNotFoundError` | `TemplateNotFoundError` raised detailing requested version | **PASS** |
| **Test 04** | Missing Context Variable | Raise `TemplateRenderError` | `TemplateRenderError` raised under `StrictUndefined` | **PASS** |
| **Test 05** | Missing Nested Attribute | Raise `TemplateRenderError` | `TemplateRenderError` raised specifying missing attribute | **PASS** |
| **Test 06** | Syntax Error on Load | Raise `TemplateRenderError` | `TemplateRenderError` raised with line number details | **PASS** |
| **Test 07** | Syntax Error on Render | Raise `TemplateRenderError` | `TemplateRenderError` raised during rendering | **PASS** |
| **Test 08** | Empty Template Render | Raise `TemplateRenderError` | `TemplateRenderError` raised for whitespace-only render | **PASS** |
| **Test 09** | Complex Jinja Logic & Macros | Correct string interpolation & macro evaluation | Rendered loops, filters (`| upper`), macros, and conditionals correctly | **PASS** |
| **Test 10** | Kwargs vs Context Precedence | Kwargs override context dict | Kwargs correctly override colliding context dict keys | **PASS** |
| **Test 11** | Version Directory Override | Render template from requested version | `version="v2"` correctly rendered v2 template | **PASS** |
| **Test 12** | Caching Enabled | Reuse compiled template in `_template_cache` | `load_template` returned identical object instance (`t1 is t2`) | **PASS** |
| **Test 13** | Caching Disabled (`cache_templates=False`) | Completely disable caching in `_template_cache` & Jinja2 | `_template_cache` bypassed, BUT `loader.env.cache` remained active (`LRUCache`) | **FAIL (Defect)** |
| **Test 14** | Custom `template_dir` Types | Accept `str` and `Path` | Both `str` and `Path` correctly coerced and used | **PASS** |
| **Test 15** | List Templates | List sorted `.j2` filenames, ignore non-`.j2` | Returned sorted `['complex.j2', 'empty.j2', ...]` excluding `.txt` | **PASS** |
| **Test 16** | List Versions | List version subdirectories, ignore hidden dirs | Returned sorted `['v1', 'v2']` excluding `.git` | **PASS** |
| **Test 17** | Path Traversal | Block relative `../` traversal outside root | `FileSystemLoader` blocked path traversal and raised `TemplateNotFoundError` | **PASS** |
| **Test 18** | Multithreaded Concurrency | Thread-safe rendering & caching under load | 10 threads completed 300 render calls with 0 errors | **PASS** |

---

## Unchallenged Areas

- **Disk Read I/O Performance**: File reading speed under extreme numbers of uncached templates on slow hardware was not benchmarked.
- **Custom Jinja Filters**: Registration of custom user-defined Jinja2 filters (beyond built-in filters) is not yet exposed via `PromptLoader` API.
