# DISPATCH — Worker Iteration 2

Objective: Implement defect fixes for Phase 06 LLM Provider Abstraction.

Read:
- `/home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md` (Phase 06 section)
- `/home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase06/PROJECT.md`
- `/home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase06/GATE_STATUS.md`
- Fix Strategy Explorer Reports:
  - `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_iter2_1/analysis.md`
  - `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_iter2_1/handoff.md`

Tasks:
1. Update `src/core/llm/provider.py`:
   - Implement `_validate_prompt(self, prompt: Any) -> None` in `BaseLLMProvider.generate_structured()` validating prompt inputs. Raise `ValidationError` if prompt is `None`, non-string/non-list (e.g. `int`, `dict`), whitespace string `""` or `"   "`, empty list `[]`, or a list containing non-string/non-dict elements or elements with empty/whitespace content.
   - Update `_translate_exception()` to use `full_text = f"{exc_name} {exc_str}".lower()`, mapping `"validation"`, `"auth"`, `"429"`, `"ratelimit"`, `"rate_limit"`, `"529"`, `"overloaded"`, `"timeout"`, `"connection"`, `"500"`, `"502"`, `"503"`, `"504"` symmetrically across exception class names and message strings.
   - Remove unreachable code on line 162.
2. Update `tests/llm/test_providers.py`:
   - Add boundary prompt validation tests (`test_provider_boundary_prompt_validation_failures`) for empty string, whitespace string, empty list, invalid prompt type, and list with empty element.
   - Add wrapped exception translation test (`test_provider_exception_translation_wrapped_sdk_errors`) testing wrapped SDK error strings and Anthropic 529 status.
3. Run verification:
   - `./.venv/bin/pytest tests/llm/test_providers.py`
   - `./.venv/bin/pytest tests/core tests/models`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Deliverable: Write implementation details in `/home/adarsh/Documents/Youtube-Channel/.agents/worker_iter2/changes.md` and `handoff.md`.
