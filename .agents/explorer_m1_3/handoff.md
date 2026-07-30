# Handoff Report: `VideoAssemblyNode` Design (`src/pipeline/nodes/video_assembly_node.py`)

## 1. Observation
- **Node Contract (`src/core/workflow/node.py:18-58`)**: Base class `Node(ABC)` requires `@property name(self) -> str` and `execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]`. Helper method `get_step_output(run_id, ledger, step_name)` queries prior step output payloads and raises `PipelineStageError` if missing.
- **Data Models (`src/core/models/assets.py:226-267`)**: `AssembledVideo` model validates `slug` (`^[a-z0-9-]+$`), `final_video_path`, `total_duration_seconds` (> 0.0), `file_size_bytes` (>= 0), `segments` (`list[RenderSegment]`), and `assembled_at`.
- **Exception Hierarchy (`src/core/exceptions.py:57, 140`)**: `PipelineStageError` (for missing input step payloads/files) and `AssemblyError` (for FFmpeg subprocess failure, timeout, or corrupted output).
- **Assembler Component (`src/assembly/assembler.py`)**: `VideoAssembler` class provides `assemble(video_segments, audio_path, subtitle_path, subtitle_text, output_path, resolution, fps, crf, preset)` returning destination `Path`.
- **Existing Node Reference (`src/pipeline/nodes/animation_generator_node.py:68-150`)**: Establishes standard initialization, path resolution, logger usage, and error wrapping conventions.

## 2. Logic Chain
1. **Subclassing `Node`**: `VideoAssemblyNode` inherits from `Node` to integrate seamlessly into `WorkflowEngine`.
2. **Step Name Property**: `@property def name(self) -> str: return "video_assembly"` uniquely identifies the node in the SQLite `StateLedger`.
3. **State Ledger Input Retrieval**:
   - `anim_output = self.get_step_output(run_id, ledger, "animation_generator")` retrieves visual segment `.mp4` file paths and segment duration metadata. Missing step output or empty segments raise `PipelineStageError`.
   - Prior step outputs for `"voice_generator"` or `"script_generator"` are checked in `ledger.get_completed_steps(run_id)` to extract `.wav` audio track paths, `.srt` subtitle paths, or raw SRT string content.
4. **Assembly Execution**: `VideoAssemblyNode.execute()` instantiates `VideoAssembler` with configurable binary, timeout, and temp dir, then invokes `assembler.assemble(...)` to merge video clips, audio, and burned-in subtitles.
5. **Output Schema Validation**: The resulting file path, size, duration, segments, and timestamp are validated through `AssembledVideo.model_validate(...)` / constructor before returning `model.model_dump()`.
6. **Exception Boundaries**: Precondition failures (missing ledger, missing prior step output, missing segment `.mp4` file) raise `PipelineStageError`. FFmpeg errors, timeouts, or corrupt artifacts raise `AssemblyError`.

## 3. Caveats
- No caveats. The contracts between `Node`, `StateLedger`, `VideoAssembler`, and `AssembledVideo` are fully reconciled and aligned.

## 4. Conclusion
- Complete class definition and `execute()` method specifications for `VideoAssemblyNode` in `src/pipeline/nodes/video_assembly_node.py` are fully formulated and documented in `analysis.md`. The design fulfills all prompt and Phase 13 requirements.

## 5. Verification Method
- **Unit Test Command**: `pytest tests/pipeline/test_assembly_node.py`
- **Verification Checklist**:
  1. Instantiation of `VideoAssemblyNode` returns `node.name == "video_assembly"`.
  2. Passing `ledger=None` to `execute()` raises `PipelineStageError`.
  3. Execution with missing `animation_generator` step in mock ledger raises `PipelineStageError`.
  4. Successful execution with mock FFmpeg binary script returns dict matching `AssembledVideo` schema.
  5. Mock FFmpeg failure (exit code 1) causes `execute()` to raise `AssemblyError`.
