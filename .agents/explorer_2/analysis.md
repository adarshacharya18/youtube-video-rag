# Comprehensive Analysis: Test Framework Patterns & VideoAssemblyNode Testing Conventions (Phase 13)

**Author:** Explorer 2 (`teamwork_preview_explorer`)  
**Date:** 2026-07-30  
**Target Node:** `VideoAssemblyNode` (`src/pipeline/nodes/video_assembly_node.py`)  
**Target Test Suite:** `tests/pipeline/test_assembly_node.py`

---

## 1. Executive Summary

Phase 13 requires implementing `VideoAssemblyNode` to combine audio artifacts (`.wav` from Phase 11/Voice) and animation artifacts (`.mp4` from Phase 12/Manim) into a final 4K YouTube video with burned-in subtitles via FFmpeg.

This analysis provides the complete design, test architecture, and mocking strategy for `tests/pipeline/test_assembly_node.py`. It establishes how FFmpeg command generation, state ledger interaction, and subprocess isolation can be thoroughly validated without requiring actual FFmpeg binaries, media codecs, or physical rendering during unit test execution.

---

## 2. Codebase Conventions & Testing Pattern Analysis

### 2.1 Pytest Fixture Infrastructure (`tests/conftest.py`)
The repository follows a standardized pattern for pytest fixtures:
- `temp_data_dir`: Creates isolated temporary directories using pytest's `tmp_path`.
- `test_config`: Loads a deterministic `PipelineConfig` with file I/O safely scoped to `tmp_path`.
- `mock_logger`: Mocks `structlog` via `pytest-mock` (`mocker.patch("src.core.logger.get_logger")`).
- `mock_problem_factory`: Utility factory returning synthetic problem data dictionaries.

### 2.2 Node Testing Conventions (`tests/pipeline/test_animation_node.py` & `tests/pipeline/test_script_node.py`)
Existing node test suites enforce the following architectural invariants:
1. **Node Inheritance & Property Contracts**: Every node inherits from `Node(ABC)` (`src/core/workflow/node.py`) and defines a unique `name` property (e.g., `name = "video_assembly"`).
2. **StateLedger Integration & Context Setup**:
   - State isolation is enforced by initializing SQLite ledgers via `StateLedger(":memory:")` or `StateLedger(db_path=tmp_path / "test.db")`.
   - Nodes query prior step outputs exclusively via `self.get_step_output(run_id, ledger, step_name)`.
   - Prior step completion is seeded using:
     ```python
     run_id = ledger.create_run(slug="two-sum")
     step_id = ledger.record_step_start(run_id, step_name="animation_generator")
     ledger.record_step_completion(step_id, output_payload={...})
     ```
   - Missing `StateLedger` or uncompleted required prior steps must raise `PipelineStageError`.

3. **Subprocess Isolation Patterns**:
   - **Mock Executable Script Fixture**: Rather than calling heavy binaries, tests write a lightweight Python script (`mock_manim.py`) to `tmp_path`. The script parses CLI flags (`sys.argv`), writes mock payload bytes (`MOCK_VIDEO_DATA_...`) to target paths, handles failure flags (e.g. `--fail`), and exits with code 0 or 1.
   - **`subprocess.run` Interception**: `monkeypatch` is used to capture command arrays (`cmd`), assert flag presence (e.g. `close_fds=True`), and test environment settings without subprocess invocation.
   - **Resource & FD Leak Prevention**: Tests explicitly verify that file descriptors before and after execution remain constant (`len(os.listdir("/proc/self/fd"))`), and temporary working directories are cleaned up even during simulated timeouts or crashes.

---

## 3. FFmpeg Command Validation Strategy

### 3.1 The Challenge
FFmpeg command construction for 4K video assembly with burned-in subtitles and multi-track audio filtergraphs is complex. Unit tests must validate:
1. Accurate command string and argument array generation.
2. Correct handling of input video clips (`.mp4`), audio tracks (`.wav`), and subtitle files (`.ass`/`.srt`).
3. 4K resolution scaling (`3840x2160`), FPS settings (`30fps`/`60fps`), and codec selection (`libx264`, `aac`).
4. Strict error handling and resource cleanup when FFmpeg fails or times out.
5. Zero dependency on system FFmpeg installation or real media assets.

### 3.2 Three-Tier Testing Strategy

