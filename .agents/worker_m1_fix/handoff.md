# Handoff Report: Worker M1 Fix — `_resolve_command` Bug Fix

## 1. Observation
- **Modified File**: `src/assembly/assembler.py` (lines 52-70).
- **Issue Description**: When `self.ffmpeg_binary` is configured to a Python script (e.g., `mock_ffmpeg.py`), `prefix` resolves to `[sys.executable, '/path/to/mock.py']`. Previously, if `args[0]` was `'/path/to/mock.py'`, `_resolve_command` did not strip `args[0]`, resulting in duplicate script path arguments (`['python3', '/path/to/mock.py', '/path/to/mock.py', ...]`).
- **Executed Command Verification Output**:
  - Python verification script testing 7 command resolution scenarios: all 7 assertions passed.
  - `PYTHONPATH=. pytest tests/pipeline/test_assembly_node.py tests/workflow/ -v`: 53 passed, 0 failures.

## 2. Logic Chain
1. In `VideoAssembler._resolve_binary_command()`, if `ffmpeg_binary` ends with `.py`, `prefix` is `[sys.executable, self.ffmpeg_binary]`.
2. In `VideoAssembler._resolve_command(args)`, if `args[0]` matches `self.ffmpeg_binary` or `"ffmpeg"`, the leading command entry in `args` is redundant because `prefix` already includes the executable binary / script.
3. Updated `_resolve_command` to check `if self.ffmpeg_binary and (args[0] == "ffmpeg" or args[0] == self.ffmpeg_binary): return prefix + list(args[1:])`.
4. If `args` already begins with the full `prefix` (`args[:len(prefix)] == prefix`), `_resolve_command` returns `list(args)` without modification.
5. This prevents argument duplication for both Python script binaries and binary executable paths.

## 3. Caveats
- No caveats. The fix directly addresses the root cause in `_resolve_command` without altering external contract interfaces or module dependencies.

## 4. Conclusion
- The `_resolve_command` bug identified by Reviewer M1-2 in `src/assembly/assembler.py` is fully fixed and verified against unit and regression tests.

## 5. Verification Method
To independently verify:
1. **Command Resolution Verification Script**:
   ```bash
   python3 -c "
   import sys
   from src.assembly.assembler import VideoAssembler
   assembler = VideoAssembler(ffmpeg_binary='/tmp/mock.py')
   cmd = ['/tmp/mock.py', '-y', '-i', 'in.mp4']
   resolved = assembler._resolve_command(cmd)
   assert resolved == [sys.executable, '/tmp/mock.py', '-y', '-i', 'in.mp4']
   "
   ```
2. **Run Pytest Suite**:
   ```bash
   PYTHONPATH=. pytest tests/pipeline/test_assembly_node.py tests/workflow/ -v
   ```
