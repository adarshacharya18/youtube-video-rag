## 2026-07-30T16:35:22Z
You are Explorer M1-1 (teamwork_preview_explorer).
Your working directory is /home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_1.

OBJECTIVE:
Formulate exact design specifications and code snippets for `src/assembly/ffmpeg_commands.py`.
Specifically:
1. Design pure helper functions: `build_assembly_command(...)`, `build_concat_filter_graph(...)`, `build_subtitle_filter(...)`, `build_4k_scale_filter(...)`.
2. Ensure command options use list format (never shell string): `["ffmpeg", "-y", "-i", ...]` with parameters for 4K resolution (3840x2160), 30 fps, video codec (`libx264`), pixel format (`yuv420p`), audio codec (`aac`), audio bitrate (`384k`), CRF (`18`), and subtitle burning (`subtitles=...`).
3. Handle edge cases like escaping path strings for FFmpeg `subtitles` filter graph.

INPUT INFORMATION:
- Read ORIGINAL_REQUEST.md: `/home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md` (Phase 13 section).
- Scope document: `/home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase13/SCOPE.md`.
- Prior survey analysis: `/home/adarsh/Documents/Youtube-Channel/.agents/spec_miner_1/spec_analysis.md`.

OUTPUT REQUIREMENTS:
Write detailed design to `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_1/analysis.md` and handoff report to `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_1/handoff.md`.

COMPLETION CRITERIA:
- Complete function signatures and implementation logic for `src/assembly/ffmpeg_commands.py`.
- Handoff report published and message sent to orchestrator parent.