```
+-----------------------------------------------------------------------------------+
|                            FFmpeg Validation Strategy                             |
+-----------------------------------------------------------------------------------+
| Tier 1: Pure Command Construction Unit Tests                                       |
| - Directly test `node.build_ffmpeg_command()` or `FFmpegAssembler.build_command()` |
| - Assert exact flags (-y, -i, -filter_complex, -c:v libx264, -c:a aac, -s 3840x2160)|
| - Zero file I/O or subprocess calls                                               |
+-----------------------------------------------------------------------------------+
| Tier 2: Subprocess Interception Tests (Monkeypatched `subprocess.run`)            |
| - Intercept `subprocess.run` calls inside `node.execute()`                         |
| - Inspect `cmd` list, verify `close_fds=True`, simulate exit code 1 or timeouts    |
| - Verify translation into domain exception (`AssemblyError`)                      |
+-----------------------------------------------------------------------------------+
| Tier 3: Mock Binary Execution (`mock_ffmpeg.py` Fixture)                          |
| - Run full `node.execute(run_id, ledger)` using mock python CLI script            |
| - Verify StateLedger updates, temp filter/subtitle file cleanup, and payload schema|
+-----------------------------------------------------------------------------------+
```

#### Tier 1: Command Builder Logic Testing
Expose a deterministic helper method on the node or assembler class:
```python
def build_ffmpeg_command(
    inputs: list[Path],
    audio_path: Path,
    output_path: Path,
    subtitle_path: Path | None = None,
    resolution: str = "3840x2160",
    fps: int = 30,
) -> list[str]: ...
```
Tests can call `build_ffmpeg_command` with synthetic paths and verify:
- Presence of `-y` (overwrite output without prompting).
- Input file declarations (`-i path1.mp4 -i path2.mp4 -i audio.wav`).
- Complex filtergraph strings (`-filter_complex "[0:v][1:v]concat=n=2:v=1:a=0[v]"` or subtitle overlay `subtitles='sub.ass'`).
- Codec options (`-c:v libx264 -preset medium -crf 18 -c:a aac -b:a 192k`).
- Target resolution (`-s 3840x2160` or `-vf scale=3840:2160`).

#### Tier 2: Subprocess Interception Testing
Using `monkeypatch.setattr(subprocess, "run", mock_run)`, tests can:
- Verify `close_fds=True` is passed to prevent file descriptor leaks.
- Verify `cwd` is set to an isolated temporary directory.
- Intercept and validate the exact `cmd` array passed during `execute()`.
- Simulate `subprocess.TimeoutExpired` to verify timeout exception wrapping.

#### Tier 3: Mock Binary Execution Fixture
Create a `mock_ffmpeg_script` pytest fixture:
```python
@pytest.fixture
def mock_ffmpeg_script(tmp_path):
    script_path = tmp_path / "mock_ffmpeg.py"
    script_content = """import sys, os

if "--fail" in sys.argv:
    sys.stderr.write("FFmpeg encoding error\\n")
    sys.exit(1)

# Find output file argument (last arg or after -y/output path)
out_file = sys.argv[-1]
os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
with open(out_file, "wb") as f:
    f.write(b"MOCK_4K_MP4_VIDEO_HEADER_AND_DATA_" * 10)

sys.exit(0)
"""
    script_path.write_text(script_content, encoding="utf-8")
    return str(script_path)
```

---

## 4. State Ledger & Prior Step Mocking Strategy

`VideoAssemblyNode` requires inputs from prior pipeline nodes. In `StateLedger`, these are:
1. `animation_generator` payload:
   ```json
   {
     "slug": "two-sum",
     "segments": [
       {
         "segment_id": "seg_cue_01",
         "visual_path": "/path/to/segment_cue_01.mp4",
         "duration": 5.0
       },
       {
         "segment_id": "seg_cue_02",
         "visual_path": "/path/to/segment_cue_02.mp4",
         "duration": 15.0
       }
     ],
     "status": "completed"
   }
   ```
2. `script_generator` or `voice_generator` payload:
   ```json
   {
     "slug": "two-sum",
     "audio_path": "/path/to/full_narration.wav",
     "subtitle_path": "/path/to/subtitles.ass",
     "spoken_narration": ["Welcome to Two Sum..."],
     "status": "completed"
   }
   ```

