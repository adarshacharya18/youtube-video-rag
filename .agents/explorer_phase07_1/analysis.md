# Architectural Analysis: Phase 07 (Prompt Library & Management)

## Executive Summary
This analysis presents the structural, dependency, and architectural investigation of the `/home/adarsh/Documents/Youtube-Channel` repository for **Phase 07: Prompt Library & Management**. 

### Key Findings
1. **Dependency Status**: `jinja2` is currently **missing** from `pyproject.toml` dependencies and `requirements.txt`, and is **not installed** in the virtual environment (`.venv`). It must be added (`jinja2>=3.1.0`) and installed before Phase 07 implementation.
2. **Codebase Architecture**: The codebase follows a synchronous batch-pipeline paradigm built around `Pydantic V2`, explicit static typing, `structlog` logging, and custom exception hierarchies in `src.core.exceptions`.
3. **LLM Core Subsystem**: Located at `src/core/llm/`, currently containing `provider.py`, `openai_client.py`, and `anthropic_client.py`. `PromptLoader` will naturally fit as `src/core/llm/prompt_loader.py`.
4. **Template Storage Location**: Recommended path is `src/core/llm/templates/` (co-located with `prompt_loader.py`), with support for customizable template directory parameters (`template_dir: Path | None = None`).
5. **Testing Architecture**: Existing LLM tests reside in `tests/llm/test_providers.py`. The new test suite must be placed at `tests/llm/test_prompt_loader.py`.

---

## 1. Codebase Structure Analysis

### Directory Tree & Subsystems
- **`src/`**:
  - `src/core/`: Central infrastructural building blocks.
    - `base.py`: Core protocols (`PipelineModule`, `Service`, `Repository`, `Provider`, `Factory`, `Command`, `Configuration`, `Lifecycle`, `Validator`) and standard result model `BasePipelineResult`.
    - `config.py`: Root config `PipelineConfig` and sub-configs using `pydantic-settings`.
    - `exceptions.py`: Central exception hierarchy root `PipelineError` -> `RetryableError` / `FatalError` -> specific operational and module errors (`ValidationError`, `ConfigurationError`, etc.).
    - `logger.py`: `structlog` setup providing structured JSON/key-value logging.
    - `models/`: Pydantic V2 schemas (`video.py`, `plan.py`, `assets.py`).
    - `llm/`: LLM abstraction provider (`provider.py`, `openai_client.py`, `anthropic_client.py`).
    - `orchestrator/`: SQLite State Ledger (`state_ledger.py`).
    - `ingestion/` & `rag/`: Document ingestion and vector RAG components.
  - `src/animation/`, `src/assembly/`, `src/voice/`, `src/script/`, `src/youtube/`, `src/cli/`: Pipeline execution modules.

- **`tests/`**:
  - `tests/core/`: Config, base, logger, exceptions tests.
  - `tests/models/`: Pydantic model validation tests (`test_validation.py`).
  - `tests/llm/`: Provider abstraction tests (`test_providers.py`).
  - `tests/fixtures/`: Sample data fixtures (e.g. `ingestion/two_sum.md`).

- **`PromptBook/`**: Architectural documentation and phase specifications (`Phase01/`, `Phase05/`, `Phase06/`, etc.).

---

## 2. Dependency & Environment Analysis

### `pyproject.toml` Inspection
The current dependencies list in `pyproject.toml` is:
```toml
dependencies = [
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "structlog>=24.1.0",
    "python-dotenv>=1.0.0",
    "pyyaml>=6.0.0",
    "markdown-it-py>=3.0.0",
    "beautifulsoup4>=4.12.0",
    "langchain>=0.2.0",
    "langchain-core>=0.2.0",
    "langchain-openai>=0.1.0",
    "langchain-anthropic>=0.1.0",
    "openai>=1.0.0",
    "anthropic>=0.20.0",
]
```
- **Finding**: `jinja2` is **missing** from `pyproject.toml`.

### `requirements.txt` Inspection
`requirements.txt` mirrors `pyproject.toml` and also lacks `jinja2`.

