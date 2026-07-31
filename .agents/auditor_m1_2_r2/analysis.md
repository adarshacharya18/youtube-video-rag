# Forensic Integrity Audit Analysis (Round 2) — Milestone M1

**Audit Date**: 2026-07-30  
**Target Codebase**: Phase 14 Milestone M1 Re-audit  
**Auditor**: Forensic Auditor 2 (Round 2) (`auditor_m1_2_r2`)  
**Scope**: 
- `src/pipeline/nodes/animation_generator_node.py`
- `src/pipeline/nodes/video_assembly_node.py`
- `src/animation/renderer.py`
- `src/pipeline/nodes/voice_generator_node.py`
- Test directories (`tests/pipeline/`, `tests/orchestrator/`, `tests/cli/`, `tests/workflow/`, `tests/production/`)

---

## 1. Ground Truth & Constraints
- **ORIGINAL_REQUEST.md Integrity Mode**: `development`
- **User Instruction**: Re-audit M1 nodes/renderer for zero fake byte writing, facade logic, or hardcoded test outputs. Run the pytest suite (`pytest tests/pipeline/ tests/orchestrator/ tests/cli/ tests/workflow/ tests/production/`). Issue explicit verdict (`CLEAN` or `INTEGRITY VIOLATION`).

---

## 2. Phase 1 — Codebase Forensic Inspection Results

### A. `src/pipeline/nodes/animation_generator_node.py`
- **Status**: CLEAN (Fake byte fallback removed).
- **Inspection Findings**:
  - The previous fallback block that wrote `b"MOCK_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5` on render failure in `_invoke_manim_subprocess` has been completely removed.
  - Line 386-394:
    ```python
    scene_file, scene_class = ANIMATION_TYPE_MAP.get(anim_type, DEFAULT_SCENE)
    rendered_clip = self.renderer.render(
        scene_script=Path(scene_file),
        class_name=scene_class,
        output_dir=temp_dir,
        output_filename=f"{cue_id}.mp4",
        parameters=parameters,
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rendered_clip, output_file)
    ```
  - `AnimationError` is properly raised on render failure or missing MP4 output.

### B. `src/pipeline/nodes/video_assembly_node.py`
- **Status**: CLEAN (Fake byte fallback removed).
- **Inspection Findings**:
  - The previous fallback block that caught `AssemblyError` and wrote `final_video_path.write_bytes(b"MOCK_ASSEMBLED_VIDEO_DATA_FOR_TESTING_PURPOSES_" * 5)` has been removed.
  - Line 223-224:
    ```python
    except AssemblyError:
        raise
    ```
  - `AssemblyError` is propagated cleanly when FFmpeg fails or is missing.

### C. `src/animation/renderer.py`
- **Status**: CLEAN.
- **Inspection Findings**:
  - Encapsulates Manim CLI execution via `subprocess.run` with `close_fds=True`, timeout limits, and non-zero exit code validation.

### D. `src/pipeline/nodes/voice_generator_node.py`
- **Status**: INTEGRITY VIOLATION (Fake byte writing & facade data).
- **Inspection Findings**:
  - Lines 51-61:
    ```python
    wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\x3e\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    if not audio_file.exists():
        audio_file.write_bytes(wav_header)

    srt_content = (
        "1\n00:00:00,000 --> 00:00:05,000\nWelcome to our algorithm walkthrough.\n\n"
        "2\n00:00:05,000 --> 00:00:10,000\nLet's analyze the time complexity.\n"
    )
    if not sub_file.exists():
        sub_file.write_text(srt_content, encoding="utf-8")
    ```
  - `VoiceGeneratorNode` writes hardcoded fake WAV bytes (`wav_header`) and hardcoded subtitle text if audio files do not exist, rather than performing audio synthesis.

---

## 3. Phase 2 — Behavioral & Test Suite Execution Results

### Command Executed
```bash
pytest tests/pipeline/ tests/orchestrator/ tests/cli/ tests/workflow/ tests/production/
```

### Execution Summary
- **Total Tests**: 160
- **Passed**: 146
- **Failed**: 14
- **Exit Code**: 1

### Detailed Failure List
1. `tests/orchestrator/test_pipeline_runner.py::test_pipeline_runner_successful_run_problem`
2. `tests/orchestrator/test_pipeline_runner.py::test_pipeline_runner_resumption_from_checkpoint`
3. `tests/orchestrator/test_pipeline_runner.py::test_pipeline_runner_get_status`
4. `tests/orchestrator/test_pipeline_runner.py::test_pipeline_runner_event_bus_subscription`
5. `tests/cli/test_ops.py::test_cli_run_command_success`
6. `tests/cli/test_ops.py::test_cli_run_command_json_output`
7. `tests/cli/test_ops.py::test_cli_status_command`
8. `tests/cli/test_ops.py::test_cli_status_command_json`
9. `tests/cli/test_ops.py::test_cli_resume_command`
10. `tests/production/test_pipeline_e2e.py::test_pipeline_e2e_full_execution`
11. `tests/production/test_pipeline_e2e.py::test_pipeline_e2e_resume_flow`
12. `tests/production/test_production_suite.py::TestProductionEndToEnd::test_end_to_end_success_path`
13. `tests/production/test_production_suite.py::TestRecoveryAndResiliency::test_checkpoint_resumption_after_failure`
14. `tests/production/test_production_suite.py::TestStressAndBenchmarks::test_sequential_multi_problem_runs`

### Root Cause Analysis of Test Failures
- Empirical system check (`which ffmpeg`) returned: `ffmpeg not found`.
- When the fake byte writing fallback block (`final_video_path.write_bytes(...)`) was removed from `VideoAssemblyNode`, executing the un-mocked production pipeline in integration and E2E tests (`PipelineRunner.run_problem(...)`) triggered a real call to `ffmpeg`.
- Because `ffmpeg` is not installed on the system and the E2E tests do not mock FFmpeg, `VideoAssemblyNode` raised `AssemblyError: Failed to execute FFmpeg subprocess: [Errno 2] No such file or directory: 'ffmpeg'`, causing all 14 integration and E2E test cases to fail.

---

## 4. Final Verdict

**VERDICT**: `INTEGRITY VIOLATION`

**Rationale**:
1. Behavioral test execution failed with 14 failing tests out of 160 in the mandatory test suite (`pytest tests/pipeline/ tests/orchestrator/ tests/cli/ tests/workflow/ tests/production/`). Per Integrity Forensics rules, any test failure or non-building test suite requires rejection.
2. `VoiceGeneratorNode` (`src/pipeline/nodes/voice_generator_node.py`) retains fake byte writing (`audio_file.write_bytes(wav_header)`).
