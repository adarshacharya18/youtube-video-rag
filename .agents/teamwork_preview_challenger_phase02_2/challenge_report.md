# Phase 02 Knowledge Ingestion - Adversarial Challenge Report

## Challenge Summary

**Overall risk assessment**: LOW

All primary requirements for data model immutability, serialization round-trips, fail-fast validation, and parser fuzzing were empirically validated. 8 out of 8 test cases in the adversarial test suite passed. Two subtle edge-case behaviors were discovered and documented.

---

## Challenges

### [Low] Challenge 1: In-Place Container Mutation in Frozen Dataclass
- **Assumption challenged**: Standard `@dataclass(frozen=True)` on `ScrapedProblem` guarantees complete immutability of the instance.
- **Attack scenario**: Code calling `problem.tags.append("mutated")`, `problem.constraints.clear()`, or `problem.examples.pop()` mutates internal container lists in-place without triggering `FrozenInstanceError`.
- **Blast radius**: Low. Standard field reassignments (`problem.tags = [...]`) are blocked by Python dataclasses, but internal list references can be altered in-place if passed between components.
- **Mitigation**: Convert `tags`, `constraints`, and `examples` fields to tuples (`Tuple[str, ...]`) or return defensive copies in `to_dict()`.

### [Low] Challenge 2: Title Post-Cleaning Validation Gap in `sanitize_problem`
- **Assumption challenged**: Sanitizer validates title completeness before attempting slug generation.
- **Attack scenario**: Payload with `raw_title = "### "` passes `if not raw_title` check (since `"### "` is non-empty string), cleans to `title = ""`, and continues to slug generation where it raises `ValueError("Problem slug is required and could not be derived from title")`.
- **Blast radius**: Low. The sanitizer still fails fast with `ValueError`, but the exception message identifies slug derivation as the cause rather than title post-clean emptiness.
- **Mitigation**: Add `if not title:` validation immediately after `title = cls.clean_title(str(raw_title))`.

---

## Stress Test Results

| Test Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| Frozen attribute reassignment (`problem.title = "x"`) | Raise `FrozenInstanceError` | `FrozenInstanceError` raised for all 11 fields | **PASS** |
| Container list mutation (`problem.tags.append(...)`) | List mutation behavior tested | List modified in-place (Python dataclass limitation) | **OBSERVED** |
| JSON `to_dict()` / `from_dict()` round-trip | Loss-less reconstruction | All fields (types, enums, lists, code) 100% faithful | **PASS** |
| `Difficulty` enum parsing & HTML cleaning | Parse `"easy"`, `"med"`, `"<b>Med</b>"` | Resolves correctly to `Difficulty` enum members | **PASS** |
| Invalid difficulty injection (`"Extreme"`, `123`, `None`) | Raise `ValueError` | `ValueError` raised consistently | **PASS** |
| Default `scraped_at` ISO generation | ISO timestamp created | Valid ISO-8601 string created when missing | **PASS** |
| Malformed root payload injections (`str`, `list`, `None`) | Raise `ValueError` | `ValueError("Expected dictionary...")` raised | **PASS** |
| Missing required fields (title, number, desc, code) | Fail-fast `ValueError` | `ValueError` raised for all missing required fields | **PASS** |
| Fuzzing 50 random strings into `DSAParser` | No unexpected crashes | Handled safely; zero uncaught exceptions | **PASS** |
| Pathological markdown (HTML bombs, 1000 lines, unclosed fences) | No infinite loops / recursion errors | Parsed safely | **PASS** |

---

## Unchallenged Areas

- Network scraping client (`src/scraper/client.py`) — Out of scope (focused on ingestion models & parser).
