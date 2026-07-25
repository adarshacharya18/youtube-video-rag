# Context Memory - Phase 05: Core Data Models & Schemas

## User Goal
Implement Pydantic V2 models for `VideoMetadata`, `EducationalPlan`, and `RenderSegment` in `src/core/models/video.py`, `src/core/models/plan.py`, and `src/core/models/assets.py`. Ensure 1-to-1 mapping with Phase 04 SQLite State Ledger (`src/core/orchestrator/state_ledger.py`), strict semantic validation, `tests/models/test_validation.py`, and `PromptBook/Phase05/01_Data_Models.md`.

## Key Workspace Paths
- Project Root: `/home/adarsh/Documents/Youtube-Channel`
- Orchestrator Working Dir: `/home/adarsh/Documents/Youtube-Channel/.agents/orchestrator`
- Original Request: `/home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md`
- State Ledger Code: `src/core/orchestrator/state_ledger.py`

## Active Constraints
- Orchestrator must DISPATCH work only (no writing implementation code or running tests directly).
- Files to edit for orchestrator are strictly within `.agents/orchestrator/`.
- Pydantic V2 BaseModel required.
- Forensic Auditor gate mandatory.
