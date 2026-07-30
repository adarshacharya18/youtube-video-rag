# Remediation Strategy & Analysis: Animation Generator Subsystem

**Target Subsystem**: `src/pipeline/nodes/animation_generator_node.py`  
**Test Suite**: `tests/pipeline/test_animation_node.py`  
**Author**: `explorer_m2_r2_1`  
**Date**: 2026-07-30  
**Iteration**: Milestone 2 Iteration 2  

---

## 1. Executive Summary

During Milestone 2 Iteration 1, empirical stress testing by `challenger_m2_1` identified **3 vulnerabilities** in `AnimationGeneratorNode`:
1. **Corrupt Cache Poisoning**: Sub-100 byte corrupt files (e.g. 1-byte partial writes) in `cache_dir` were treated as valid Cache HITs, returning corrupt video artifacts without re-rendering.
2. **`cue_id` Path Traversal Vulnerability**: Raw `cue_id` values were directly concatenated into file paths (`run_output_dir / f"segment_{cue_id}.mp4"`), allowing path traversal payloads (e.g. `../`) to write files outside `run_output_dir`.
3. **Non-Atomic Cache Copy Race Condition**: Direct `shutil.copy2` writes to shared cache files caused race conditions and partial file exposures under concurrent execution.

This document details the exact root causes, security impact, architectural fix design, and complete implementation specifications for both `src/pipeline/nodes/animation_generator_node.py` and `tests/pipeline/test_animation_node.py`.

---

## 2. Vulnerability Analysis & Technical Remediation Strategy

### 2.1 Vulnerability 1: Corrupt Cache Validation (Sub-100 Byte Files)

#### Root Cause
In `src/pipeline/nodes/animation_generator_node.py`:
```python
# Lines 275-278 (BEFORE)
if cached_file.exists() and cached_file.stat().st_size > 0:
    logger.info("Cache HIT for cue_id=%s (hash=%s)", cue_id, cache_hash)
    shutil.copy2(cached_file, output_file)
    return output_file
```
The existence and size check `st_size > 0` accepts any non-zero byte file (e.g., 1 byte from interrupted write or corrupted header).

#### Remediation Strategy
1. Introduce a helper method `_is_valid_video_file(file_path: Path) -> bool` that verifies:
   - File exists on disk.
   - File size is **at least 100 bytes** (`file_path.stat().st_size >= 100`).
   - File can be opened in binary mode and first 100 bytes can be read without raising an exception.
2. In `_render_or_get_cached_clip`:
   - Check cache hits using `_is_valid_video_file(cached_file)`.
   - If `cached_file.exists()` is true but `_is_valid_video_file(cached_file)` returns `False`, log a warning indicating a corrupt cache file was detected, unlink/delete the corrupt file, and trigger a **Cache MISS**.
   - After rendering, validate `output_file` using `_is_valid_video_file(output_file)`. If invalid, raise `AnimationError("Manim render completed for cue '{cue_id}' but produced no valid video artifact (file missing or < 100 bytes)").`

---

### 2.2 Vulnerability 2: `cue_id` Path Traversal Sanitization

#### Root Cause
In `src/pipeline/nodes/animation_generator_node.py`:
```python
# Line 156 (BEFORE)
output_file = run_output_dir / f"segment_{cue_id}.mp4"
```
When `cue_id` contains path traversal sequences like `../malicious_segment` or `../../etc_passwd`, `run_output_dir / f"segment_{cue_id}.mp4"` resolves to a path outside `run_output_dir`.

