# Phase 05 Core Data Models & Schemas — Adversarial Challenge Report

## Challenge Summary

**Overall risk assessment**: MEDIUM

Empirical adversarial stress testing was conducted on Phase 05 Pydantic V2 models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`, and associated submodels) and the SQLite State Ledger (`StateLedger`).

The official test suite (`.venv/bin/pytest tests/models/test_validation.py`) passes 100% (7/7 tests). Pydantic V2 models reliably raise `ValidationError` for standard malformed JSON, invalid types, invalid slugs, disallowed FPS, duplicate section IDs, and negative durations, without crashing with unhandled system exceptions (`AttributeError`, `KeyError`, `RecursionError`).

However, custom adversarial empirical stress testing revealed a **Medium-severity validation bypass vulnerability** related to floating-point infinity (`float('inf')`) math in duration invariant checks, along with minor whitespace validation gaps in string list fields.

---

## Challenges

### [Medium] Challenge 1: `float('inf')` Duration Input Bypasses Invariant Validation

- **Assumption challenged**: Pydantic's `Field(..., gt=0.0)` constraint and custom `@model_validator` checks prevent infinite-duration plans and render segments from entering the pipeline.
- **Attack scenario**: An input payload specifies `estimated_duration = float('inf')` (or JSON `1e9999` / `Infinity`) for plan sections and `estimated_total_duration = float('inf')` for `EducationalPlan` (or `end_time = float('inf')` and `duration = float('inf')` for `RenderSegment`).
  - In Python, `float('inf') > 0.0` evaluates to `True`, so field-level `gt=0.0` validation passes.
  - In `EducationalPlan.validate_plan_invariants`, the check calculates `sum_durations = sum(sec.estimated_duration for sec in self.sections)` (which equals `inf`).
  - The invariant check then evaluates `abs(self.estimated_total_duration - sum_durations) > 0.1`. In Python float math, `inf - inf` evaluates to `nan`.
  - In Python float comparisons, `abs(nan) > 0.1` evaluates to `False`.
  - Consequently, the validator `if abs(...) > 0.1:` condition evaluates to `False`, allowing an invalid `EducationalPlan` with infinite durations to bypass validation without raising a `ValidationError`.
- **Blast radius**: Downstream rendering components (Manim / FFmpeg / TTS audio generator) will encounter `inf` or `nan` during timeline positioning and segment rendering, leading to unhandled runtime failures or infinite loops during audio/video compilation.
- **Mitigation**:
  1. Add `math.isfinite(v)` checks or `allow_inf=False` to all float duration/timing fields in `PlanSection`, `EducationalPlan`, `RenderSegment`, `AssetReference`, `AudioAsset`, `VideoAsset`, `RenderManifest`, and `AssembledVideo`.
  2. Explicitly validate that section durations and total durations are finite numbers before performing subtraction.

```python
# Recommended mitigation in plan.py / assets.py:
@field_validator("estimated_duration")
@classmethod
def validate_finite_duration(cls, v: float) -> float:
    if not math.isfinite(v) or v <= 0:
        raise ValueError("Duration must be a positive finite number")
    return v
```

---

### [Low] Challenge 2: Whitespace-Only String Items in `tags` and `prerequisites`

- **Assumption challenged**: String list elements are strictly validated for non-whitespace content.
- **Attack scenario**: Passing `tags=["   ", "\t\n"]` to `VideoMetadata` or `SEOMetadata`, or `prerequisites=["   "]` to `EducationalPlan`.
- **Blast radius**: Minor metadata pollution in YouTube tags or educational prerequisites.
- **Mitigation**: Add `@field_validator` on `tags` and `prerequisites` to assert every string element in the list is non-empty after `strip()`.

---

## Stress Test Results

| Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| Pytest suite execution (`tests/models/test_validation.py`) | 7/7 tests pass | 7/7 tests passed (0.25s) | PASS |
| Unicode, emojis, CJK, RTL, diacritics, null bytes in metadata | Correctly preserved & serialized | Preserved & serialized cleanly | PASS |
| Malformed types, invalid slug patterns, disallowed FPS (29) | Raise `ValidationError` | `ValidationError` raised | PASS |
| Deeply nested dicts (100 levels) | Handle cleanly without RecursionError | Handled cleanly | PASS |
| Large payload EducationalPlan (1,000 sections) | Validate & instantiate | Validated in <0.05s | PASS |
| SQLite State Ledger WAL mode & 1MB payloads | Transaction safe, no data corruption | Written and re-hydrated 100% match | PASS |
| State Ledger Foreign Key violation (invalid run_id) | Raise `PipelineError` | `PipelineError` raised | PASS |
| `float('nan')` in `gt=0.0` float fields | Raise `ValidationError` | `ValidationError` raised (`nan > 0` is False) | PASS |
| `float('inf')` in section & total duration fields | Raise `ValidationError` | Validation bypassed (`inf - inf = nan`) | FAIL |

---

## Unchallenged Areas

- **Manim rendering execution**: Out of scope for Phase 05 (Phase 05 covers Pydantic V2 data models & SQLite State Ledger only).
- **FFmpeg assembly execution**: Out of scope for Phase 05.
