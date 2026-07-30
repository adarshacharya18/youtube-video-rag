# Implementation Summary: VideoAssembler `_resolve_command` Fix

## File Modified
- `src/assembly/assembler.py`

## Summary of Changes
Updated `VideoAssembler._resolve_command` (`src/assembly/assembler.py:52-70`) to handle configured `self.ffmpeg_binary` paths without creating duplicate script argument entries when `args[0]` equals `self.ffmpeg_binary` or `"ffmpeg"`.

### Detailed Changes in `_resolve_command`:
1. Check if `args` already starts with exact multi-element binary prefix (`len(prefix) > 1 and args[:len(prefix)] == prefix`) or single-element prefix (`len(prefix) == 1 and args[0] == prefix[0]`).
2. If `self.ffmpeg_binary` is configured and `args[0]` matches either `"ffmpeg"` or `self.ffmpeg_binary`, strip `args[0]` and append `args[1:]` to `prefix`:
   ```python
   if self.ffmpeg_binary and (args[0] == "ffmpeg" or args[0] == self.ffmpeg_binary):
       return prefix + list(args[1:])
   ```
3. Otherwise, prepend `prefix` to `args`.

## Rationale
When `self.ffmpeg_binary` is a Python script (e.g. `/tmp/mock.py`), `prefix` resolves to `[sys.executable, '/tmp/mock.py']`. Previously, when `args[0]` was `'/tmp/mock.py'`, `args[0] == prefix[0]` was `False` (comparing `/tmp/mock.py` to `python3`) and `args[0] == "ffmpeg"` was `False`, causing `prefix + list(args)` to produce duplicate script arguments (`['python3', '/tmp/mock.py', '/tmp/mock.py', ...]`). Slicing `args[1:]` when `args[0] == self.ffmpeg_binary` eliminates duplicate script path arguments.

## Verification
- Verified with python test matrix covering mock Python scripts, binary executables, default `ffmpeg`, full prefixes, and relative argument lists.
- Verified existing test suite `pytest tests/pipeline/test_assembly_node.py tests/workflow/` (53 passed).
