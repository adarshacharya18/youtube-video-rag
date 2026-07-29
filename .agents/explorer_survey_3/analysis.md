# Phase 08 Workflow Engine Documentation Survey & Specification Analysis

## 1. Executive Summary

This report delivers a comprehensive survey of documentation standards across `PromptBook/` (specifically Phases 01, 05, 06, and 07) and defines the exact requirements and structure for `PromptBook/Phase08/01_Workflow_Engine.md` to satisfy **Requirement R3** and the **Acceptance Criteria** for **Phase 08 (The Workflow Engine)**.

### Key Survey Findings:
1. **Directory State**: `PromptBook/Phase08/` directory exists. However, `PromptBook/Phase08/01_Workflow_Engine.md` does **not** exist yet. It must be authored as part of Phase 08 implementation.
2. **Prior Art Conventions**: Architectural deliverables in `PromptBook/` adhere to a consistent 6-to-7 section template featuring executive summaries, class/interface blueprints, Mermaid diagrams (`graph TD` and `sequenceDiagram`), exception matrices, state persistence contracts, and Pytest verification guides.
3. **Core Architectural Alignment**: Phase 08 documentation must formally specify the **Synchronous Batch-Pipeline** execution model, where `Node` instances in `src/core/workflow/node.py` interact exclusively with the `StateLedger` (SQLite WAL mode) via a `run_id`, guaranteeing true pipeline idempotency without passing in-memory state objects down the chain.

---

## 2. PromptBook Directory Structure & Prior Docs Survey

### 2.1 Directory Structure Overview
The `PromptBook/` repository root contains phase-indexed directories (`Phase01/` through `Phase15/`) as well as foundational root-level architectural documents (`01_Global_Rules.md`, `02_Project_Architecture.md`, `11_Workflow_Engine.md`, etc.).

#### Key Deliverables in Examined Phases:
- **Phase 01 (`PromptBook/Phase01/`)**:
  - `01_Global_Rules.md`: Global PEP 8, static typing, and structural logging standards.
  - `02_Synchronous_Batch_Pipeline_Architecture.md`: Defines explicit architectural guarantees (synchronous sequential execution, no dynamic DI, no complex async event buses).
  - `05_Error_Handling.md`: Centralized exception hierarchy (`PipelineError`, `RetryableError`, `FatalError`) and graceful degradation flowcharts.
- **Phase 05 (`PromptBook/Phase05/`)**:
  - `01_Data_Models.md`: Documents Pydantic V2 schemas (`VideoMetadata`, `EducationalPlan`, `RenderSegment`) and 1-to-1 SQLite State Ledger mapping reference.
- **Phase 06 (`PromptBook/Phase06/`)**:
  - `01_LLM_Abstraction.md`: Resilient LLM provider abstraction (`BaseLLMProvider`, `OpenAIClient`, `AnthropicClient`), exponential backoff retry flow chart, exception translation matrix.
- **Phase 07 (`PromptBook/Phase07/`)**:
  - `01_Prompt_Library.md`: Centralized Jinja2 prompt loader engine (`PromptLoader`), versioning hierarchy, StrictUndefined mode, CoT prompt engineering guidelines.
- **Phase 08 (`PromptBook/Phase08/`)**:
  - Contains initial placeholder files (`01_Persistence_Architecture.md`, `02_Storage_Manager.md`, etc.).
  - **Missing Target File**: `01_Workflow_Engine.md` must be created to document the node abstraction, fault-tolerant execution engine, sequence diagrams, and test suite.

---

## 3. Documentation Conventions & Styling Standards

From surveying `Phase01`, `Phase05`, `Phase06`, and `Phase07`, the following mandatory documentation standards must be observed:

### 3.1 Structure & Heading Hierarchy
1. **Document Title**: Top-level `# Phase 08: Workflow Engine Architecture`.
2. **Numbered Sections**: `# 1. Executive Summary & Architecture Overview`, `# 2. Node Abstraction & Idempotency Strategy`, etc.
3. **Section Dividers**: Major sections separated by horizontal rules (`---`).
4. **Subsections**: Use `##` and `###` with bolded parameter names and typed code blocks.

### 3.2 Mermaid Diagram Conventions
- **Flow/Component Diagrams**: Use `graph TD` or `graph LR` with clear component boxes and directional arrows.
- **Sequence Diagrams**:
  - Header: `sequenceDiagram`.
  - Participant declarations with aliases:
    ```mermaid
    sequenceDiagram
        participant E as WorkflowEngine
        participant N as Node (Ingest/Plan/Script/Render)
        participant L as StateLedger (SQLite)
    ```
  - Message Types:
    - `->>` for synchronous method invocation (`E->>L: record_step_start(run_id, step_name)`).
    - `-->>` for return payload / execution result.
    - `--x` or `alt / else` blocks for exception handling and failure recording (`E->>L: record_step_failure(...)`).
  - Notes: `Note over E, L:` to highlight ledger state changes (`IN_PROGRESS`, `COMPLETED`, `FAILED`).

