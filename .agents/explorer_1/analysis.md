# Architectural Analysis: Phase 13 Media Production — Video Assembly

## Executive Summary
This report presents a thorough investigation of the codebase architecture to support the implementation of **Phase 13: Media Production: Video Assembly**. The goal of Phase 13 is to build `VideoAssemblyNode` in `src/pipeline/nodes/video_assembly_node.py` (supported by `src/assembly/ffmpeg_commands.py` and `src/assembly/assembler.py`), which reads audio artifacts (Phase 11) and Manim video animation clips (Phase 12) from the SQLite `StateLedger`, compiles them using FFmpeg via `subprocess.run()`, generates burned-in subtitles, outputs a 4K YouTube-ready video (`AssembledVideo`), and rigorously cleans up all intermediate temporary files.

---

## 1. Codebase Architecture & Workflow Engine Infrastructure

### 1.1 Base Node Contract (`src/core/workflow/node.py`)
All workflow steps inherit from `src.core.workflow.node.Node`. The interface enforces:
- `name` (`@property @abstractmethod -> str`): Unique step identifier string (e.g., `"video_assembly"`).
- `execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]`: Main entry point executed by `WorkflowEngine`.
- Provided helper methods:
  - `get_run_record(run_id, ledger) -> PipelineRunRecord`: Queries `StateLedger.get_run(run_id)` and raises `PipelineStageError` if the run is missing.
  - `get_step_output(run_id, ledger, step_name) -> dict[str, Any]`: Queries `StateLedger.get_completed_steps(run_id)` and returns the `output_payload` dictionary for `step_name`, or raises `PipelineStageError` if the step was not completed.
  - `get_completed_step_outputs(run_id, ledger) -> dict[str, dict[str, Any]]`: Returns a map of all completed steps to their output payloads.

### 1.2 Workflow Execution Engine (`src/core/workflow/engine.py`)
`WorkflowEngine` executes nodes sequentially:
- Wraps node execution in `try ... except Exception as e`.
- Records step start via `ledger.record_step_start(run_id, node.name)`.
- Emits lifecycle events (`NodeStarted`, `NodeCompleted`, `NodeFailed`) to `EventBus`.
- On completion: calls `ledger.record_step_completion(step_id, node_output)`.
- On error: calls `ledger.record_step_failure(step_id, error_message, error_details)`, updates pipeline status to `FAILED`, and halts execution gracefully.

---

## 2. State Ledger Storage & Artifact Retrieval Patterns

### 2.1 SQLite Schema & State Ledger Interface (`src/core/orchestrator/state_ledger.py`)
- Tables: `pipeline_runs` and `step_executions`.
- Output payload storage: JSON column `output_payload` in `step_executions`.
- Retrieval interface: `ledger.get_completed_steps(run_id)` returns `dict[str, StepExecutionRecord]`.

### 2.2 Phase 11 Audio Artifact Storage
From `ScriptGeneratorNode` (`src/pipeline/nodes/script_generator_node.py`) and asset models (`src/core/models/assets.py`):
- Payloads store script data and narration tracks under `"script"`.
- Audio paths are present in:
  1. `script_payload.get("audio_path")` or `script_payload["script"].get("audio_path")`.
  2. `RenderSegment.audio_path` or `RenderSegment.audio_asset` (e.g. `.wav` narration files).
  3. Direct step fallback for audio outputs if recorded under prior steps like `"voice_generator"` or `"script_generator"`.

### 2.3 Phase 12 Manim Video Artifact Storage
From `AnimationGeneratorNode` (`src/pipeline/nodes/animation_generator_node.py`):
- Step output payload structure:
  ```json
  {
    "slug": "two-sum",
    "segments": [
      {
        "segment_id": "seg_cue_01",
        "segment_type": "visual_anim",
        "start_time": 0.0,
        "end_time": 5.0,
        "duration": 5.0,
        "asset_references": [
          {
            "asset_id": "asset_cue_01",
            "asset_type": "video",
            "file_path": "/path/to/renders/run_id/segment_cue_01.mp4",
            "duration": 5.0
          }
        ],
        "visual_path": "/path/to/renders/run_id/segment_cue_01.mp4",
        "scene_type": "ARRAY_HIGHLIGHT",
        "visual_parameters": {"array": [2, 7, 11, 15]}
      }
    ],
    "render_count": 1,
    "output_directory": "/path/to/renders/run_id",
    "status": "completed"
  }
  ```
- Retrieval method in `VideoAssemblyNode`:
  ```python
  anim_output = self.get_step_output(run_id, ledger, "animation_generator")
  segments = anim_output.get("segments", [])
  ```

---

## 3. Subprocess & Temporary File Management Analysis

