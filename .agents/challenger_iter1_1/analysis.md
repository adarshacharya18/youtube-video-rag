# Empirical Challenge & Stress Test Report — LLM Provider Abstraction

**Agent Identity**: `challenger_iter1_1` (Role: Challenger / Critic & Specialist)  
**Date**: 2026-07-26  
**Target Module**: Phase 06 — LLM Provider Abstraction (`src/core/llm/provider.py`, `openai_client.py`, `anthropic_client.py`, `tests/llm/test_providers.py`)  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Executive Summary & Verdict

The unit test suite `./.venv/bin/pytest tests/llm/test_providers.py` passes 15/15 tests. However, adversarial empirical stress testing using custom stress harnesses (`stress_harness.py` and `stress_harness_v2.py`) revealed **9 empirical defects/vulnerabilities** in prompt validation, exception translation string matching, HTTP status handling, and dead code.

### Overall Risk Assessment: **HIGH**
While basic mocked happy-path tests and standard retry recovery pass, edge-case exception wrapping from vendor SDKs (OpenAI/Anthropic/LangChain) and malformed inputs bypass protection, leading to unhandled `FatalError` misclassifications and invalid API invocations.

---

## 2. Test Execution Summary

### Pytest Unit Suite
- Command: `./.venv/bin/pytest tests/llm/test_providers.py`
- Result: **PASSED (15/15 passed in 2.49s)**

### Empirical Stress Harness Suite
- Harness Path: `.agents/challenger_iter1_1/stress_harness_v2.py`
- Executed Tests: 1,000 exponential backoff delay trials, 20 exception translation matrix cases, 8 prompt validation boundary cases, 20 concurrent thread workers.
- Result: **FAILED (9 defects detected)**

---

## 3. Empirical Findings & Challenges

### Challenge 1: Prompt Validation Bypass for Non-String & Empty List Inputs [HIGH]
- **Observation**: `src/core/llm/provider.py` line 103:
  ```python
  if prompt is None or (isinstance(prompt, str) and not prompt.strip()):
      raise ValidationError("Prompt cannot be empty or null")
  ```
- **Attack Scenario**: Passing `prompt = []` (empty list), `prompt = [HumanMessage(content="")]`, `prompt = 12345` (integer), or `prompt = {"key": "val"}` (dict).
- **Empirical Proof**:
  In `stress_harness_v2.py`, `generate_structured([], VideoMetadata)` passed input validation and invoked `structured_llm.invoke([])` without raising `ValidationError` upfront.
- **Blast Radius**: Malformed inputs bypass domain validation, reaching vendor SDKs and causing cryptic downstream errors or wasting API request quota.
- **Mitigation**: Expand validation in `generate_structured`:
  ```python
  if prompt is None:
      raise ValidationError("Prompt cannot be empty or null")
  if isinstance(prompt, str) and not prompt.strip():
      raise ValidationError("Prompt string cannot be empty or whitespace")
  if isinstance(prompt, list):
      if len(prompt) == 0:
          raise ValidationError("Prompt message list cannot be empty")
  elif not isinstance(prompt, str):
      raise ValidationError(f"Prompt must be a string or list of messages, got {type(prompt).__name__}")
  ```

---

### Challenge 2: Exception Translation String Matching Gaps [HIGH]
- **Observation**: `src/core/llm/provider.py` lines 184–201 inspect `exc_name` and `exc_str` using asymmetrical rules:
  - `validation` is only checked in `exc_name.lower()`, NOT `exc_str`.
  - `auth` is only checked in `exc_name.lower()`, NOT `exc_str`.
  - `ratelimit` (without spaces) is checked in `exc_name.lower()`, but only `"rate limit"` (with space) is checked in `exc_str`.
  - HTTP 529 (Anthropic Overloaded) is not in `status_code in (500, 502, 503, 504)`.
- **Attack Scenario**: Vendor SDKs or LangChain wrappers often raise generic `Exception("ValidationError: 1 error...")` or `SDKError("RateLimitError: 30000 TPM limit")` where `exc_name = "Exception"` or `"SDKError"`.
- **Empirical Proof**:
  - `SDKError('RateLimitError: 30000 TPM limit')` translated to `FatalError` instead of `RateLimitError`.
  - `SDKError('AuthenticationError: invalid key')` translated to `FatalError` instead of `AuthenticationError`.
  - `SDKError('ValidationError: 1 validation error')` translated to `FatalError` instead of `ValidationError`.
  - `SDKError('Error code: 529', status_code=529)` translated to `FatalError` instead of `NetworkError`.
  - `SDKError('ConnectionResetError: Connection lost')` translated to `FatalError` instead of `NetworkError`.
