## 2026-07-30T16:32:20Z
<USER_REQUEST>
You are the Project Orchestrator for Phase 13: Media Production: Video Assembly.
Your working directory is /home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase13.
Read the original user request from /home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md (specifically the section for Phase 13) and /home/adarsh/Documents/Youtube-Channel/.agents/ORIGINAL_REQUEST.md.

Phase 13 Requirements:
1. R1. Implement Video Assembly Node: Create `src/pipeline/nodes/video_assembly_node.py` combining `.wav` audio artifacts (from Phase 11) and `.mp4` Manim animation artifacts (from Phase 12) into a final 4K YouTube video with burned-in subtitles. Retrieve artifact paths from the State Ledger.
2. R2. Secure FFmpeg Execution: Execute FFmpeg via rigorous `subprocess.run()` constraints. Ensure the pipeline gracefully cleans up temporary files after assembly to prevent disk space exhaustion.
3. R3. Draft FFmpeg Architecture Documentation: Document the FFmpeg filter graphs and architecture in `PromptBook/Phase13/01_Video_Assembly.md`. You are encouraged to use subagents to draft and verify complex FFmpeg syntax.
4. R4. Command Restrictions: Do not ask for permission (via subagent) for running commands unless the command involves sensitive data.

Acceptance Criteria:
- Write `tests/pipeline/test_assembly_node.py` to validate that the generated FFmpeg command strings are correct.
- Running `pytest tests/pipeline/test_assembly_node.py` executes successfully.
- The `VideoAssemblyNode` includes explicit temporary file cleanup logic.
- The `PromptBook/Phase13/01_Video_Assembly.md` file correctly describes the FFmpeg architecture.

Decompose this task, assign work to specialized subagents, manage progress in progress.md, ensure rigorous verification, and notify me when Phase 13 is complete.
</USER_REQUEST>