#### Remediation Strategy
1. Introduce a helper method `_sanitize_cue_id(cue_id: Any) -> str`:
   - Convert `cue_id` to string and extract `Path(str(cue_id)).name` to discard leading directory components.
   - Replace directory traversal sequences (`..`), slashes (`/`), and backslashes (`\`) with underscores (`_`).
   - Use regular expression substitution (`re.sub(r'[^a-zA-Z0-9_-]', '_', clean_id)`) to enforce an alphanumeric/underscore/hyphen strict safe character set.
   - Fall back to `"cue_safe"` if sanitization yields an empty string.
2. Apply `safe_cue_id = self._sanitize_cue_id(raw_cue_id)` when constructing:
   - Output filename: `output_file = run_output_dir / f"segment_{safe_cue_id}.mp4"`
   - Segment IDs and Asset IDs: `seg_id = f"seg_{safe_cue_id}"`, `asset_id = f"asset_{safe_cue_id}"`
   - Temporary directory prefix: `tempfile.TemporaryDirectory(prefix=f"manim_{safe_cue_id}_", ...)`
3. Add a defense-in-depth path containment assertion:
   - Verify `output_file.resolve().is_relative_to(run_output_dir.resolve())`.

---

### 2.3 Vulnerability 3: Atomic Cache Writes

#### Root Cause
In `src/pipeline/nodes/animation_generator_node.py`:
```python
# Line 293 (BEFORE)
if output_file.exists() and output_file.stat().st_size > 0:
    shutil.copy2(output_file, cached_file)
```
Direct `shutil.copy2` to `cached_file` is non-atomic. If multiple worker processes or threads render the same visual cue concurrently, one process may read or overwrite `cached_file` while another process is halfway through writing it.

#### Remediation Strategy
1. Use an atomic write pattern in `self.cache_dir`:
   - Copy `output_file` to a temporary file in `self.cache_dir`: `tmp_cache_file = self.cache_dir / f"{cache_hash}_{os.getpid()}.tmp"`
   - Atomically move/replace the temporary file to `cached_file` using `os.replace(tmp_cache_file, cached_file)`.
   - In `try/finally` or `except`, ensure `tmp_cache_file` is unlinked if replacement fails.
2. Under POSIX filesystem semantics, `os.replace` within the same directory (`self.cache_dir`) is guaranteed to be an atomic operation. Concurrent readers will only ever observe the original state or the fully replaced valid file.

---

### 2.4 Vulnerability 4: Robust Type Parsing & Defensive Handling

#### Root Cause
In `AnimationGeneratorNode.execute`:
- `timestamp = float(cue.get("timestamp_seconds") or 0.0)` raises unhandled `ValueError` if `timestamp_seconds` is non-numeric string (e.g. `"bad"`).
- `parameters = cue.get("parameters") or {}` raises unhandled `AttributeError` if `parameters` is a string instead of a dict.

#### Remediation Strategy
Wrap float conversion and parameter dictionary accesses in defensive try/except handlers defaulting to safe values (`0.0` for timestamp, `{}` for parameters, `5.0` for duration).

---

## 3. Exact Implementation Specifications

### 3.1 Changes to `src/pipeline/nodes/animation_generator_node.py`

#### Imports Section (Lines 8-15)
Add `os` and `re`:
```python
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional, Union
```

#### Helper Methods to Add to `AnimationGeneratorNode`
```python
    def _sanitize_cue_id(self, cue_id: Any) -> str:
        """Sanitize cue_id to prevent path traversal and filesystem escape."""
        if not cue_id:
            return "cue_safe"
        clean_id = Path(str(cue_id)).name
        clean_id = clean_id.replace("..", "_").replace("/", "_").replace("\\", "_")
        clean_id = re.sub(r'[^a-zA-Z0-9_-]', '_', clean_id).strip("_")
        return clean_id if clean_id else "cue_safe"

    def _is_valid_video_file(self, file_path: Path) -> bool:
        """Validate that video file exists, is at least 100 bytes, and has a readable header."""
        if not file_path.exists():
            return False
        try:
            if file_path.stat().st_size < 100:
                return False
            with open(file_path, "rb") as f:
                header = f.read(100)
                if len(header) < 100:
                    return False
            return True
        except Exception:
            return False
```

#### Refactored `execute` Processing Loop
```python
            # 3. Process each visual cue
            for idx, cue in enumerate(visual_cues):
                raw_cue_id = cue.get("cue_id", f"cue_{idx:02d}")
                cue_id = self._sanitize_cue_id(raw_cue_id)
                anim_type = cue.get("animation_type", "array_highlight")
                
                try:
                    timestamp = float(cue.get("timestamp_seconds") or 0.0)
                except (ValueError, TypeError):
                    timestamp = 0.0

                raw_params = cue.get("parameters")
                parameters = raw_params if isinstance(raw_params, dict) else {}
                
                try:
                    duration = float(parameters.get("duration") or 5.0)
                except (ValueError, TypeError):
                    duration = 5.0

                output_file = run_output_dir / f"segment_{cue_id}.mp4"
                
                # Verify output file path stays within run output directory
                if not output_file.resolve().is_relative_to(run_output_dir.resolve()):
                    raise AnimationError(f"Invalid cue_id '{raw_cue_id}' escapes run output directory")

                # Check cache or render clip
                video_path = self._render_or_get_cached_clip(
                    cue_id=cue_id,
                    anim_type=anim_type,
                    parameters=parameters,
                    output_file=output_file,
                )
                created_files.append(output_file)

                start_time = timestamp
                end_time = start_time + duration

                # Construct AssetReference & RenderSegment
                asset_ref = AssetReference(
                    asset_id=f"asset_{cue_id}",
                    asset_type="video",
                    file_path=str(video_path),
                    duration=duration,
                )

                segment = RenderSegment(
                    segment_id=f"seg_{cue_id}",
                    segment_type="visual_anim",
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    asset_references=[asset_ref],
                    visual_path=str(video_path),
                    scene_type=anim_type.upper(),
                    visual_parameters=parameters,
                )
                render_segments.append(segment)
```

#### Refactored `_render_or_get_cached_clip` Method
```python
    def _render_or_get_cached_clip(
        self,
        cue_id: str,
        anim_type: str,
        parameters: Dict[str, Any],
        output_file: Path,
    ) -> Path:
        """Check cache hit or launch Manim subprocess rendering with isolated temp dir."""
        cache_hash = self._compute_cache_hash(anim_type, parameters)
        cached_file = self.cache_dir / f"{cache_hash}.mp4"

        # Check Cache HIT with >= 100 byte & header validation
        if self._is_valid_video_file(cached_file):
            logger.info("Cache HIT for cue_id=%s (hash=%s)", cue_id, cache_hash)
            tmp_output = output_file.parent / f"{output_file.name}.tmp"
            try:
                shutil.copy2(cached_file, tmp_output)
                os.replace(tmp_output, output_file)
            except Exception:
                if tmp_output.exists():
                    try:
                        tmp_output.unlink()
                    except Exception:
                        pass
                shutil.copy2(cached_file, output_file)
            return output_file

        if cached_file.exists():
            logger.warning(
                "Corrupt or sub-100 byte cache file detected for cue_id=%s (hash=%s, size=%d bytes). Replacing.",
                cue_id,
                cache_hash,
                cached_file.stat().st_size,
            )
            try:
                cached_file.unlink()
            except Exception:
                pass

        logger.info("Cache MISS: Rendering cue_id=%s (anim_type=%s)", cue_id, anim_type)

        # Isolated temporary directory context management
        parent_temp = str(self.explicit_temp_dir) if self.explicit_temp_dir else None
        if self.explicit_temp_dir:
            self.explicit_temp_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix=f"manim_{cue_id}_", dir=parent_temp) as temp_dir_str:
            temp_dir_path = Path(temp_dir_str)
            self._invoke_manim_subprocess(cue_id, anim_type, parameters, output_file, temp_dir_path)

        # Validate rendered output file and save to cache atomically
        if self._is_valid_video_file(output_file):
            tmp_cache_file = self.cache_dir / f"{cache_hash}_{os.getpid()}.tmp"
            try:
                shutil.copy2(output_file, tmp_cache_file)
                os.replace(tmp_cache_file, cached_file)
            except Exception as e:
                if tmp_cache_file.exists():
                    try:
                        tmp_cache_file.unlink()
                    except Exception:
                        pass
                logger.warning("Failed atomic cache write for hash %s: %s", cache_hash, e)
                shutil.copy2(output_file, cached_file)
        else:
            raise AnimationError(
                f"Manim render completed for cue '{cue_id}' but produced no valid video artifact (file missing or < 100 bytes)"
            )

        return output_file
