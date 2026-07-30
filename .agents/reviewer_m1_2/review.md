# Phase 13 Milestone 1 Code Review Report

**Reviewer**: Reviewer M1-2 (`teamwork_preview_reviewer`)  
**Date**: 2026-07-30  
**Verdict**: `REQUEST_CHANGES`

---

## Review Summary

Independent review of Phase 13 Milestone 1 code implementation:
- `src/assembly/ffmpeg_commands.py`
- `src/assembly/assembler.py`
- `src/pipeline/nodes/video_assembly_node.py`

The core assembly logic, state ledger integration, FFmpeg filter graph generation, Pydantic schema validation, and temporary file cleanup are well-structured, non-shell isolated, and conform to Phase 13 requirements (R1, R2).

However, a **Major Bug** was discovered during adversarial stress-testing in `VideoAssembler._resolve_command` when `self.ffmpeg_binary` is set to a Python script (such as a mock script used in unit/integration testing). The binary path gets duplicated in the executed subprocess argument list, causing CLI argument parsing in mock scripts to fail.

---

## Findings

### Major Finding 1: Command Resolution Bug for `.py` Executables in `VideoAssembler._resolve_command`

- **What**: `VideoAssembler._resolve_command` duplicates the Python script argument when `self.ffmpeg_binary` is a Python script (e.g. `mock_ffmpeg.py`).
- **Where**: `src/assembly/assembler.py`, lines 52-70 (`_resolve_command`).
- **Why**: When `assemble()` builds `cmd_args` using `build_assembly_command`, the resulting argument array starts with `self.ffmpeg_binary` (e.g., `['/path/to/mock.py', '-y', ...]`).
  In `_resolve_command`:
  - `prefix` is `[sys.executable, '/path/to/mock.py']`.
  - `args[0]` is `'/path/to/mock.py'`.
  - `args[0] == prefix[0]` evaluates to `False` (since `prefix[0]` is `python3`).
  - `args[0] == "ffmpeg"` evaluates to `False`.
  - The fallback `prefix + list(args)` executes, producing: `['python3', '/path/to/mock.py', '/path/to/mock.py', '-y', ...]`.
  This passes `/path/to/mock.py` as `sys.argv[1]` to the subprocess script, causing position-based argument parsing in mock scripts (e.g., expecting `-y` at `sys.argv[1]`) to crash or fail.
- **Suggestion**: Update `_resolve_command` in `src/assembly/assembler.py` to replace `args[0]` whenever `args[0] == self.ffmpeg_binary`:
  ```python
  if self.ffmpeg_binary and (args[0] == "ffmpeg" or args[0] == self.ffmpeg_binary):
      return prefix + list(args[1:])
  ```

---

## Verified Claims

1. **State Ledger Integration & State Isolation**:
   - `VideoAssemblyNode` subclassing `Node` retrieves step outputs strictly from `StateLedger` (`animation_generator` for visual clips, `voice_generator` / `script_generator` for audio/subtitles). -> **PASS**
2. **FFmpeg Filter Graph Generation & Escaping**:
   - `escape_ffmpeg_filter_path` properly escapes backslashes, colons, single quotes, and square brackets in subtitle paths. -> **PASS**
   - `build_concat_filter_graph` generates valid 4K scaling, pad, SAR, concat, subtitle, and audio resampling filter graphs. -> **PASS**
3. **Pydantic Model Payload Validation**:
   - Output payload strictly conforms to `AssembledVideo` schema with sanitized slug matching `^[a-z0-9-]+$`. -> **PASS**
4. **Temporary File & Directory Cleanup**:
   - `VideoAssembler` uses `tempfile.TemporaryDirectory` and unlinks temporary output files (`.tmp_*`) on error. -> **PASS**
5. **Exception Handling & Process Isolation**:
   - `VideoAssembler.run_command` executes via non-shell `subprocess.run(..., close_fds=True, shell=False)` and maps timeouts and non-zero exit codes to `AssemblyError`. -> **PASS**
6. **Integrity Violations Check**:
   - Checked for hardcoded test outputs, dummy implementations, shortcuts, or fabricated artifacts. None detected. -> **PASS**

---

## Stress Test Results

- **Edge Case: Special characters in subtitle paths** (`C:\Video:Special's[1].srt`) -> `escape_ffmpeg_filter_path` produces `C\:\\Video\:Special\'s\[1\].srt` -> **PASS**
- **Edge Case: Empty video_segments input** -> raises `AssemblyError` / `ValueError` -> **PASS**
- **Edge Case: Non-existent input segment file** -> raises `AssemblyError` / `PipelineStageError` -> **PASS**
- **Edge Case: Missing StateLedger instance** -> raises `PipelineStageError` -> **PASS**
- **Edge Case: Subprocess timeout handling** -> raises `AssemblyError` ("FFmpeg process timed out...") -> **PASS**
- **Edge Case: Mock Python script CLI args** -> `VideoAssembler` passes `['python3', '/tmp/mock.py', '/tmp/mock.py', ...]` -> **FAIL** (Major Finding 1)
