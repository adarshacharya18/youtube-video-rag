# Handoff Report — Phase 06: LLM Provider Abstraction Fix Strategy (Iteration 2)

**Agent**: `explorer_iter2_1` (Role: Fix Strategy Explorer)  
**Date**: 2026-07-26  
**Target Module**: Phase 06 — LLM Provider Abstraction (`src/core/llm/provider.py`, `tests/llm/test_providers.py`)  

---

## 1. Observation

Direct observations from examining `src/core/llm/provider.py`, `tests/llm/test_providers.py`, and Challenger 1's report (`.agents/challenger_iter1_1/analysis.md` and `handoff.md`):

1. **Input Validation Defect**:
   - `src/core/llm/provider.py:103-104`:
     ```python
     if prompt is None or (isinstance(prompt, str) and not prompt.strip()):
         raise ValidationError("Prompt cannot be empty or null")
     ```
   - Observed behavior: Inputs like `prompt = []` (empty list), `prompt = 12345` (int), `prompt = {"key": "val"}` (dict), or `prompt = [HumanMessage(content="")]` (message object with empty content) evaluate `isinstance(prompt, str)` as `False`. They bypass validation and reach LLM execution without raising `ValidationError`.

2. **Exception Translation Asymmetry Defect**:
   - `src/core/llm/provider.py:183-201`:
     - `"ratelimit"` checked `exc_name.lower()`, but `exc_str` checked `"rate limit"` with a space.
     - `"validation"` checked ONLY in `exc_name.lower()`, NOT `exc_str`.
     - `"auth"` checked ONLY in `exc_name.lower()`, NOT `exc_str`.
     - HTTP status code 529 (Anthropic overloaded) was missing from network error status codes `(500, 502, 503, 504)`.
   - Observed behavior: Custom SDK wrapped exceptions like `SDKError("RateLimitError: 30000 TPM limit")`, `SDKError("AuthenticationError: invalid key")`, `SDKError("ValidationError: ...")`, and `SDKError("Error code: 529")` have `exc_name = "SDKError"`. Because keyword matches were asymmetrical or missing keywords, these exceptions fell through to `FatalError`.

3. **Dead Code**:
   - `src/core/llm/provider.py:162`:
     ```python
     raise NetworkError(f"LLM request failed after {self.max_retries} retries")
     ```
   - Observed behavior: The loop on lines 112–160 either returns `result` (line 135) or raises `translated_exc` when `attempt == max_attempts` (line 160). Line 162 is unreachable under all conditions.

---

## 2. Logic Chain

1. **Step 1 (Input Validation)**:
   - *Observation*: `generate_structured()` only checked `not prompt.strip()` if `isinstance(prompt, str)`.
   - *Reasoning*: Prompt parameters can be strings or lists of message objects. If a prompt is `None`, an empty list `[]`, a non-string/non-list type, or a list containing messages with empty/whitespace text, passing it to `with_structured_output().invoke()` causes runtime failures down the LangChain/vendor SDK stack.
   - *Fix Formulation*: Implement `_validate_prompt(self, prompt: Any) -> None` that explicitly checks `prompt is None`, `isinstance(prompt, str)`, `isinstance(prompt, list)` (ensuring non-empty list and non-empty content per item), and rejects all other types with `ValidationError`.

2. **Step 2 (Exception Translation)**:
   - *Observation*: `_translate_exception()` inspected `exc_name` and `exc_str` with different keyword sets.
   - *Reasoning*: Third-party SDKs or custom wrappers often raise exception classes named `SDKError`, `APIError`, or generic `Exception` where the actual error type (`RateLimitError`, `ValidationError`, `AuthenticationError`) is embedded in `str(exc)`. By creating a single combined lower-case string `full_text = f"{exc_name} {exc_str}".lower()`, all keyword checks (`"ratelimit"`, `"rate limit"`, `"auth"`, `"validation"`, `"529"`, `"overloaded"`) evaluate symmetrically across both exception class name and message string. Furthermore, adding status code 529 ensures Anthropic Overloaded errors translate to retryable `NetworkError`.

3. **Step 3 (Dead Code Cleanup)**:
   - *Observation*: Line 162 comes after a `while attempt <= max_attempts:` block where the `else:` branch of the final attempt unconditionally raises `translated_exc`.
   - *Reasoning*: Because line 160 always raises on retry exhaustion, line 162 is unreachable. Removing it cleans up dead code without affecting runtime behavior.

4. **Step 4 (Test Additions)**:
   - *Observation*: Existing test suite `tests/llm/test_providers.py` (15 unit tests) passed but lacked assertions for boundary input types and wrapped SDK exceptions.
   - *Fix Formulation*: Add `@pytest.mark.parametrize` test cases for boundary prompts (`[]`, `123`, `{}`, `[HumanMessage(content="")]`) and a multi-case test `test_provider_exception_translation_wrapped_sdk_errors` for wrapped SDK exceptions and HTTP 529.

---

## 3. Caveats

- **No Live Vendor API Execution**: Live API keys were not tested during this design phase; fix strategies rely on unit test mocks and empirical stress harness logic.
- **Read-Only Scope**: This agent operates under read-only constraints; implementation changes must be applied by an implementer agent using the exact specifications provided in `analysis.md`.

---

## 4. Conclusion

The 3 defects identified by Challenger 1 are fully analyzed and resolved by the proposed fix strategy:
- `src/core/llm/provider.py`: Replace `generate_structured()` prompt check with `_validate_prompt()`, upgrade `_translate_exception()` with symmetric `full_text` keyword matching and HTTP 529 support, and remove dead line 162.
- `tests/llm/test_providers.py`: Append `test_provider_boundary_prompt_validation_failures` and `test_provider_exception_translation_wrapped_sdk_errors`.

---

## 5. Verification Method

To verify the fix strategy once implemented by worker/implementer:

1. **Run Pytest Suite**:
   ```bash
   ./.venv/bin/pytest tests/llm/test_providers.py -v
   ```
   *Expected Result*: All 15 existing unit tests + new boundary prompt tests + new wrapped exception translation tests pass (17+ passed).

2. **Run Empirical Stress Harness**:
   ```bash
   ./.venv/bin/python .agents/challenger_iter1_1/stress_harness_v2.py
   ```
   *Expected Result*: 0 defects/issues reported by the stress harness.

3. **Inspect Files**:
   - `src/core/llm/provider.py`: Verify `_validate_prompt()` is called, `_translate_exception()` uses `full_text`, status 529 is included, and line 162 is removed.