### 3.1 Subprocess Isolation & Safety Rules (Established in Phase 12)
1. **`close_fds=True`**: Prevents file descriptor leaks across sub-processes (verified in `tests/pipeline/test_animation_node.py:test_no_file_descriptor_leak_on_execution`).
2. **Timeout Enforcement**: `timeout` parameter in `subprocess.run()` (e.g. 300 seconds) prevents hangs.
3. **Atomic File Creation & Validation**: Check output files exist and size >= threshold before returning.
4. **Exception Mapping**: Catch `subprocess.TimeoutExpired`, non-zero exit codes, and wrap in domain exception `AssemblyError` (defined in `src.core.exceptions`).

### 3.2 Temporary File Cleanup Requirements
FFmpeg processing creates intermediate assets:
- Concat file lists (`concat_list.txt`)
- Burned-in subtitle files (`subtitles.srt` / `.ass`)
- Filter graph temp files / intermediate scaled clips.

**Cleanup Strategy**:
- Wrap FFmpeg execution in `with tempfile.TemporaryDirectory(prefix="assembly_", dir=self.temp_dir) as temp_dir:`
- Write `concat_list.txt` and `subtitles.srt` inside `temp_dir`.
- On subprocess error or timeout: `tempfile.TemporaryDirectory` automatically cleans up all temp files.
- On assembly failure: clean up partially written final output files (`.mp4`) in destination output directory.

---

## 4. Architectural Blueprint for `VideoAssemblyNode`

### 4.1 Class Definition & Location
- Location: `src/pipeline/nodes/video_assembly_node.py`
- Class signature: `class VideoAssemblyNode(Node):`
- Domain exception: `from src.core.exceptions import AssemblyError, PipelineStageError`
- Data models: `from src.core.models.assets import AssembledVideo, RenderSegment`

### 4.2 Step Execution Flow
1. **Ledger Validation**: Ensure `ledger is not None`.
2. **Retrieve Artifacts**:
   - `anim_output = self.get_step_output(run_id, ledger, "animation_generator")`
   - Retrieve `script_generator` output for spoken narration text / timing if SRT subtitles need to be compiled.
3. **Prepare Temp Directory**:
   - Create isolated temp directory via `tempfile.TemporaryDirectory()`.
4. **Build Concat List & Subtitle File**:
   - Generate `concat_list.txt` referencing all valid segment MP4 visual paths.
   - Generate SRT subtitle file mapping narration segments to timestamps.
5. **Construct FFmpeg Command**:
   - Target resolution: 4K (3840x2160) or 1080p fallback based on quality setting.
   - Video codec: `libx264` or `libx265`, `-pix_fmt yuv420p`, `-preset medium`, `-crf 18`.
   - Filter graph: `-vf "subtitles=subtitles.srt:force_style='FontSize=24,PrimaryColour=&H00FFFFFF'"` (or video scale filter `scale=3840:2160`).
   - Audio input & codec: Concat audio or overlay `.wav` audio track (`-c:a aac -b:a 320k`).
6. **Execute FFmpeg via Subprocess**:
   - `subprocess.run(cmd, capture_output=True, text=True, close_fds=True, timeout=self.timeout)`
7. **Validate Artifact**:
   - Check destination file exists and is valid (size > 100 bytes).
8. **Return Output Payload**:
   - Construct `AssembledVideo` model and return dict payload:
     ```python
     {
         "slug": slug,
         "final_video_path": str(output_file),
         "total_duration_seconds": total_duration,
         "file_size_bytes": file_size,
         "status": "completed"
     }
     ```

---

## 5. Supporting Code Modules (`src/assembly/`)

1. **`src/assembly/ffmpeg_commands.py`**:
   - Contains pure helper functions to generate FFmpeg CLI argument arrays.
   - Functions:
     - `build_concat_command(input_files: list[Path], output_file: Path, preset: str = "medium") -> list[str]`
     - `build_assembly_command(video_inputs: list[Path], audio_input: Optional[Path], subtitle_file: Optional[Path], output_file: Path, resolution: str = "3840x2160") -> list[str]`
     - `generate_srt_file(subtitles: list[dict], srt_path: Path) -> Path`

2. **`src/assembly/assembler.py`**:
   - Encapsulates low-level FFmpeg execution runner class `FFmpegAssembler`.

---

## 6. Verification & Test Plan

Unit test suite (`tests/pipeline/test_assembly_node.py`):
1. **`test_node_name()`**: Verify `node.name == "video_assembly"`.
2. **`test_missing_ledger_raises_error()`**: Verify `PipelineStageError` when `ledger=None`.
3. **`test_missing_animation_output_raises_error()`**: Verify `PipelineStageError` when `animation_generator` prior step is missing.
4. **`test_successful_assembly()`**: Mock FFmpeg script binary, verify complete assembly execution and state ledger payload output.
5. **`test_ffmpeg_failure_raises_assembly_error()`**: Verify non-zero exit code raises `AssemblyError`.
6. **`test_temp_directory_cleanup()`**: Verify temporary directory and `concat_list.txt` / `subtitles.srt` files are completely removed after execution.
7. **`test_no_fd_leak()`**: Measure open file descriptors in `/proc/self/fd` before and after execution.