- **Blast Radius**: Transient rate limits, network resets, and Anthropic 529 overloaded errors are misclassified as `FatalError` (unretryable), crashing the pipeline immediately instead of retrying.
- **Mitigation**: Update `_translate_exception` in `src/core/llm/provider.py`:
  ```python
  # Rate Limits (HTTP 429)
  if status_code == 429 or any(kw in exc_name.lower() or kw in exc_str for kw in ["ratelimit", "rate limit", "429"]):
      return RateLimitError(f"LLM rate limit exceeded: {exc}")

  # Authentication / Authorization (HTTP 401, 403)
  if status_code in (401, 403) or any(kw in exc_name.lower() or kw in exc_str for kw in ["auth", "unauthorized", "api key"]):
      return AuthenticationError(f"LLM authentication failed: {exc}")

  # Validation / Structured Output Parser Failures
  if any(kw in exc_name.lower() or kw in exc_str for kw in ["validation", "outputparser", "json"]):
      return ValidationError(f"LLM structured output validation failed: {exc}")

  # Network / Timeouts / Connection / HTTP 5xx Server Errors (including Anthropic 529)
  if (
      isinstance(exc, (TimeoutError, ConnectionError))
      or status_code in (500, 502, 503, 504, 529)
      or any(kw in exc_name.lower() or kw in exc_str for kw in ["timeout", "connection", "network", "httperror", "overloaded"])
  ):
      return NetworkError(f"LLM network issue: {exc}")
  ```

---

### Challenge 3: Unreachable Dead Code in `provider.py` [LOW]
- **Observation**: `src/core/llm/provider.py` line 162:
  ```python
  raise NetworkError(f"LLM request failed after {self.max_retries} retries")
  ```
- **Logic Chain**: The `while attempt <= max_attempts:` loop (lines 112–160) always either returns `result` on line 135 or raises `translated_exc` on line 160 when `attempt == max_attempts`. Line 162 can never be reached under any control flow.
- **Empirical Proof**: Code coverage output confirms line 162 is unexecuted (`Missing 162`).
- **Mitigation**: Remove unreachable line 162 or adjust the loop condition if default fallback exception is desired.

---

## 4. Empirical Stress Test Verification Table

| Test Category | Scenario | Expected Behavior | Actual Behavior | Result |
|---------------|----------|-------------------|-----------------|--------|
| Pytest Test Suite | 15 unit tests in `test_providers.py` | All tests pass | 15/15 Passed | **PASS** |
| Exponential Backoff | 1,000 delay calculation trials (Attempts 1-5) | Delays strictly bounded by `[0.5*capped, capped]` | Attempt 1: [0.50, 1.00]s, Attempt 5: [5.00, 10.00]s | **PASS** |
| Schema Validation Parity | Both providers map `VideoMetadata`, `EducationalPlan`, `RenderSegment` | Exact schema match across OpenAI & Anthropic | 100% Schema & Type Equality | **PASS** |
| Rate Limit Retry | 3 consecutive HTTP 429 failures | Retries 3 times, raises `RateLimitError` | 3 attempts executed, `RateLimitError` raised | **PASS** |
| Validation Immediate Halt | OutputParserException on attempt 1 | Immediately raises `ValidationError` without retrying | 1 attempt executed, halted immediately | **PASS** |
| Fallback Protocol | Primary OpenAI fails with 401 Auth error | Fallback Anthropic client succeeds | Returned canonical `VideoMetadata` | **PASS** |
| Multithread Concurrency | 20 parallel threads invoking `generate_structured` | No race conditions or state corruption | 20/20 threads succeeded | **PASS** |
| Input Prompt Boundary | `prompt = []`, `[HumanMessage("")]`, `12345`, `{}` | Raise `ValidationError` upfront | Bypassed validation, attempted execution | **FAIL** |
| Exception Mapping | Generic `Exception("RateLimitError...")`, `ValidationError`, HTTP 529 | Map to domain `RateLimitError`, `ValidationError`, `NetworkError` | Translated to `FatalError` | **FAIL** |

---

## 5. Unchallenged Areas

- **Live Provider Endpoints**: Live network tests against production OpenAI/Anthropic APIs were not executed due to missing live credentials (mocked testing per specification).
- **Streaming Response Processing**: Out of scope for Phase 06 structured generation.

---

## 6. Recommendations for Implementation Iteration 2

1. Update `src/core/llm/provider.py`:
   - Harden `generate_structured` input prompt validation for empty lists, message list types, and invalid prompt data types.
   - Symmetrize string keyword matching in `_translate_exception` across both `exc_name` and `exc_str`.
   - Add status code 529 (Anthropic overloaded) to retryable `NetworkError` status list.
   - Remove unreachable line 162.
2. Update `tests/llm/test_providers.py`:
   - Add unit test cases for empty list prompt `[]` and non-string/non-list prompt types asserting `ValidationError`.
   - Add unit test cases for generic wrapped exceptions (e.g. `Exception("ValidationError: ...")`) asserting proper domain translation.
   - Add test case for HTTP status 529.