### Environment Runtime Inspection
Running `.venv/bin/python -c "import jinja2"` yields:
`ModuleNotFoundError: No module named 'jinja2'`

### Action Item for Implementer
- Update `pyproject.toml` under `[project.dependencies]` to include `"jinja2>=3.1.0"`.
- Update `requirements.txt` to include `jinja2>=3.1.0`.
- Install package inside `.venv` (`.venv/bin/pip install jinja2` or `.venv/bin/pip install -e .`).

---

## 3. Coding Styles & Conventions

1. **Python Formatting & Line Length**:
   - PEP 8 compliant, line length ~88-100 chars, 4 spaces indentation.

2. **Static Typing & Annotations**:
   - Strict explicit typing across all functions, methods, parameters, and return types.
   - Modern generic syntax (`list[str]`, `dict[str, Any]`, `Path | None`, `str | None`).
   - Use `typing.Any` or `TypeVar` explicitly when required.

3. **Exception Handling**:
   - Import and raise custom exceptions from `src.core.exceptions`.
   - Missing template file or invalid template name -> raise `ValidationError` (or `PipelineValidationError`).
   - Template rendering error -> raise `ValidationError` with descriptive details.

4. **Structured Logging**:
   - Logger instantiation: `logger = structlog.get_logger(__name__)`.
   - Logging calls: use keyword parameters rather than string formatting/concatenation:
     `logger.info("rendering_prompt_template", template_name=template_name, variables=list(kwargs.keys()))`

5. **Docstrings & Comments**:
   - Module-level docstrings outlining purpose.
   - Standard Google/Sphinx style class and method docstrings with `Args:`, `Returns:`, `Raises:`.

---

## 4. Prompt Template Storage Location Strategy

### Recommended Location: `src/core/llm/templates/`
- Primary relative path: `src/core/llm/templates/`
- Co-locating template files (`.j2`) inside `src/core/llm/templates/` ensures that `prompt_loader.py` can locate default templates via `Path(__file__).parent / "templates"`.
- Required Foundational Templates:
  1. `src/core/llm/templates/educational_plan.j2` (Educational Plan Generation)
  2. `src/core/llm/templates/code_explanation.j2` (Code Explanation)

### Flexible Directory Support in `PromptLoader`
`PromptLoader` should accept an optional `template_dir: Path | str | None = None` parameter during initialization:
- If `template_dir` is provided, use `Path(template_dir)`.
- If `template_dir` is `None`, default to `Path(__file__).parent / "templates"`.
- Use Jinja2's `FileSystemLoader` pointing to the resolved template directory with `Environment(loader=FileSystemLoader(...), autoescape=False, trim_blocks=True, lstrip_blocks=True)`.

---

## 5. Architectural Implementation Blueprint for Phase 07

1. **File Locations to Create/Modify**:
   - `pyproject.toml` & `requirements.txt`: Add `jinja2>=3.1.0`.
   - `src/core/llm/prompt_loader.py`: The `PromptLoader` class implementing Jinja2 template loading and rendering.
   - `src/core/llm/templates/educational_plan.j2`: Foundational Jinja2 prompt template for generating DSA educational plans.
   - `src/core/llm/templates/code_explanation.j2`: Foundational Jinja2 prompt template for step-by-step code explanation and visual scene breakdown.
   - `PromptBook/Phase07/01_Prompt_Library.md`: Documentation detailing template organization, Jinja2 syntax rules, prompt engineering standards, and versioning conventions.
   - `tests/llm/test_prompt_loader.py`: Test suite verifying template rendering with mock variables, assertion of rendered string output, and error handling for missing/malformed templates.

2. **Key Design Considerations for `PromptLoader`**:
   - Method signature: `render(template_name: str, **kwargs: Any) -> str`
   - Checks template existence before rendering, raising structured custom exception (`ValidationError`) if missing or invalid.
   - Support rendering complex nested Pydantic models, dicts, lists, conditional blocks (`{% if %}`), and loops (`{% for %}`).
   - Ensure whitespace control (`trim_blocks=True`, `lstrip_blocks=True`).