```

---

### 3.2 Changes to `tests/pipeline/test_animation_node.py`

#### 1. Updating Mock Scripts to Generate >= 100 Bytes
In `test_animation_node.py`, all mock scripts writing video bytes must be updated to produce at least 100 bytes (e.g. `b"MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5` = 175 bytes):

- **Fixture `mock_manim_script` (line 52)**:
  Replace `f.write(b"MOCK_VIDEO_DATA_FOR_TESTING")` with:
  `f.write(b"MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5)`
- **`test_animation_node_writes_parameters_json_to_temp_dir` (line 453)**:
  Replace `f.write(b"MP4_DATA")` with:
  `f.write(b"MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5)`
- **`test_partial_output_cleanup_on_midway_failure` (line 579)**:
  Replace `f.write(b"MP4_DATA")` with:
  `f.write(b"MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5)`
- **`test_cli_flags_and_command_array_construction` (lines 808, 862)**:
  Replace `out_path.write_bytes(b"MOCK_VIDEO_DATA")` with:
  `out_path.write_bytes(b"MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5)`
- **`test_subprocess_invocation_kwargs` (line 930)**:
  Replace `out_path.write_bytes(b"MOCK_VIDEO_DATA")` with:
  `out_path.write_bytes(b"MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5)`

#### 2. Adding Unit Tests for the 3 Vulnerability Fixes

Add the following 3 new test functions to `tests/pipeline/test_animation_node.py`:

