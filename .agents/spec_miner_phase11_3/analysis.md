# Phase 11 Specification Mining Analysis Report

**Subagent ID**: `spec_miner_phase11_3`  
**Date**: 2026-07-29  
**Target Phase**: Phase 11 — Script & Narration Generation  
**Codebase Root**: `/home/adarsh/Documents/Youtube-Channel`  
**Authoritative Sources**: `ORIGINAL_REQUEST.md`, `src/core/workflow/node.py`, `src/core/workflow/engine.py`, `src/core/orchestrator/state_ledger.py`, `src/core/llm/`, `src/core/models/plan.py`, `src/core/exceptions.py`, `tests/workflow/test_engine.py`, `tests/llm/test_providers.py`.

---

## 1. Executive Summary

Phase 11 implements the **Script & Narration Generation** phase of the Automated DSA Educational YouTube Video Pipeline. It introduces a dedicated `WorkflowEngine` node — `ScriptGeneratorNode` (`src/pipeline/nodes/script_generator_node.py`) — that converts raw Data Structures and Algorithms (DSA) problem data into a timed, highly engaging YouTube script. 

The output script is formatted as a strictly typed Pydantic JSON structure organized around four essential YouTube engagement metrics:
1. **Hook**: Fast-paced opening to grab viewer attention.
2. **Context**: Clear problem statement, intuition, and target scenario.
3. **Solution**: Step-by-step algorithmic breakdown and code implementation walkthrough.
4. **Complexity**: Asymptotic Time & Space complexity analysis.

To guarantee zero malformed outputs during automated workflow execution, `ScriptGeneratorNode` implements a robust **Error-Feedback Retry Loop**. If an LLM response fails Pydantic schema validation or contains invalid JSON (`ValidationError` or `JSONDecodeError`), the node catches the exception, extracts the exact error details, feeds the error message back to the LLM prompt context, and retries the generation.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Workflow Node | `ScriptGeneratorNode` | Pipeline node inheriting from `Node` (`src.core.workflow.node.Node`) executing timed YouTube script generation step. | `run_id: str`, `ledger: StateLedger` | `dict[str, Any]` (JSON payload containing full script breakdown, slug, and status) | Raises `PipelineStageError` if prior step output missing; catches & retries LLM errors up to max_retries before raising `PipelineError`. | `ORIGINAL_REQUEST.md` (R1), `src/core/workflow/node.py` |
| 2 | Pydantic Schema | YouTube Script Pydantic Schema | Models YouTube engagement structure (`Hook`, `Context`, `Solution`, `Complexity`), spoken narration, and visual cues. | Raw LLM JSON dict/string | `YouTubeScript` / `ScriptSchema` model instance | Raises `pydantic.ValidationError` if fields, types, or duration/format invariants are violated. | `ORIGINAL_REQUEST.md` (R2), `src/core/models/plan.py` |
| 3 | Error-Feedback | Error-Feedback Retry Loop | Catching `ValidationError` / `JSONDecodeError`, appending exact error text to prompt context, and re-invoking LLM provider. | Prompt, LLM provider, max_retries (default 3) | Validated Pydantic script instance | Retries up to max_retries. If all retries fail, raises `PipelineStageError`. | `ORIGINAL_REQUEST.md` (R2), `src/core/llm/provider.py` |
| 4 | Prompt Engineering | Script Prompt Template | Jinja2 template (`script_generation.j2`) rendering problem context, engagement requirements, and Pydantic output constraints. | `topic`, `slug`, `difficulty`, `description`, `constraints`, `examples`, `code` | Rendered Jinja2 prompt string | Raises `TemplateRenderError` if required Jinja2 variables are missing. | `src/core/llm/prompt_loader.py`, `src/core/llm/prompts/v1/` |
| 5 | Documentation | Phase 11 PromptBook Document | Detailed architecture doc at `PromptBook/Phase11/01_Script_Generation.md` covering schema, retry loop, and metric logic. | N/A (Markdown document) | `PromptBook/Phase11/01_Script_Generation.md` | N/A | `ORIGINAL_REQUEST.md` (R3) |
| 6 | Testing | Node Test Suite | Pytest suite (`tests/pipeline/test_script_node.py`) testing successful generation, corrupted JSON feedback retry recovery, and state ledger integration. | Mock LLM provider, SQLite `:memory:` StateLedger | Test execution pass/fail | Asserts mock LLM call count == 2 (fail then recover) and final payload validity. | `ORIGINAL_REQUEST.md` (Acceptance Criteria) |

---

## 3. Detailed Requirements Mining

### R1. Script Generator Node Specification
- **File Path**: `src/pipeline/nodes/script_generator_node.py`
- **Class Name**: `ScriptGeneratorNode(Node)`
- **Base Class**: `src.core.workflow.node.Node`
- **Properties**:
  - `name`: Returns `"script_generator"` (or `"script"`).
