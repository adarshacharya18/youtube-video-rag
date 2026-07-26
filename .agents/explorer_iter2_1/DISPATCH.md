# DISPATCH — Explorer Iteration 2 - Fix Strategy Explorer

Objective: Formulate precise fix strategy for defects identified by Challenger 1 in Iteration 1.
Read:
- `/home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md` (Phase 06 section)
- `/home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase06/PROJECT.md`
- `/home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase06/GATE_STATUS.md`
- `/home/adarsh/Documents/Youtube-Channel/.agents/challenger_iter1_1/analysis.md`
- `/home/adarsh/Documents/Youtube-Channel/.agents/challenger_iter1_1/handoff.md`

Tasks to Address:
1. **Input Validation Defect**: `generate_structured()` in `src/core/llm/provider.py` must validate prompt types and contents. Empty string `""`, whitespace-only strings `"   "`, empty lists `[]`, non-string/non-list objects (e.g. `123`, `{}`), and list items with whitespace/empty content must raise `ValidationError`.
2. **Exception Translation Defect**: Update `_translate_exception` in `src/core/llm/provider.py` so that:
   - String matching checks both `exc_name` and `exc_str` (lowercase) for `"validation"`, `"auth"`, `"ratelimit"`, `"rate_limit"`, `"429"`, `"overloaded"`, `"529"`, `"timeout"`, `"connection"`, `"500"`, `"502"`, `"503"`, `"504"`.
   - Anthropic status 529 / overloaded is mapped to `RateLimitError` / `RetryableError`.
   - Wrapped SDK exceptions match properly.
3. **Dead Code Cleanup**: Remove unreachable code on line 162 of `src/core/llm/provider.py`.
4. **Test Suite Expansion**: Update `tests/llm/test_providers.py` to add test cases for these boundary input validation scenarios and exception translation edge cases.

Deliverable: Write fix specification in `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_iter2_1/analysis.md` and `handoff.md`.