### Ledger Setup Helper for Unit Tests
```python
def seed_assembly_ledger(ledger, run_id, anim_payload, script_payload):
    # Record completed animation_generator step
    s1 = ledger.record_step_start(run_id, step_name="animation_generator")
    ledger.record_step_completion(s1, output_payload=anim_payload)

    # Record completed script_generator step
    s2 = ledger.record_step_start(run_id, step_name="script_generator")
    ledger.record_step_completion(s2, output_payload=script_payload)
```

---

## 5. Recommended Test Structure for `tests/pipeline/test_assembly_node.py`

Below is the concrete blueprint for `tests/pipeline/test_assembly_node.py`:

```python
"""Tests for VideoAssemblyNode and FFmpeg video assembly execution."""

import os
from pathlib import Path
import subprocess
import sys
import pytest

from src.core.exceptions import AssemblyError, PipelineStageError
from src.core.models.assets import AssembledVideo
from src.core.orchestrator.state_ledger import StateLedger
from src.pipeline.nodes.video_assembly_node import VideoAssemblyNode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_ledger(tmp_path):
    """Clean SQLite StateLedger fixture."""
    return StateLedger(db_path=tmp_path / "test_ledger.db")


@pytest.fixture
def mock_ffmpeg_script(tmp_path):
    """Mock FFmpeg CLI binary fixture."""
    script_path = tmp_path / "mock_ffmpeg.py"
    script_content = """import sys, os
out_file = sys.argv[-1]
if "--fail" in sys.argv:
    sys.stderr.write("Simulated FFmpeg assembly failure\\n")
    sys.exit(1)
os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
with open(out_file, "wb") as f:
    f.write(b"MOCK_4K_FINAL_VIDEO_ARTIFACT_DATA_" * 10)
sys.exit(0)
"""
    script_path.write_text(script_content, encoding="utf-8")
    return str(script_path)


# ---------------------------------------------------------------------------
# Unit Test Cases
# ---------------------------------------------------------------------------

def test_node_name_and_init():
    """Verify node property name returns 'video_assembly'."""
    node = VideoAssemblyNode(resolution="3840x2160")
    assert node.name == "video_assembly"
    assert node.resolution == "3840x2160"


def test_execute_without_ledger_raises_error():
    """Verify executing without StateLedger raises PipelineStageError."""
    node = VideoAssemblyNode()
    with pytest.raises(PipelineStageError):
        node.execute(run_id="run_123", ledger=None)


def test_execute_without_prior_animation_step_raises_error(temp_ledger):
    """Verify missing animation_generator step raises PipelineStageError."""
    run_id = temp_ledger.create_run(slug="two-sum")
    node = VideoAssemblyNode()
    with pytest.raises(PipelineStageError):
        node.execute(run_id=run_id, ledger=temp_ledger)


def test_ffmpeg_command_string_generation_4k(tmp_path):
    """Verify generated FFmpeg CLI command list contains correct inputs, codecs, and 4K flags."""
    node = VideoAssemblyNode(resolution="3840x2160", fps=30)
    input_segments = [tmp_path / "seg1.mp4", tmp_path / "seg2.mp4"]
    audio_path = tmp_path / "narration.wav"
    output_path = tmp_path / "final_output.mp4"
    subtitle_path = tmp_path / "subtitles.ass"

    cmd = node.build_ffmpeg_command(
        inputs=input_segments,
        audio_path=audio_path,
        output_path=output_path,
        subtitle_path=subtitle_path,
    )

    assert cmd[0].endswith("ffmpeg") or "python" in cmd[0]
    assert "-y" in cmd
    assert str(audio_path) in cmd
    assert "-c:v" in cmd and "libx264" in cmd
    assert "-c:a" in cmd and "aac" in cmd
    assert str(output_path) in cmd


def test_successful_assembly_execution(temp_ledger, mock_ffmpeg_script, tmp_path):
    """Verify end-to-end assembly execution, payload structure, and AssembledVideo schema validity."""
    run_id = temp_ledger.create_run(slug="two-sum")
    
    # 1. Create dummy input media files
    anim_dir = tmp_path / "renders" / run_id
    anim_dir.mkdir(parents=True)
    seg1_file = anim_dir / "segment_01.mp4"
    seg1_file.write_bytes(b"MOCK_SEGMENT_1_DATA_" * 5)

    audio_file = tmp_path / "narration.wav"
    audio_file.write_bytes(b"MOCK_AUDIO_DATA_" * 5)

    # 2. Seed StateLedger with prior step outputs
    anim_payload = {
        "slug": "two-sum",
        "segments": [
            {
                "segment_id": "seg_01",
                "segment_type": "visual_anim",
                "start_time": 0.0,
                "end_time": 5.0,
                "duration": 5.0,
                "visual_path": str(seg1_file),
                "asset_references": [{"asset_id": "a1", "asset_type": "video", "file_path": str(seg1_file)}]
            }
        ]
    }
    s1 = temp_ledger.record_step_start(run_id, step_name="animation_generator")
    temp_ledger.record_step_completion(s1, output_payload=anim_payload)

    script_payload = {
        "slug": "two-sum",
        "audio_path": str(audio_file)
    }
    s2 = temp_ledger.record_step_start(run_id, step_name="script_generator")
    temp_ledger.record_step_completion(s2, output_payload=script_payload)

    # 3. Execute node
    output_dir = tmp_path / "assembled"
    node = VideoAssemblyNode(
        ffmpeg_binary=mock_ffmpeg_script,
        output_dir=output_dir
    )
    result = node.execute(run_id=run_id, ledger=temp_ledger)

    assert result["status"] == "completed"
    assert result["slug"] == "two-sum"
    assert Path(result["final_video_path"]).exists()

    # Validate output payload against Pydantic AssembledVideo model
    assembled_model = AssembledVideo.model_validate(result["assembled_video"])
    assert assembled_model.slug == "two-sum"


def test_subprocess_failure_raises_assembly_error(temp_ledger, tmp_path):
    """Verify non-zero FFmpeg exit code raises AssemblyError."""
    run_id = temp_ledger.create_run(slug="fail-test")

    fail_script = tmp_path / "fail_ffmpeg.py"
    fail_script.write_text("import sys\nsys.stderr.write('FFmpeg Error')\nsys.exit(1)\n", encoding="utf-8")

    # Seed minimal step output
    anim_payload = {"slug": "fail-test", "segments": []}
    s1 = temp_ledger.record_step_start(run_id, step_name="animation_generator")
    temp_ledger.record_step_completion(s1, output_payload=anim_payload)

    node = VideoAssemblyNode(ffmpeg_binary=str(fail_script))
    with pytest.raises(AssemblyError):
        node.execute(run_id=run_id, ledger=temp_ledger)


def test_temporary_file_cleanup_on_completion_and_failure(temp_ledger, mock_ffmpeg_script, tmp_path):
    """Verify intermediate filtergraph files and temp dirs are deleted after assembly."""
    run_id = temp_ledger.create_run(slug="cleanup-test")
    # (Seed ledger and run node, assert temp files in work dir are unlinked)


def test_no_file_descriptor_leak_on_assembly(temp_ledger, mock_ffmpeg_script, tmp_path):
    """Verify open file descriptor count remains identical before and after node execution."""
    fds_before = len(os.listdir("/proc/self/fd"))
    # (Run node)
    fds_after = len(os.listdir("/proc/self/fd"))
    assert fds_after == fds_before
```

---

## 6. Summary of Key Recommendations for Phase 13 Implementer

1. **Class Architecture**:
   - Implement `VideoAssemblyNode` in `src/pipeline/nodes/video_assembly_node.py` inheriting from `src.core.workflow.node.Node`.
   - Implement or utilize `FFmpegAssembler` helper in `src/assembly/assembler.py` and command generator in `src/assembly/ffmpeg_commands.py`.
2. **Deterministic Command Builder Method**:
   - Expose `build_ffmpeg_command(...)` as a standalone or static/method call to allow pure unit testing without executing subprocesses.
3. **Artifact Cleanup Guarantees**:
   - Use `tempfile.TemporaryDirectory` or `try...finally` blocks to guarantee intermediate filter files (`filter_graph.txt`, `concat_list.txt`, `.ass` subtitle temp files) are purged on both success and failure.
4. **State Ledger Output**:
   - Output payload must include serialized `AssembledVideo` Pydantic model (`src/core/models/assets.py`), output file path, duration, file size, and `"status": "completed"`.
