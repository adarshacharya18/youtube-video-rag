# Changes Made for Phase 07 Milestone 1

## Summary
Implemented Core Prompt Loading Engine & Dependencies for Phase 07 (Prompt Library & Management).

## Modified & Created Files

### 1. `pyproject.toml`
- Added `"jinja2>=3.1.0"` to the `dependencies` list under `[project]`.

### 2. `requirements.txt`
- Added `jinja2>=3.1.0` under `# LLM Provider Dependencies`.

### 3. `src/core/exceptions.py`
- Defined `PromptTemplateError(FatalError)` as base exception for prompt loader issues.
- Defined `TemplateNotFoundError(PromptTemplateError)` raised when prompt templates or versions are missing on disk.
- Defined `TemplateRenderError(PromptTemplateError)` raised when Jinja2 fails due to syntax errors or missing context variables under `StrictUndefined`.

### 4. `src/core/config.py`
- Added `PromptConfig` model with `template_dir: Path = Path("src/core/llm/prompts")` and `default_version: str = "v1"`.
- Added `prompts: PromptConfig = Field(default_factory=PromptConfig)` to `LLMConfig` and `PipelineConfig`.

### 5. `src/core/llm/prompt_loader.py`
- Created `PromptLoader` class implementing Jinja2 template loading, in-memory caching (`_template_cache`), version subdirectory resolution, `StrictUndefined` variable checking, and domain exception translation.
- Implemented `__init__`, `_resolve_template_path`, `load_template`, `get_template`, `render`, `list_templates`, and `list_versions` with `structlog` integration.
