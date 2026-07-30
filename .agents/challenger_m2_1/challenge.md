# Milestone 2 Empirical Challenge Report: `test_animation_node.py`

**Target Subsystem**: `tests/pipeline/test_animation_node.py`, `src/pipeline/nodes/animation_generator_node.py`, `src/animation/renderer.py`  
**Challenger Role**: Empirical Challenger (`challenger_m2_1`)  
**Date**: 2026-07-30  
**Overall Verdict**: **REJECT** (Blocking findings: 1-byte corrupt cache file accepted as cache HIT, unsanitized `cue_id` path traversal risk, non-atomic cache write under concurrency).

---

## 1. Executive Summary

The `tests/pipeline/test_animation_node.py` test suite was evaluated against the Phase 12 Media Production (Animation) specifications. The existing test suite contains **34 test cases** covering CLI flag generation, file descriptor cleanup, temporary directory deletion, zero-byte cache handling, and visual cue mappings across all 8 scene types. All 34 tests in pytest pass cleanly.

However, empirical stress testing and edge-case probing using a custom test harness (`stress_harness.py`) revealed **3 significant vulnerabilities/defects**:
1. **Cache Poisoning via Non-Zero Corrupt Cache Files**: Cache lookup only checks `st_size > 0`. A 1-byte or corrupt non-zero `.mp4` file is treated as a valid Cache HIT and copied to output, bypassing re-rendering and outputting corrupted video artifacts.
2. **Unsanitized `cue_id` Path Traversal Risk**: `output_file = run_output_dir / f"segment_{cue_id}.mp4"` does not sanitize `cue_id`. A payload containing `cue_id="../filename"` creates output files outside the run output directory.
3. **Non-Atomic Cache Copy Race Condition**: In high-concurrency execution with shared cache directories, `shutil.copy2(output_file, cached_file)` is non-atomic. Parallel threads can read/copy partially written cache files.

---

## 2. Standard Test Suite Execution

Executed standard test suite via pytest:
```bash
pytest tests/pipeline/test_animation_node.py -v
```
**Results**:
- **Passed**: 34 tests
- **Failed**: 0 tests
- **Warnings**: 9 warnings (Pydantic V2 migration warnings in unrelated models)
- **Duration**: 2.82s
- **Code Coverage**: `src/pipeline/nodes/animation_generator_node.py` (90%), `src/animation/renderer.py` (91%)

---

## 3. Empirical Stress & Leak Verification

Using `.agents/challenger_m2_1/stress_harness.py`, the node was subjected to high-volume stress iterations and high-concurrency execution:

### 3.1 File Descriptor (FD) Leak Check
- **Method**: Ran 50 sequential pipeline executions of `AnimationGeneratorNode.execute()` with mock Manim binary. Measured open file descriptors in `/proc/self/fd` before and after.
- **Observation**:
  - Open FDs before 50 runs: `18`
  - Open FDs after 50 runs: `18`
  - Net FD Leak: **0 file descriptors** (VERIFIED SAFE).

### 3.2 Temporary Directory Sanitation
- **Method**: Verified `/tmp` directory after 50 normal runs, process timeouts, and non-zero process crashes.
- **Observation**:
  - Leftover `manim_*` temp directories: **0** (VERIFIED SAFE). `tempfile.TemporaryDirectory` context manager correctly unlinks temporary working directories under all termination modes.

---

## 4. Specific Challenge Findings & Vulnerabilities

### Finding 1 [HIGH]: 1-Byte Corrupt Cache File Accepted as Cache HIT
- **Component**: `AnimationGeneratorNode._render_or_get_cached_clip` (lines 275-278)
- **Observation**:
  ```python
  if cached_file.exists() and cached_file.stat().st_size > 0:
      logger.info("Cache HIT for cue_id=%s (hash=%s)", cue_id, cache_hash)
      shutil.copy2(cached_file, output_file)
      return output_file
  ```
- **Attack Scenario**: If a process crash, disk truncation, or interrupted write leaves a 1-byte file (or header-only corrupt MP4 file < 100 bytes) in `cache_dir`, `_render_or_get_cached_clip` treats it as a valid cache hit and copies it to `output_file`.
- **Impact**: Silent video rendering failure; invalid video artifact returned in `RenderSegment`.
- **Mitigation**: Validate cache files against a minimum valid MP4 threshold size (e.g. `st_size >= 512` bytes or MP4 magic bytes check `ftyp`).

---

### Finding 2 [MEDIUM]: Unsanitized `cue_id` Enables Path Traversal
- **Component**: `AnimationGeneratorNode.execute` (line 156)
- **Observation**:
  ```python
  output_file = run_output_dir / f"segment_{cue_id}.mp4"
  ```
- **Attack Scenario**: If an upstream script generator produces a payload with `cue_id = "../malicious_segment"`, `output_file` resolves to `run_output_dir / "segment_../malicious_segment.mp4"`, which writes into `run_output_dir.parent`.
- **Impact**: Files are created outside designated run directory; during cleanup on error (`f.unlink()`), unexpected files could be deleted.
- **Mitigation**: Sanitize `cue_id` using `Path(cue_id).name` or `re.sub(r'[^a-zA-Z0-9_-]', '_', cue_id)`.

---

### Finding 3 [MEDIUM]: Non-Atomic Cache Write Under Concurrency
- **Component**: `AnimationGeneratorNode._render_or_get_cached_clip` (line 293)
- **Observation**:
  ```python
  if output_file.exists() and output_file.stat().st_size > 0:
      shutil.copy2(output_file, cached_file)
  ```
- **Attack Scenario**: Under high-concurrency (multi-thread/multi-process worker nodes), two processes rendering the same visual cue simultaneously will both write to `cached_file` using non-atomic `shutil.copy2`. Process A may read `cached_file` while Process B is halfway through copying it.
- **Impact**: Intermittent corrupted cache files in multi-worker production deployments.
- **Mitigation**: Write to a temporary file in `cache_dir` first, then atomically move (`os.replace` or `Path.replace`).

---

### Finding 4 [LOW]: Unhandled Exceptions on Malformed Visual Cue Data
- **Component**: `AnimationGeneratorNode.execute` (lines 152-153)
- **Observation**:
  - `timestamp = float(cue.get("timestamp_seconds") or 0.0)` raises unhandled `ValueError` if `timestamp_seconds` is an invalid string (e.g. `"bad"`).
  - `parameters = cue.get("parameters") or {}` raises unhandled `AttributeError` if `parameters` is a string instead of a dict when accessing `parameters.get("duration")`.
- **Impact**: Unhandled python built-in exceptions instead of structured `PipelineStageError` or `AnimationError`.
- **Mitigation**: Add try-except parsing wrappers around float conversion and parameters type-checking.

---

## 5. Verification Commands

To independently reproduce all findings:

1. **Standard Pytest Suite**:
   ```bash
   pytest tests/pipeline/test_animation_node.py -v
   ```

2. **Empirical Stress & Edge-Case Harness**:
   ```bash
   python3 .agents/challenger_m2_1/stress_harness.py
   ```

---

## 6. Recommendations for Approval

To achieve **APPROVE** status for Milestone 2:
1. Update `_render_or_get_cached_clip` to validate minimum cache file size (`st_size >= 512`) and perform atomic writes to `cache_dir`.
2. Add sanitization for `cue_id` in `AnimationGeneratorNode`.
3. Add unit tests in `tests/pipeline/test_animation_node.py` specifically asserting rejection of 1-byte corrupt cache files and path traversal attempt handling.
