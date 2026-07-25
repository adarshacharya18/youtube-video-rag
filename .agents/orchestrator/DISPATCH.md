## 2026-07-25T20:45:56Z

You are the Project Orchestrator for Phase 05: Core Data Models & Schemas of the Automated DSA Educational YouTube Video Pipeline.

Your Working Directory is: /home/adarsh/Documents/Youtube-Channel/.agents/orchestrator
The project root is: /home/adarsh/Documents/Youtube-Channel

Read /home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md for full requirements and acceptance criteria.
Also inspect existing Phase 04 code (`src/core/orchestrator/state_ledger.py`) and schema to align Pydantic models 1-to-1 with the SQLite State Ledger schema.

Key deliverables for Phase 05:
1. `src/core/models/video.py`, `src/core/models/plan.py`, and `src/core/models/assets.py` using Pydantic V2 `BaseModel`. Define models `VideoMetadata`, `EducationalPlan`, `RenderSegment` as specified in user requirements.
2. Strict semantic validation (e.g., segment durations are positive, video resolutions are valid, non-empty strings, ledger alignment).
3. `tests/models/test_validation.py` actively testing malformed JSON, missing fields, wrong types, and semantic violations to verify `ValidationError` is raised.
4. `PromptBook/Phase05/01_Data_Models.md` documenting Pydantic schemas and 1-to-1 mapping with Phase 04 State Ledger.

Follow all teamwork protocols, maintain `.agents/orchestrator/plan.md`, `progress.md`, and `context.md`, spawn specialist subagents (explorers, workers/implementers, reviewers/challengers) as needed, verify all tests pass with pytest, and write handoff.md when ready.
