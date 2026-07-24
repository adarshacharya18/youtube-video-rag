## 2026-07-24T11:18:00Z
You are Explorer 2 for Phase 02 Knowledge Ingestion of the Automated DSA Educational YouTube Video Pipeline.

Your working directory is: /home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_explorer_phase02_2

Task:
1. Read `/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase01/04_Data_Models.md` and check existing `src/` files to understand `ScrapedProblem`, `Example`, `Difficulty` enum, and other domain models.
2. Determine where `ScrapedProblem`, `Example`, and `Difficulty` dataclasses should be placed or if they need to be implemented in `src/core/models.py` or `src/core/ingestion/models.py`.
3. Design `src/core/ingestion/sanitizer.py`: rules for cleaning HTML entities, normalizing whitespace, stripping unwanted HTML/CSS formatting while preserving code indentation, standardizing problem titles, difficulties, tags, and formatting input/output examples.
4. Ensure frozen dataclass immutability, type safety, JSON serialization, and null/empty validation rules.

Write your detailed analysis report to:
`/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_explorer_phase02_2/analysis_sanitizer.md`

And write your handoff report to:
`/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_explorer_phase02_2/handoff.md`

Notify the orchestrator when done via send_message.