```python
def test_corrupt_sub_100_byte_cache_file_ignored_and_replaced(temp_ledger, mock_manim_script, tmp_path):
    """Verify sub-100 byte corrupt cache file is ignored as cache miss, re-rendered, and replaced in cache."""
    out_dir = tmp_path / "renders"
    cache_dir = tmp_path / "cache"

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    cue_params = {"test_key": "corrupt_test"}
    cache_hash = node._compute_cache_hash("array_highlight", cue_params)
    cache_dir.mkdir(parents=True, exist_ok=True)
    corrupt_cache_file = cache_dir / f"{cache_hash}.mp4"
    # Write a 1-byte corrupt file
    corrupt_cache_file.write_bytes(b"X")

    run_id = temp_ledger.create_run(slug="corrupt-cache-test")
    script_payload = {
        "slug": "corrupt-cache-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_corrupt_sub100",
                    "animation_type": "array_highlight",
                    "parameters": cue_params,
                }
            ]
        },
    }
    s1 = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(s1, output_payload=script_payload)

    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"
    # Assert corrupt cache file was replaced and now has size >= 100 bytes
    assert corrupt_cache_file.stat().st_size >= 100, f"Cache file size should be >= 100 bytes, got {corrupt_cache_file.stat().st_size}"
    output_file = out_dir / run_id / "segment_cue_corrupt_sub100.mp4"
    assert output_file.exists()
    assert output_file.stat().st_size >= 100


def test_cue_id_path_traversal_sanitization(temp_ledger, mock_manim_script, tmp_path):
    """Verify cue_id containing path traversal sequences (e.g. '../') is sanitized and stays inside run output directory."""
    run_id = temp_ledger.create_run(slug="path-traversal-test")
    
    script_payload = {
        "slug": "path-traversal-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "../escaped_segment",
                    "animation_type": "array_highlight",
                    "timestamp_seconds": 0.0,
                    "parameters": {"array": [1, 2]},
                },
                {
                    "cue_id": "../../etc/passwd",
                    "animation_type": "tree_traversal",
                    "timestamp_seconds": 5.0,
                    "parameters": {"root": 1},
                },
            ]
        },
    }
    step_id = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(step_id, output_payload=script_payload)

    out_dir = tmp_path / "renders"
    cache_dir = tmp_path / "cache"

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    result = node.execute(run_id=run_id, ledger=temp_ledger)
    assert result["status"] == "completed"
    
    run_out_dir = out_dir / run_id
    # Check that output files were created strictly inside run_out_dir
    assert (run_out_dir / "segment_escaped_segment.mp4").exists()
    assert (run_out_dir / "segment_passwd.mp4").exists()
    
    # Assert no file was created in parent directory
    escaped_file = out_dir / "segment_escaped_segment.mp4"
    assert not escaped_file.exists(), "File should NOT escape run output directory"


def test_atomic_cache_write_mechanics(temp_ledger, mock_manim_script, tmp_path, monkeypatch):
    """Verify cache saving uses atomic file replacement via os.replace from a temporary file in cache_dir."""
    out_dir = tmp_path / "renders"
    cache_dir = tmp_path / "cache"

    replaced_files = []
    orig_replace = os.replace

    def mock_replace(src, dst):
        replaced_files.append((Path(src), Path(dst)))
        return orig_replace(src, dst)

    monkeypatch.setattr(os, "replace", mock_replace)

    node = AnimationGeneratorNode(
        manim_binary=mock_manim_script,
        output_dir=out_dir,
        cache_dir=cache_dir,
    )

    run_id = temp_ledger.create_run(slug="atomic-cache-test")
    script_payload = {
        "slug": "atomic-cache-test",
        "script": {
            "visual_cues": [
                {
                    "cue_id": "cue_atomic",
                    "animation_type": "array_highlight",
                    "parameters": {"key": "atomic_val"},
                }
            ]
        },
    }
    s1 = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(s1, output_payload=script_payload)

    node.execute(run_id=run_id, ledger=temp_ledger)

    # Verify os.replace was called with a .tmp file in cache_dir
    cache_replaces = [r for r in replaced_files if r[1].parent == cache_dir and r[1].suffix == ".mp4"]
    assert len(cache_replaces) >= 1, "Cache write must execute atomic os.replace"
    src_file, dst_file = cache_replaces[0]
    assert src_file.suffix == ".tmp", "Source file for atomic replace must have .tmp suffix"
    assert src_file.parent == cache_dir, "Temporary file must reside in cache_dir for atomic replace"
```

---

## 4. Verification Plan

1. **Unit Test Execution**:
   Run the pytest test suite:
   ```bash
   pytest tests/pipeline/test_animation_node.py -v
   ```
   *Expected outcome*: All tests (including existing 34 tests + 3 new vulnerability tests = 37 total) pass cleanly with 100% success.

2. **Empirical Stress & Security Verification**:
   Execute the challenger's empirical stress harness:
   ```bash
   python3 .agents/challenger_m2_1/stress_harness.py
   ```
   *Expected outcome*:
   - 1-byte corrupt cache test passes (1-byte file ignored, re-rendered clip >= 100 bytes produced).
   - Path traversal test passes (`../escaped_segment` sanitized to `segment_escaped_segment.mp4` within `run_output_dir`).
   - 50 sequential stress iterations completed with 0 FD leaks and 0 leftover `/tmp` directories.

---
