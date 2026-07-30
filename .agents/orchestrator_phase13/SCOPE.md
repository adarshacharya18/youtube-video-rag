# Scope: Phase 13 - Media Production: Video Assembly

## Architecture
- `src/assembly/ffmpeg_commands.py`: Pure FFmpeg CLI command list builders for 4K rendering, concat, audio mixing, subtitle burning.
- `src/assembly/assembler.py`: `VideoAssembler` class executing FFmpeg commands securely via non-shell `subprocess.run()`, managing timeouts, error handling (`AssemblyError`), and explicit temporary file cleanup.
- `src/pipeline/nodes/video_assembly_node.py`: `VideoAssemblyNode` subclassing `Node`, interacting with `StateLedger` to retrieve Phase 11 (`voice_generator`/`script_generator`) and Phase 12 (`animation_generator`) artifacts, executing assembly, validating `AssembledVideo` model payload, and storing results.
- `tests/pipeline/test_assembly_node.py`: Complete test suite for command string validation, subprocess mocking, state ledger integration, error/timeout handling, FD leaks, and temporary file cleanup.
- `PromptBook/Phase13/01_Video_Assembly.md`: Documentation of state ledger contracts, FFmpeg parameters, filter graphs, security constraints, and testing matrix.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | FFmpeg Command Builders | Build 4K (3840x2160) video assembly, concat, subtitle burn-in, and audio merge command list | M1 | R1, R2 |
| 2 | Video Assembler Core | Secure non-shell FFmpeg `subprocess.run()` execution with `close_fds=True`, timeout, and `AssemblyError` handling | M1 | R1, R2 |
| 3 | Video Assembly Node | `VideoAssemblyNode` subclass of `Node` retrieving Phase 11/12 artifacts from `StateLedger` and outputting `AssembledVideo` payload | M1 | R1 |
| 4 | Temp File Cleanup | Explicit `tempfile.TemporaryDirectory` / `try...finally` cleanup logic for intermediate SRT/concat files | M1 | R2 |
| 5 | Assembly Unit Tests | `tests/pipeline/test_assembly_node.py` validating command strings, mocks, state ledger, timeouts, FD leaks, temp cleanup | M2 | Acceptance Criteria |
| 6 | FFmpeg Documentation | `PromptBook/Phase13/01_Video_Assembly.md` detailing FFmpeg architecture, filter graphs, and security | M3 | R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Assembly Core & Node | `src/assembly/ffmpeg_commands.py`, `src/assembly/assembler.py`, `src/pipeline/nodes/video_assembly_node.py` | None | DONE |
| M2 | Test Suite & Verification | `tests/pipeline/test_assembly_node.py` | M1 | DONE |
| M3 | Architecture Documentation | `PromptBook/Phase13/01_Video_Assembly.md` | M1 | DONE |

## Interface Contracts
### `VideoAssemblyNode` ↔ `StateLedger`
- Input: `get_step_output(run_id, ledger, "animation_generator")` -> returns dict with `"segments"` (`visual_path`, `duration`, etc.) and `get_step_output(run_id, ledger, "script_generator")` -> narration text / SRT / `.wav` audio paths.
- Output: dict matching `AssembledVideo` schema (`slug`, `final_video_path`, `total_duration_seconds`, `file_size_bytes`, `segments`, `assembled_at`).

### `VideoAssembler` ↔ FFmpeg Subprocess
- Subprocess args: `List[str]`, `shell=False`, `close_fds=True`, `check=False`, `capture_output=True`, `text=True`, `timeout=300.0`.
- Exception: raises `AssemblyError(PipelineError)` on non-zero exit code or `subprocess.TimeoutExpired`.

## Code Layout
- `src/assembly/ffmpeg_commands.py`
- `src/assembly/assembler.py`
- `src/pipeline/nodes/video_assembly_node.py`
- `tests/pipeline/test_assembly_node.py`
- `PromptBook/Phase13/01_Video_Assembly.md`