- **Execution Contract**:
  - Signature: `execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]`
  - Workflow:
    1. Fetch run record and previous step outputs (e.g., `"ingest"` or `"plan"`) using `self.get_step_output(run_id, ledger, prior_step_name)`.
    2. Extract problem details (`slug`, `title`, `difficulty`, `description`, `constraints`, `examples`, `accepted_code`).
    3. Render the prompt template using `PromptLoader` (`src/core/llm/prompt_loader.py`).
    4. Call the LLM provider (`OpenAIClient` or `AnthropicClient`) within the Error-Feedback Retry Loop.
    5. Validate response against `ScriptSchema` / `YouTubeScript` Pydantic model.
    6. Return state dictionary payload matching `dict[str, Any]` (e.g. `{"script": script_pydantic.model_dump(), "slug": slug, "status": "completed"}`).

### R2. YouTube Engagement Metrics & Pydantic Schema
The script Pydantic model enforces YouTube video pacing and structure across four primary metric sections:

1. **Hook (`HookSection`)**:
   - Spoken narration designed to intrigue YouTube viewers within the first 15–30 seconds.
   - Associated visual cues (e.g. high-contrast title card, visual problem teaser).
   - Target duration: 15–30 seconds.
2. **Context (`ContextSection`)**:
   - Problem statement breakdown, real-world context, inputs, outputs, and constraints.
   - Spoken narration explaining why brute force is insufficient or what the core challenge is.
   - Associated visual cues (e.g. array/graph visualization setup).
3. **Solution (`SolutionSection`)**:
   - Algorithmic intuition and step-by-step visual walkthrough.
   - Code snippet execution highlights (`code`, `language`, `line_highlights`).
   - Spoken narration walking line-by-line through the solution.
4. **Complexity (`ComplexitySection`)**:
   - Asymptotic analysis: Big-O Time Complexity and Space Complexity.
   - Spoken narration explaining memory/time trade-offs and edge cases.
5. **Top-Level `YouTubeScript` / `ScriptSchema` Model**:
   - `topic`: str
   - `slug`: str (matching `^[a-z0-9-]+$`)
   - `difficulty`: str
   - `hook`: `HookSection`
   - `context`: `ContextSection`
   - `solution`: `SolutionSection`
   - `complexity`: `ComplexitySection`
   - `total_duration`: float (gt 0.0, matching sum of section durations within ±0.1s)
   - `spoken_narration`: list[str] (aggregated narration text)
   - `visual_cues`: list[VisualCue] (all visual animation cues)

### R3. Error-Feedback Retry Loop Architecture
- **Trigger**: Catching `pydantic.ValidationError` or `json.JSONDecodeError` during LLM response parsing/validation.
- **Retry Logic**:
  ```python
  attempt = 0
  max_retries = 3
  last_error = None
  current_prompt = base_prompt

  while attempt < max_retries:
      try:
          response_text = llm_provider.generate(current_prompt)
          parsed_json = json.loads(response_text)
          script_model = YouTubeScript.model_validate(parsed_json)
          return script_model
      except (ValidationError, JSONDecodeError, ValueError) as exc:
          attempt += 1
          last_error = exc
          error_msg = str(exc)
          logger.warning(f"Script generation validation failed (attempt {attempt}/{max_retries}): {error_msg}")
          # Construct feedback prompt
          current_prompt = (
              f"{base_prompt}\n\n"
              f"=== PREVIOUS ATTEMPT FAILED SCHEMA VALIDATION ===\n"
              f"Your previous JSON output was invalid or violated the Pydantic schema.\n"
              f"Exact Error Message: {error_msg}\n"
              f"Please fix all schema and formatting errors and return VALID JSON strictly matching the schema."
          )

  raise PipelineStageError(f"ScriptGeneratorNode failed after {max_retries} attempts: {last_error}")
  ```

### R4. Documentation Requirements (`PromptBook/Phase11/01_Script_Generation.md`)
The documentation file must include:
- Overview of YouTube scripting philosophy (Hook, Context, Solution, Complexity).
- Complete Pydantic Schema model definitions and field descriptions.
- Sequence flow diagram/description of the Error-Feedback Retry Loop.
- Integration instructions with `WorkflowEngine` and `StateLedger`.

### R5. Pytest Structure Requirements (`tests/pipeline/test_script_node.py`)
- **Required Mocking**:
  - Mock LLM provider response sequence:
    - Attempt 1: Return malformed JSON string (e.g. `"{ 'hook': missing_closing_brace"` or JSON missing required `complexity` field).
    - Attempt 2: Return valid, fully populated JSON string matching `YouTubeScript`.
