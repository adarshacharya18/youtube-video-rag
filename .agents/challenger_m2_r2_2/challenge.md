# Empirical Challenge Report: Cue Mapping, Scene Generation & Caching Behavior

**Milestone**: Milestone 2 Iteration 2  
**Target Modules**: `src/pipeline/nodes/animation_generator_node.py`, `tests/pipeline/test_animation_node.py`  
**Challenger**: challenger_m2_r2_2  

---

## Challenge Summary

**Overall Risk Assessment**: **LOW**  
All cue mapping, scene generation, fallbacks, and caching mechanisms in `AnimationGeneratorNode` have been empirically tested and verified. All 21 entries in `ANIMATION_TYPE_MAP` map cleanly to existing scene templates on disk and execute successfully. Caching mechanics correctly invalidate on parameter or quality level changes while reusing cached video artifacts on exact matches.

---

## Challenge Activities & Empirical Verification

### Activity 1: Pytest Filtered Test Suite Execution
- **Command**: `pytest tests/pipeline/test_animation_node.py -k "mapping or cache or fallback" -v`
- **Result**: **15 PASSED**, 22 deselected (0 failures) in 2.07s.
- **Full Node Test Suite**: `pytest tests/pipeline/test_animation_node.py -v`
- **Result**: **37 PASSED** (0 failures) in 2.71s.
- **Pipeline Dir Test Suite**: `pytest tests/pipeline/ -v`
- **Result**: **50 PASSED** (0 failures) in 2.78s.

### Activity 2: Verification of ANIMATION_TYPE_MAP (21 Entries)
Verified that `ANIMATION_TYPE_MAP` contains exactly 21 mapping entries and every entry resolves to an existing file and class on disk:

| # | Animation Type | Scene Template File | Scene Class | Disk File Exists |
|---|----------------|---------------------|-------------|------------------|
| 1 | `array_highlight` | `src/animation/scenes/array_scene.py` | `ArrayScene` | True |
| 2 | `array_traversal` | `src/animation/scenes/array_scene.py` | `ArrayScene` | True |
| 3 | `tree_traversal` | `src/animation/scenes/tree_scene.py` | `TreeScene` | True |
| 4 | `binary_tree` | `src/animation/scenes/tree_scene.py` | `TreeScene` | True |
| 5 | `code_highlight` | `src/animation/scenes/code_scene.py` | `CodeScene` | True |
| 6 | `code_walkthrough` | `src/animation/scenes/code_scene.py` | `CodeScene` | True |
| 7 | `code_scene` | `src/animation/scenes/code_scene.py` | `CodeScene` | True |
| 8 | `graph_animation` | `src/animation/scenes/graph_scene.py` | `GraphScene` | True |
| 9 | `graph_traversal` | `src/animation/scenes/graph_scene.py` | `GraphScene` | True |
| 10 | `hashmap_operation` | `src/animation/scenes/hashmap_scene.py` | `HashmapScene` | True |
| 11 | `hashmap_insert` | `src/animation/scenes/hashmap_scene.py` | `HashmapScene` | True |
| 12 | `hashmap_lookup` | `src/animation/scenes/hashmap_scene.py` | `HashmapScene` | True |
| 13 | `hashmap` | `src/animation/scenes/hashmap_scene.py` | `HashmapScene` | True |
| 14 | `linkedlist_pointer` | `src/animation/scenes/linkedlist_scene.py` | `LinkedListScene` | True |
| 15 | `linked_list` | `src/animation/scenes/linkedlist_scene.py` | `LinkedListScene` | True |
| 16 | `linkedlist` | `src/animation/scenes/linkedlist_scene.py` | `LinkedListScene` | True |
| 17 | `linkedlist_operation` | `src/animation/scenes/linkedlist_scene.py` | `LinkedListScene` | True |
| 18 | `stack_queue_operation` | `src/animation/scenes/stack_queue_scene.py` | `StackQueueScene` | True |
| 19 | `stack_queue` | `src/animation/scenes/stack_queue_scene.py` | `StackQueueScene` | True |
| 20 | `complexity_chart` | `src/animation/scenes/complexity_scene.py` | `ComplexityScene` | True |
| 21 | `complexity` | `src/animation/scenes/complexity_scene.py` | `ComplexityScene` | True |

**Execution Verification**: Constructed a script passing all 21 visual cue types in a single pipeline run to `AnimationGeneratorNode`. All 21 segments rendered successfully with valid output files (> 100 bytes) created in the run output directory.

### Activity 3: Cache Key Invalidation & Reuse Testing
Tested SHA-256 hash calculation logic: `hashlib.sha256(f"{anim_type}:{json.dumps(parameters, sort_keys=True)}:{self.quality}".encode("utf-8")).hexdigest()`.

1. **Quality Level Invalidation**:
   - `low` -> `4973e4265dd5ca565f6e0bdc4f4ae5e645a2a1ed0c73a3a47e12222122b36173`
   - `medium` -> `1ea052ccdc12b0c023107c5ad7f991430b213c7fab66db2505ee2c50fcf55a6f`
   - `high` -> `c98cf9a56eb953df2a74de26bcaafe5999f6f0c31f50e6fea7883ef92ed7e849`
   - `fourk` -> `91b7d9ac2de8e802c496f90fb5a6d246452d7222d150158b4f7742bfd4e0343d`
   - Verified that changing quality forces a Cache MISS and creates a distinct cached video artifact.

2. **Parameter Change Invalidation**:
   - Modifying parameter values (e.g. `{"array": [1, 2]}` vs `{"array": [3, 4]}`) produces distinct hashes, invalidating cache.
   - Adding or removing parameter keys produces distinct hashes.

3. **Key Order Stability (Cache HIT)**:
   - `{"b": 2, "a": 1}` and `{"a": 1, "b": 2}` produce identical hashes due to `sort_keys=True`, guaranteeing proper cache hits regardless of key insertion order.

4. **Corrupt / Sub-100 Byte Cache File Invalidation**:
   - Sub-100 byte or 0-byte corrupt files in `cache_dir` are automatically detected, unlinked, and re-rendered atomically.

---

## Stress Testing & Adversarial Checks

| Scenario | Expected Behavior | Actual Behavior | Result |
|----------|-------------------|-----------------|--------|
| Filtered Pytest run | 15 passed for mapping/cache/fallback | 15 passed | **PASS** |
| All 21 ANIMATION_TYPE_MAP entries | All target scene files exist on disk | 21/21 files exist | **PASS** |
| Node execution with all 21 cue types | Generates 21 valid RenderSegments | 21 segments generated (>100B each) | **PASS** |
| Cache hit on identical inputs | Skips subprocess render | Render skipped, returns cached file | **PASS** |
| Quality change invalidation | Triggers re-render with new hash | 2 distinct cache files created | **PASS** |
| Param change invalidation | Triggers re-render with new hash | Distinct cache files created | **PASS** |
| Key order variation | Identical hash via sort_keys=True | Identical hash generated | **PASS** |
| Cue ID path traversal attack (`../../etc/passwd`) | Sanitized to safe filename in run dir | `segment_passwd.mp4` in run output dir | **PASS** |
| Subprocess failure / timeout tempdir cleanup | Cleans temporary directory completely | Temporary parent directory is 100% empty | **PASS** |

---

## Verdict

**APPROVE**