### 3.3 Node Lifecycle & Execution Flow Explanations
Node lifecycle docs must explicitly detail state transitions in the SQLite State Ledger:
- `PENDING` -> Initial state of pipeline run.
- `IN_PROGRESS` -> Recorded via `ledger.record_step_start(run_id, step_name, input_payload)`.
- `COMPLETED` -> Recorded via `ledger.record_step_completion(step_execution_id, output_payload)`.
- `FAILED` -> Recorded via `ledger.record_step_failure(step_execution_id, error_message, error_details)`.

### 3.4 Error Handling & Resiliency Details
Docs must feature a Markdown **Exception Mapping Matrix** table containing:
- Exception Source / Trigger.
- Operational Classification (`RetryableError` vs `FatalError`).
- Ledger Action (`record_step_failure`).
- System Behavior (Halt sequence without process crash, preserve state for resumption).

---

## 4. Required Content Blueprint for `PromptBook/Phase08/01_Workflow_Engine.md`

To satisfy **Requirement R3** and the **Phase 08 Acceptance Criteria**, `PromptBook/Phase08/01_Workflow_Engine.md` must be constructed according to the following 7-part specification:

### 4.1 Section Breakdown & Detailed Contents

#### Section 1: Executive Summary & Workflow Engine Architecture Overview
- High-level overview of the Phase 08 Workflow Engine.
- Reinforce adherence to the Synchronous Batch-Pipeline pattern (no async event buses, no dynamic DI).
- Explain the key objectives: fault-tolerance, idempotency, state-ledger-only state passing, and crash safety.

#### Section 2: Strict Node Abstraction & Idempotency Strategy (`src/core/workflow/node.py`)
- Abstract base class definition `Node(ABC)`:
  - `@abstractmethod def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]`
  - `name: str` attribute for identifying step in ledger.
- Idempotency contract:
  - Nodes inspect `ledger.get_completed_steps(run_id)` before executing heavy compute/LLM/render tasks.
  - If node step is already `COMPLETED`, node returns stored output payload without re-running.
  - Strict prohibition of in-memory object passing down the pipeline chain; all inputs/outputs serialized via Pydantic V2 `.model_dump(mode="json")` to SQLite ledger.

#### Section 3: Fault-Tolerant Workflow Engine Mechanics (`src/core/workflow/engine.py`)
- `WorkflowEngine` class design:
  - Initialization with `StateLedger` instance.
  - `run_pipeline(pipeline_run_id: str, nodes: list[Node]) -> dict[str, Any]`
- Execution Loop logic:
  - Wraps each `node.execute()` in a try/except block.
  - Records step start (`record_step_start`).
  - On success: records step completion (`record_step_completion`).
  - On failure (`except Exception as exc`): catches exception, calls `ledger.record_step_failure(step_execution_id, str(exc), ...)`.
  - Prevents application crash, halts downstream node execution, and returns structured run result with status `FAILED`.

#### Section 4: SQLite State Ledger Data Contract & Schema Mapping
- 1-to-1 integration with Phase 04 `StateLedger` (`src/core/orchestrator/state_ledger.py`).
- Tables updated: `pipeline_runs` and `step_executions`.
- State transitions table detailing how `pipeline_run_id` and `step_execution_id` are updated at each node phase.

#### Section 5: High-Quality Mermaid Sequence Diagrams
Must include at least 3 distinct Mermaid diagrams:
1. **Successful Workflow Execution Sequence**: End-to-end execution of Ingest -> Plan -> Script -> Render nodes with StateLedger status updates.
2. **Fault-Tolerant Error Handling Sequence**: Node exception caught by WorkflowEngine, `record_step_failure` invoked, ledger updated to `FAILED`, process halts gracefully without application crash.
3. **Pipeline Resumption & Idempotency Flow**: Re-running engine on a previously failed or partially completed `run_id`, skipping already `COMPLETED` nodes.

#### Section 6: Exception Taxonomy & Operational Failure Matrix
- Table detailing error scenarios (e.g. Node execution error, Ledger write failure, invalid payload schema).
- Operational classification (`RetryableError` vs `FatalError`).
- Impact on engine and SQLite State Ledger.

#### Section 7: Verification & Test Guide
- Execution command: `pytest tests/workflow/test_engine.py`.
- Test architecture explanation:
  - Verifying mock nodes throwing exceptions update state ledger to `FAILED`.
  - Verifying application does not crash.
  - Verifying state-ledger-only state passing.

---

## 5. Verification & Acceptance Audit

To verify completeness of `PromptBook/Phase08/01_Workflow_Engine.md` during implementation:

| Requirement / Criterion | Verification Standard | Status |
|---|---|---|
| R3 Architectural Documentation | File `PromptBook/Phase08/01_Workflow_Engine.md` exists and details engine mechanics, node lifecycle, and sequence diagrams. | Pending Implementation |
| Acceptance Criteria Diagram Check | File contains high-quality Mermaid sequence diagrams (`sequenceDiagram`) detailing fault-tolerant execution flow. | Pending Implementation |
| Acceptance Criteria Code Parity | File documents `src/core/workflow/node.py` and `src/core/workflow/engine.py` API contracts matching `pytest tests/workflow/test_engine.py`. | Pending Implementation |
