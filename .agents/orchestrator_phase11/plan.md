# Execution Plan — Phase 11: Script & Narration Generation

## Objectives
1. Script Generator Node (`src/pipeline/nodes/script_generator_node.py`) inheriting from core `Node`.
2. Pydantic schema for the script JSON (spoken narration, visual cues, YouTube engagement metrics: Hook, Context, Solution, Complexity).
3. Error-Feedback Retry Loop catching `ValidationError` or `JSONDecodeError` and feeding exact error string back to LLM.
4. Documentation in `PromptBook/Phase11/01_Script_Generation.md`.
5. Test suite in `tests/pipeline/test_script_node.py` mocking LLM to return corrupted JSON on call 1, valid JSON on call 2, verifying retry recovery.

## Workflow Phases
- **Phase 0: Survey** — Spawn Explorers / Spec Miners to map `src/core/node.py` or existing Node hierarchy, LLM abstraction, prompt library, and test setup.
- **Phase 1: Implementation** — Spawn Worker to write `src/pipeline/nodes/script_generator_node.py`, `PromptBook/Phase11/01_Script_Generation.md`, and `tests/pipeline/test_script_node.py`.
- **Phase 2: Verification** — Spawn Reviewers, Challengers, and Forensic Auditor.
- **Phase 3: Gate & Delivery** — Gate evaluation in `GATE_STATUS.md` and claim victory to Sentinel.
