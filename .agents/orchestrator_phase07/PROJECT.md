# Project: Phase 07 Prompt Library & Management

## Architecture
- `src/core/llm/prompt_loader.py`: `PromptLoader` wrapping Jinja2 `Environment` with `FileSystemLoader`, `StrictUndefined` variable enforcement, in-memory caching (`_template_cache`), and exception handling.
- `src/core/config.py`: Add `PromptConfig` (`template_dir: Path`, `default_version: str`).
- `src/core/exceptions.py`: Add `PromptTemplateError`, `TemplateNotFoundError`, `TemplateRenderError` inheriting from `FatalError`.
- Templates directory: `src/core/llm/prompts/v1/` containing `educational_plan.j2` and `code_explanation.j2`.
- Documentation: `PromptBook/Phase07/01_Prompt_Library.md`.
- E2E / Unit Tests: `tests/llm/test_prompt_loader.py`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Dependency Updates | Add `jinja2>=3.1.0` to `pyproject.toml` and `requirements.txt` | M1 | survey (explorer_1) |
| 2 | Core Exceptions & Config | Add `PromptTemplateError`, `TemplateNotFoundError`, `TemplateRenderError` to `src/core/exceptions.py`, add `PromptConfig` to `src/core/config.py` | M1 | survey (explorer_2) |
| 3 | Prompt Loading Engine | Create `src/core/llm/prompt_loader.py` with Jinja2 engine, strict undefined, caching | M1 | survey (explorer_2) |
| 4 | Foundational Templates | Create `src/core/llm/prompts/v1/educational_plan.j2` and `code_explanation.j2` | M2 | survey (explorer_2) |
| 5 | Prompt Management Doc | Document prompt engineering guidelines, Jinja2 usage, and storage strategy in `PromptBook/Phase07/01_Prompt_Library.md` | M2 | survey (explorer_2) |
| 6 | Unit & E2E Testing Suite | Create `tests/llm/test_prompt_loader.py` with mock variable rendering & strict string match assertions | E2E | survey (explorer_3) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Core Engine & Config | `pyproject.toml`, `requirements.txt`, `src/core/exceptions.py`, `src/core/config.py`, `src/core/llm/prompt_loader.py` | none | DONE |
| 2 | M2: Foundational Templates & Doc | `src/core/llm/prompts/v1/educational_plan.j2`, `src/core/llm/prompts/v1/code_explanation.j2`, `PromptBook/Phase07/01_Prompt_Library.md` | M1 | DONE |
| 3 | E2E: Test Suite | `tests/llm/test_prompt_loader.py` | M1, M2 | DONE |

## Interface Contracts
### PromptLoader API
- `__init__(template_dir: Path | str | None = None, default_version: str = "v1", cache_templates: bool = True)`
- `load_template(template_name: str, version: str | None = None) -> jinja2.Template`
- `render(template_name: str, context: dict[str, Any], version: str | None = None) -> str`
- `list_templates(version: str | None = None) -> list[str]`

### Exceptions API
- `PromptTemplateError(FatalError)`: Base exception for prompt loader issues.
- `TemplateNotFoundError(PromptTemplateError)`: Raised when requested `.j2` template file or version does not exist.
- `TemplateRenderError(PromptTemplateError)`: Raised when Jinja2 rendering fails (e.g. missing variable under `StrictUndefined` or syntax error).

## Code Layout
- Dependencies: `pyproject.toml`, `requirements.txt`
- Config & Exceptions: `src/core/config.py`, `src/core/exceptions.py`
- Prompt Loader: `src/core/llm/prompt_loader.py`
- Templates: `src/core/llm/prompts/v1/educational_plan.j2`, `src/core/llm/prompts/v1/code_explanation.j2`
- Documentation: `PromptBook/Phase07/01_Prompt_Library.md`
- Tests: `tests/llm/test_prompt_loader.py`
