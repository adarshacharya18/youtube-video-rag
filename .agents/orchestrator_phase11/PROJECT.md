# Project: Phase 11 - Script & Narration Generation

## Architecture
- Pipeline Node: `ScriptGeneratorNode` inheriting from core `Node` (`src/core/workflow/node.py` or similar).
- Schema: Pydantic models for YouTube engagement sections (Hook, Context, Solution, Complexity), containing spoken narration and visual cues.
- Retry Engine: Error-feedback loop catching `pydantic.ValidationError` and `json.JSONDecodeError`, passing raw LLM output + error string back to LLM for retry.
- Prompt Book: `PromptBook/Phase11/01_Script_Generation.md`.
- Test Suite: `tests/pipeline/test_script_node.py` with mock LLM calls testing error correction retry.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Node Core | `ScriptGeneratorNode` inheriting from core `Node` | M1 | ORIGINAL_REQUEST.md |
| 2 | Pydantic Schema | Script model with spoken narration, visual cues, Hook/Context/Solution/Complexity | M1 | ORIGINAL_REQUEST.md |
| 3 | Retry Loop | Catch `ValidationError` / `JSONDecodeError`, append error prompt, retry LLM | M1 | ORIGINAL_REQUEST.md |
| 4 | Documentation | `PromptBook/Phase11/01_Script_Generation.md` | M1 | ORIGINAL_REQUEST.md |
| 5 | Unit Tests | `tests/pipeline/test_script_node.py` with 2-pass mock LLM recovery | M1 | ORIGINAL_REQUEST.md |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Phase 11 Implementation | Script generator node, Pydantic schema, retry loop, docs, unit tests | none | DONE |
