# Handoff Report: Reviewer M1-2 — Phase 13 Milestone 1 Code Review

## 1. Observation
- **Reviewed Code Files**:
  - `src/assembly/ffmpeg_commands.py`: pure command builder functions.
  - `src/assembly/assembler.py`: `VideoAssembler` subprocess wrapper.
  - `src/pipeline/nodes/video_assembly_node.py`: `VideoAssemblyNode` workflow node.
  - `tests/pipeline/test_assembly_node.py`: Phase 13 assembly test suite.
- **Executed Test Output**:
  - `PYTHONPATH=. pytest tests/pipeline/test_assembly_node.py -v`: 22 passed in 1.79s.
  - `PYTHONPATH=. pytest tests/workflow/ -v`: 22 passed in 0.38s.
- **Adversarial Bug Discovery**:
  - In `src/assembly/assembler.py:52-70`, `_resolve_command(['/tmp/mock.py', '-y', ...])` returned `['/usr/bin/python3', '/tmp/mock.py', '/tmp/mock.py', '-y', ...]`.
  - The script path `/tmp/mock.py` was duplicated in the argument list when `self.ffmpeg_binary` is a Python script (`.py`).

## 2. Logic Chain
1. `VideoAssembler.assemble()` calls `build_assembly_command(..., ffmpeg_binary=self.ffmpeg_binary or "ffmpeg")`.
2. When `self.ffmpeg_binary` is configured to a Python script (e.g. `/tmp/mock.py`), `build_assembly_command` sets `args[0] = '/tmp/mock.py'`.
3. `VideoAssembler.run_command` calls `_resolve_command(args)`.
4. `_resolve_command` computes `prefix = [sys.executable, '/tmp/mock.py']`.
5. `args[0]` (`'/tmp/mock.py'`) does not match `prefix[0]` (`/usr/bin/python3`) and does not match `'ffmpeg'`.
6. `_resolve_command` falls back to `return prefix + list(args)`, yielding `['/usr/bin/python3', '/tmp/mock.py', '/tmp/mock.py', '-y', ...]`.
7. This passes `/tmp/mock.py` as `sys.argv[1]` to the python script, causing CLI argument checks expecting flags like `-y` at index 1 to fail.

## 3. Caveats
- `tests/pipeline/test_assembly_node.py` passed because `test_assembler_subprocess_failure` and `test_assembler_successful_mock_execution` used `patch.object(assembler, "run_command", ...)`, which mocked `run_command` directly and bypassed execution of `_resolve_command`.
- No integrity violations (hardcoded test results or facade implementations) were found in the codebase.

## 4. Conclusion
- **Verdict**: `REQUEST_CHANGES`
- The core design, StateLedger integration, FFmpeg filter graph generation, and Pydantic models are well-built and align with Phase 13 requirements. However, `src/assembly/assembler.py` must fix `_resolve_command` to handle `args[0] == self.ffmpeg_binary` without duplicating the script path.

## 5. Verification Method
To verify the bug and fix:
1. **Reproduce Command Resolution Bug**:
   ```bash
   python3 -c "
   from src.assembly.assembler import VideoAssembler
   assembler = VideoAssembler(ffmpeg_binary='/tmp/mock.py')
   cmd = ['/tmp/mock.py', '-y']
   resolved = assembler._resolve_command(cmd)
   print('Resolved:', resolved)
   assert resolved == [assembler._resolve_binary_command()[0], '/tmp/mock.py', '-y']
   "
   ```
2. **Run Pytest Unit Suite**:
   ```bash
   PYTHONPATH=. pytest tests/pipeline/test_assembly_node.py -v
   ```
