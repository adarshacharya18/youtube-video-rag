## 2026-07-29T11:41:39+05:30

You are Worker 1 for Phase 07 Milestone 1 (Core Prompt Loading Engine & Dependencies).

Your Working Directory: /home/adarsh/Documents/Youtube-Channel/.agents/worker_phase07_m1

MANDATORY READ:
- /home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md (specifically Phase 07 entry)
- /home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase07/PROJECT.md
- /home/adarsh/Documents/Youtube-Channel/.agents/explorer_phase07_1/analysis.md
- /home/adarsh/Documents/Youtube-Channel/.agents/explorer_phase07_2/analysis.md
- /home/adarsh/Documents/Youtube-Channel/.agents/explorer_phase07_3/analysis.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Scope & Owned Files:
You are exclusively responsible for writing/modifying:
- `pyproject.toml`
- `requirements.txt`
- `src/core/exceptions.py`
- `src/core/config.py`
- `src/core/llm/prompt_loader.py`

Detailed Instructions:
1. Update `pyproject.toml` and `requirements.txt` to include `jinja2>=3.1.0`. Install `jinja2` into `.venv` using run_command (e.g. `./.venv/bin/pip install jinja2`). Verify with `./.venv/bin/python -c "import jinja2; print(jinja2.__version__)"`.
2. Update `src/core/exceptions.py`:
   - Define `PromptTemplateError(FatalError)`
   - Define `TemplateNotFoundError(PromptTemplateError)`
   - Define `TemplateRenderError(PromptTemplateError)`
3. Update `src/core/config.py`:
   - Define `PromptConfig` model with `template_dir: Path = Path("src/core/llm/prompts")` and `default_version: str = "v1"`.
   - Add `prompts: PromptConfig = Field(default_factory=PromptConfig)` to `Config` / `Settings`.
4. Create `src/core/llm/prompt_loader.py`:
   - Implement `PromptLoader` class.
   - `__init__(self, template_dir: Path | str | None = None, default_version: str = "v1", cache_templates: bool = True)`
   - Set up `jinja2.Environment(loader=jinja2.FileSystemLoader(...), undefined=jinja2.StrictUndefined, trim_blocks=True, lstrip_blocks=True)`.
   - Implement template resolution logic handling version subdirectories (e.g. `prompts/v1/educational_plan.j2`), automatically appending `.j2` if omitted.
   - Catch `jinja2.TemplateNotFound` and raise `TemplateNotFoundError`.
   - Catch `jinja2.UndefinedError`, `jinja2.TemplateSyntaxError`, `jinja2.TemplateError` and raise `TemplateRenderError`.
   - Implement `load_template`, `render`, and `list_templates`.
   - Add `structlog` logging.
5. Run existing tests (`./.venv/bin/pytest tests/core/ tests/llm/`) to verify everything compiles and passes cleanly.

Deliverables:
- Write `changes.md` in your working directory.
- Write `handoff.md` in your working directory with build & test output evidence.
- Send a completion message back to the orchestrator.
