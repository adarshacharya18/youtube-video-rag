## 2026-07-30T16:35:22Z
You are Explorer M1-2 (teamwork_preview_explorer).
Your working directory is /home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_2.

OBJECTIVE:
Formulate exact design specifications and code snippets for `src/assembly/assembler.py`.
Specifically:
1. Design `VideoAssembler` class with `assemble(...)` method.
2. Formulate secure non-shell `subprocess.run(..., close_fds=True, timeout=300.0, capture_output=True, text=True)` invocation.
3. Map non-zero exit codes, stdout/stderr error outputs, and `subprocess.TimeoutExpired` to `AssemblyError` (`src/core/exceptions.py:140`).
4. Design robust temporary file management (`tempfile.TemporaryDirectory()`, writing concat lists / SRT files, ensuring cleanup in `finally` block).

INPUT INFORMATION:
- Read ORIGINAL_REQUEST.md: `/home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md` (Phase 13 section).
- Scope document: `/home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase13/SCOPE.md`.
- Prior survey analysis: `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_1/analysis.md`.

OUTPUT REQUIREMENTS:
Write detailed design to `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_2/analysis.md` and handoff report to `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_2/handoff.md`.

COMPLETION CRITERIA:
- Complete class definition, method signatures, and execution logic for `VideoAssembler` in `src/assembly/assembler.py`.
- Handoff report published and message sent to orchestrator parent.