- **Assertions**:
  - Node catches initial validation failure.
  - Node formats feedback prompt containing exact error string (`str(e)`).
  - LLM provider `invoke`/`generate` called exactly twice.
  - Final execution output payload contains valid script data and succeeds.
  - Node records completed step into `StateLedger`.

---

## 4. Codebase Integration & Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                    WorkflowEngine                           │
│              (src/core/workflow/engine.py)                  │
└──────────────────────────────┬──────────────────────────────┘
                               │ execute(run_id, ledger)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   ScriptGeneratorNode                       │
│           (src/pipeline/nodes/script_generator_node.py)     │
└──────┬───────────────────────┬───────────────────────┬──────┘
       │                       │                       │
       ▼                       ▼                       ▼
┌──────────────┐      ┌─────────────────┐      ┌──────────────┐
│ StateLedger  │      │  PromptLoader   │      │ LLM Provider │
│ get_step_    │      │ render(template)│      │  (OpenAI /   │
│ output()     │      │                 │      │  Anthropic)  │
└──────────────┘      └─────────────────┘      └──────┬───────┘
                                                      │
                                                      ▼
                                              ┌───────────────┐
                                              │ Error-Feedback│
                                              │ Retry Loop    │
                                              │ (Max 3)       │
                                              └───────────────┘
```

- **Core Dependencies**:
  - Base Node: `src.core.workflow.node.Node`
  - State Ledger: `src.core.orchestrator.state_ledger.StateLedger`, `PipelineRunRecord`, `StepStatus`
  - Prompt Loader: `src.core.llm.prompt_loader.PromptLoader`
  - LLM Provider: `src.core.llm.provider.BaseLLMProvider`, `OpenAIClient`, `AnthropicClient`
  - Exceptions: `src.core.exceptions.PipelineStageError`, `src.core.exceptions.ValidationError`
  - Pydantic: `pydantic.BaseModel`, `Field`, `field_validator`, `model_validator`

---

## 5. Edge Cases

| # | Feature | Input | Observed / Specified Behavior |
|---|---------|-------|-------------------|
| 1 | Error-Feedback Loop | Malformed JSON on Attempt 1, Valid JSON on Attempt 2 | Node catches `JSONDecodeError`, builds feedback prompt with exact error, re-invokes LLM, and successfully returns script. |
| 2 | Error-Feedback Loop | Missing required field (`complexity`) in Pydantic output | Node catches `ValidationError`, extracts missing field error details, feeds back error to LLM, recovers on retry. |
| 3 | Retry Exhaustion | Corrupted JSON output on all N attempts | Node exhausts max retries (3), raises `PipelineStageError`. `WorkflowEngine` catches exception and sets run status to `FAILED`. |
| 4 | State Ledger Integration | Missing `run_id` in StateLedger | `get_run_record()` raises `PipelineStageError("Pipeline run '...' not found in StateLedger")`. |
| 5 | State Ledger Integration | Missing prior step output (e.g. `"ingest"`) | `get_step_output()` raises `PipelineStageError("Node 'script_generator' requires output from prior step 'ingest'")`. |
| 6 | Duration Validation | `estimated_total_duration` mismatch with sum of section durations (> 0.1s difference) | Pydantic `@model_validator` raises `ValidationError`, triggering retry loop. |
| 7 | Slug Formatting | Capital letters or special symbols in slug (`"Two_Sum!"`) | Pydantic regex validator `^[a-z0-9-]+$` fails, triggering retry loop. |
| 8 | Empty Problem Input | Empty or whitespace-only problem description from ledger | Node raises `PipelineStageError` before LLM call to save tokens/API costs. |

---

## 6. Verification & Acceptance Criteria Matrix

| Deliverable File | Role | Acceptance Criteria |
|------------------|------|---------------------|
| `src/pipeline/nodes/script_generator_node.py` | Pipeline Node Implementation | Inherits from `Node`, uses `PromptLoader` and LLM abstraction, executes `StateLedger` input/output lookups, implements Error-Feedback Retry Loop. |
| `src/models/script.py` / `src/core/models/script.py` | Pydantic Models | Defines `YouTubeScript`, `HookSection`, `ContextSection`, `SolutionSection`, `ComplexitySection`, `VisualCue` with field validators for duration and slug. |
| `PromptBook/Phase11/01_Script_Generation.md` | SDK & Architecture Documentation | Documents scripting engagement structure (Hook, Context, Solution, Complexity), JSON schema, and Error-Feedback Retry Loop architecture. |
| `tests/pipeline/test_script_node.py` | Pytest Unit & Integration Suite | Tests end-to-end execution, mocks LLM returning corrupted JSON on attempt 1 & valid JSON on attempt 2, asserts recovery and error feedback construction. |
