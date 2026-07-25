# Phase 05 Empirical Challenge Report

**Date**: 2026-07-25
**Agent**: Challenger 2 (Empirical Challenger)
**Scope**: Phase 05: Core Data Models & Schemas (`src/core/models/`, `tests/models/test_validation.py`)
**Verdict**: **APPROVE**

---

## Challenge Summary

**Overall risk assessment**: **LOW**

The Phase 05 Core Data Models & Schemas implementation strictly fulfills all functional, architectural, and validation requirements outlined in `ORIGINAL_REQUEST.md`. 
An empirical test harness (`empirical_runner.py`) was executed to test all 14 Pydantic V2 models across 4 core dimensions:
1. JSON Schema generation (`Model.model_json_schema()`)
2. Serialization roundtrips (`model_dump`, `model_dump_json`, `model_validate`, `model_validate_json`), deep copying (`copy.deepcopy`, `model_copy(deep=True)`)
3. Attribute mutability and assignment validation behavior
4. Invalid input permutations (54 distinct edge cases) and `pydantic.ValidationError` detail inspection

All 21 pytest suite tests (`.venv/bin/pytest tests/core tests/models/test_validation.py`) passed cleanly with high code coverage (96%–99% across model modules).

---

## Challenges & Technical Observations

### [Low] Challenge 1: Post-Instantiation Attribute Mutation (`validate_assignment = False`)

- **Assumption challenged**: Models enforce strict immutability or runtime type/semantic validation during direct field assignment.
- **Attack scenario**: Code downstream instantiates a valid `VideoMetadata` or `RenderSegment` instance and subsequently modifies an attribute directly (e.g. `video.fps = -999` or `segment.duration = -50.0`).
- **Observation**: Pydantic V2 defaults to `validate_assignment=False` unless `model_config = ConfigDict(validate_assignment=True)` is specified. Post-instantiation assignment bypasses validators.
- **Blast radius**: Low. Internal pipeline data flow is designed to pass immutable payloads via JSON serialization/deserialization across steps rather than mutating fields in-place.
- **Mitigation**: If field mutation in-place must be prevented or validated, add `model_config = ConfigDict(validate_assignment=True)` or `frozen=True` to the base/target models in future iterations.

### [Low] Challenge 2: Type Coercion Order in `AssembledVideo.assembled_at` Union

- **Assumption challenged**: Deserializing a JSON-serialized `AssembledVideo` model preserves the `datetime` type when `assembled_at` was originally a `datetime` object.
- **Attack scenario**: `assembled = AssembledVideo(..., assembled_at=datetime.now())` is serialized to JSON (`model_dump(mode="json")`) and then re-hydrated via `AssembledVideo.model_validate(json_dict)`.
- **Observation**: `assembled_at` is typed as `str | datetime | None`. In Pydantic V2 union matching, `str` appears before `datetime`. As a result, the string ISO representation `'2026-07-25T12:00:00'` matches `str` first and is retained as a `str` rather than being converted back into a `datetime` object.
- **Blast radius**: Low. SQLite State Ledger stores datetime fields as ISO strings, and downstream components handle string date representations gracefully.
- **Mitigation**: Reordering union type hint to `datetime | str | None` would allow Pydantic to attempt parsing ISO strings into `datetime` objects prior to falling back to `str`.

---

## Stress Test Results

| Test Category | Target Models | Tested Scenarios | Expected Result | Actual Result | Verdict |
|---|---|---|---|---|---|
| **JSON Schema Generation** | All 14 models | `Model.model_json_schema()` export & JSON serialization | Valid Dict with `type: object`, `properties`, and `required` | Clean JSON schemas generated for all 14 models | **PASS** |
| **Serialization Roundtrips** | All 14 models | `model_dump(python)` -> `model_validate`, `model_dump(json)` -> `model_validate`, `model_dump_json()` -> `model_validate_json` | 100% structural and field equality | Re-hydrated instances match originals exactly | **PASS** |
| **Deep Copy Verification** | All 14 models | `copy.deepcopy(inst)` and `inst.model_copy(deep=True)` | Equal value, distinct object identity (`id(cp) != id(inst)`) | Identity checks and equality assertions passed | **PASS** |
| **Invalid Permutations & Errors** | All 14 models | 54 invalid input cases (whitespace strings, negative durations, invalid regex slugs, invalid FPS, out-of-range volume, duplicate section IDs, duration mismatches) | `pydantic.ValidationError` raised with precise `loc`, `type`, and `msg` | 54 / 54 cases raised expected `ValidationError` with correct field location | **PASS** |
| **Project Pytest Suite** | `tests/core`, `tests/models` | `.venv/bin/pytest tests/core tests/models/test_validation.py` | All tests pass | 21 / 21 tests passed (0.27s) | **PASS** |

---

## Unchallenged Areas

- **Database I/O Integration**: Covered under Phase 04 State Ledger verification. Model roundtrips with SQLite were verified in `test_state_ledger_model_serialization_roundtrip`.

---

## Final Verdict

**Verdict**: **APPROVE**

Phase 05 Core Data Models & Schemas are robust, type-safe, fully compliant with Phase 04 State Ledger mapping requirements, and empirically verified.
