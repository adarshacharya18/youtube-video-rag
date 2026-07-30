# Handoff Report: Subtask M1-2 — VideoAssembler Design (`src/assembly/assembler.py`)

## 1. Observation
- Target File: `src/assembly/assembler.py` (currently empty 0-byte file).
- Underlying Exception: `AssemblyError` defined in `src/core/exceptions.py:140` (`class AssemblyError(PipelineError)`).
- Input Contracts & Requirements:
  - `ORIGINAL_REQUEST.md` (Phase 13 section, lines 236-265): Media Production: Video Assembly combining audio `.wav` and animation `.mp4` into 4K YouTube video with burnt subtitles and cleanup.
  - `SCOPE.md`: Subtask M1-2 requires `VideoAssembler` class in `src/assembly/assembler.py` executing FFmpeg non-shell `subprocess.run()`, managing timeouts, error mapping (`AssemblyError`), and explicit temporary file cleanup.
- Precedent Patterns: `AnimationGeneratorNode` (`src/pipeline/nodes/animation_generator_node.py:347`) and `ManimRenderer` (`src/animation/renderer.py:101-115`) use `close_fds=True`, `timeout`, `capture_output=True`, `text=True`, and `tempfile.TemporaryDirectory()`.

## 2. Logic Chain
1. **Low-Level Execution Abstraction**:
   - `VideoAssembler` encapsulates execution logic for running FFmpeg commands without exposing raw shell processes to higher-level workflow nodes.
   - `_resolve_binary_command()` allows injecting a custom binary path (or mock script ending in `.py`) or defaulting to system `"ffmpeg"`.

2. **Secure Non-Shell Subprocess Execution**:
   - Setting `shell=False` (by passing a list of string arguments) prevents shell-injection vulnerabilities.
   - Setting `close_fds=True` guarantees that file descriptors opened by the parent Python process are closed in the child subprocess, avoiding FD resource leaks.
   - Passing `timeout=300.0` ensures long-running or stalled FFmpeg renders do not hang the pipeline indefinitely.
   - `capture_output=True` and `text=True` capture stdout/stderr strings for error reporting.

3. **Domain Exception Mapping**:
   - Catching `subprocess.TimeoutExpired` explicitly captures trailing output and raises `AssemblyError` with chained context (`from e`).
   - Checking `result.returncode != 0` captures `result.stderr` (or `result.stdout`) and raises `AssemblyError`.
   - Validating output artifact size (`_is_valid_video`) ensures that even if FFmpeg returns 0, zero-byte or missing output files raise `AssemblyError`.

4. **Robust Temporary File Lifecycle & Clean Failure Recovery**:
   - Using `tempfile.TemporaryDirectory(prefix="assembly_", dir=...)` guarantees that all intermediate files (`concat_list.txt`, `subtitles.srt`) are automatically unlinked upon exiting the context.
   - Output files are written to a temporary destination (`tmp_dest = dest_path.parent / f"{dest_path.name}.tmp_{pid}"`).
   - Upon successful execution and size validation, `os.replace(tmp_dest, dest_path)` atomically moves the artifact to its final destination.
   - In case of failure, `except Exception:` block explicitly cleans up `tmp_dest` if it exists.

## 3. Caveats
- No caveats. The design covers all security, timeout, error mapping, and temporary directory cleanup requirements.

## 4. Conclusion
The complete design specification and drop-in code snippet for `VideoAssembler` in `src/assembly/assembler.py` has been formulated and published to `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_2/analysis.md`. The implementer can directly copy or adapt the code snippet from `analysis.md` to populate `src/assembly/assembler.py`.

## 5. Verification Method
1. **Inspect Handoff & Analysis**:
   - Read `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_2/analysis.md` to review class definition, method signatures, error handling, and complete implementation snippet.
2. **Implementation & Unit Test Verification**:
   - Once implemented in `src/assembly/assembler.py`, run unit tests: `pytest tests/pipeline/test_assembly_node.py` or dedicated unit test file.
   - Assert `subprocess.run` parameters include `close_fds=True`, `capture_output=True`, `text=True`, `timeout=300.0`.
   - Assert `subprocess.TimeoutExpired` and non-zero exit codes raise `AssemblyError`.
   - Assert temporary directories created by `tempfile.TemporaryDirectory` are absent after completion or exception.
