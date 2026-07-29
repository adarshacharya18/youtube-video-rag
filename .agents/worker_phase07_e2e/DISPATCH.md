## 2026-07-29T06:19:12Z

You are Test Writer / Worker E2E for Phase 07 Milestone E2E (Test Suite Implementation).

Your Working Directory: /home/adarsh/Documents/Youtube-Channel/.agents/worker_phase07_e2e

MANDATORY READ:
- /home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md (specifically Phase 07 entry)
- /home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase07/PROJECT.md
- /home/adarsh/Documents/Youtube-Channel/.agents/explorer_phase07_3/analysis.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Scope & Owned File:
You are exclusively responsible for creating:
- `tests/llm/test_prompt_loader.py`

Detailed Requirements (from ORIGINAL_REQUEST.md acceptance criteria):
1. `pytest tests/llm/test_prompt_loader.py` MUST pass cleanly.
2. Must actively render Jinja templates with mock variables and assert the rendered output strictly matches expected hardcoded strings (`assert output == EXPECTED_HARDCODED_STRING`).
3. Include pytest fixtures (`tmp_path` mock template directory hierarchies for `v1` and `v2`).
4. Test core API methods: `PromptLoader.__init__`, `load_template`, `render`, `list_templates`.
5. Test version resolution and automatic `.j2` extension appending.
6. Test exception raising: `TemplateNotFoundError` (for missing templates/versions) and `TemplateRenderError` (for missing context variables under Jinja2 `StrictUndefined` or syntax errors).
7. Test integration with real project templates (`educational_plan.j2` and `code_explanation.j2`).
8. Run pytest command to verify: `./.venv/bin/pytest tests/llm/test_prompt_loader.py -v`.

Deliverables:
- Write `changes.md` in your working directory.
- Write `handoff.md` in your working directory with test execution evidence.
- Send a completion message back to the orchestrator.
