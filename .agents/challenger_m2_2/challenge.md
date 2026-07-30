# Adversarial Challenge Report — Milestone 2 Visual Cue Mapping & Caching Behavior

## Challenge Summary

**Overall risk assessment**: LOW

The visual cue mapping, SHA-256 render caching mechanism, and fallback visual cue extraction logic in `src/pipeline/nodes/animation_generator_node.py` and `tests/pipeline/test_animation_node.py` are robust, reliable, and thoroughly tested. All 34 tests in `tests/pipeline/test_animation_node.py` pass cleanly. Empirical stress-testing verified that cache keys invalidate predictably upon parameter/quality changes, all 21 mapped visual cue types map to valid on-disk Manim scene files and classes, and fallback cue extraction handles various malformed/partially validated script payloads gracefully.

---

## Challenges & Findings

### [Low] Challenge 1: Case Sensitivity in `ANIMATION_TYPE_MAP` Lookup

- **Assumption challenged**: `ANIMATION_TYPE_MAP` matches animation types regardless of casing.
- **Attack scenario**: If an upstream prompt or script generator produces uppercase or title-cased cue types (e.g., `"ARRAY_HIGHLIGHT"` or `"Tree_Traversal"`), `ANIMATION_TYPE_MAP.get(anim_type)` returns `None` because the map keys are all lower snake_case strings (`"array_highlight"`, `"tree_traversal"`).
- **Blast radius**: The node falls back to `DEFAULT_SCENE` (`ArrayScene`) instead of raising an error or routing to the specialized scene class (`TreeScene`, `CodeScene`, etc.).
- **Mitigation**: While Pydantic schemas and standard generator nodes enforce lower snake_case (`array_highlight`), normalizing lookup via `anim_type.lower()` prior to dictionary get would make the lookup case-insensitive and even more resilient.

---

### [Low] Challenge 2: Cache Key Hashing on Float vs Int Parameter Types

- **Assumption challenged**: Semantically equivalent parameter representations (e.g., `{"duration": 5}` vs `{"duration": 5.0}`) yield the same SHA-256 cache key.
- **Attack scenario**: If a script section generates integer parameters (`5`) in one run and float parameters (`5.0`) in another, `json.dumps({"duration": 5}, sort_keys=True)` produces `'{"duration": 5}'` vs `'{"duration": 5.0}'`, producing distinct SHA-256 cache hashes.
- **Blast radius**: Triggers a cache miss and re-renders the scene clip rather than reusing the cache hit.
- **Mitigation**: Purely a performance inefficiency (cache miss), not a functional failure or state corruption. Rendering completes correctly and stores the new clip under the float hash.

---

## Stress Test Results

| Scenario / Test Case | Expected Behavior | Actual Behavior | Result |
|----------------------|-------------------|-----------------|--------|
| **Pytest Selective Execution** (`-k "mapping or cache or fallback"`) | Execute 13 mapping, caching, and fallback tests | 13 passed, 21 deselected | PASS |
| **Pytest Full Execution** (`tests/pipeline/test_animation_node.py`) | All node tests pass successfully | 34 passed, 0 failed in 2.52s | PASS |
| **Visual Cue Mapping Inspection** (All 21 map entries) | Map targets point to existing files and valid class names | All 21 mappings point to existing `.py` files containing target classes | PASS |
| **Unknown Animation Type Fallback** | Fall back gracefully to `DEFAULT_SCENE` (`ArrayScene`) | Successfully maps to `ArrayScene` without crashing | PASS |
| **Cache Invalidation on Parameter Change** | Modified parameters change SHA-256 hash and trigger subprocess re-render | `h1 != h3`, cache miss verified via non-existent mock binary raising `AnimationError` | PASS |
| **Cache Key Key-Order Invariance** | Dicts with different key order produce identical hash | `sort_keys=True` ensures `h1 == h2` | PASS |
| **Cache Key Quality Invalidation** | Changing quality (`low` vs `medium`) invalidates hash | `h1 != h5`, cache miss triggered | PASS |
| **Zero-Byte Corrupt Cache Recovery** | 0-byte cache file ignored, re-rendered, and overwritten | Re-renders clip, updates file to >0 bytes | PASS |
| **Fallback Cue Extraction (Malformed Model)** | Extract visual cues from section dicts when model validation fails | Successfully extracts 4 section cues (`cue_hook`, `cue_ctx`, `cue_sol`, `cue_comp`) | PASS |
| **Fallback Cue Extraction (Top-Level Fallback)** | Extract top-level `visual_cues` when model validation fails | Successfully extracts `visual_cues` list | PASS |
| **Direct / Unwrapped Payload Extraction** | Extract cues when payload has top-level `visual_cues` outside `script` | Successfully extracts 1 direct cue | PASS |

---

## Unchallenged Areas

- **Actual Manim CLI Binary Execution**: Verified via python script mock binary as per test suite design. Real Manim rendering depends on system ffmpeg and cairo dependencies, which is outside the isolated unit test scope.
- **SQLite StateLedger Concurrency**: Single-threaded synchronous batch pipeline as defined in PROJECT.md architecture.
