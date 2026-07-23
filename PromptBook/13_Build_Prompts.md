# Master Build Prompts: Phase 01 to Phase 15

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  

This document contains the master prompt templates to instruct AI agents to build out each of the 15 phases of the DSA Pipeline from scratch. Each prompt is designed to be fed individually into the agent's context, utilizing specific global skills, ensuring context passes from one phase to the next, and strictly enforcing the pipeline's architectural paradigms.

---

## Phase 01: Initial Setup & Global Architecture

```markdown
<USER_REQUEST>
/skill senior-architect
/skill python-pro

Implement Phase 01: Initial Setup & Global Architecture.

**Context:**
We are building an Automated DSA Educational YouTube Video Pipeline. This is a massive, multi-hour batch processing system. The architecture must strictly adhere to a Synchronous Batch-Pipeline paradigm—we are explicitly forbidding complex asynchronous event buses and dynamic DI containers in favor of linear, predictable, fail-fast execution.

**Preparation:**
- Review the core concept of a headless video generation pipeline.
- Define the global folder structure for `src/`, `tests/`, `scripts/`, and `PromptBook/`.
- Establish the `01_Global_Rules.md` outlining Python conventions (PEP 8, static typing, structural logging).

**Build:**
- Create the foundational `src/core/base.py` and `src/core/exceptions.py`.
- Define the global configuration loaders in `src/core/config.py`.
- Scaffold the `PromptBook/Phase01/` documentation outlining the high-level architecture.

**Testing:**
- Create unit tests in `tests/core/test_config.py` to validate environment variable loading.

**Instructions:**
You are authorized to use `invoke_subagent` to delegate research or parallel documentation tasks. Take as much time as you need. Do all necessary research to establish a robust foundation, and build this phase to the absolute highest production standards.
</USER_REQUEST>
```

---

## Phase 02: Knowledge Ingestion

```markdown
<USER_REQUEST>
/skill rag-engineer
/skill python-pro

Implement Phase 02: Knowledge Ingestion.

**Context:**
Building on the `src/core/config.py` established in Phase 01, we now need to ingest raw DSA problems (e.g., from LeetCode repositories or Markdown files). The ingestion layer must cleanly parse problem descriptions, constraints, and optimal solutions into standardized Python dataclasses.

**Preparation:**
- Review the configuration structures from Phase 01.
- Research optimal markdown parsing strategies and AST extraction for Python/C++ solution code.

**Build:**
- Create `src/core/ingestion/parser.py` to parse raw Markdown/HTML DSA problems.
- Create `src/core/ingestion/sanitizer.py` to clean and standardize the parsed data.
- Document the ingestion pipeline in `PromptBook/Phase02/01_Ingestion_Strategy.md`.

**Testing:**
- Write robust tests in `tests/ingestion/test_parser.py` using mock Markdown files as fixtures.

**Instructions:**
You are authorized to use subagents to handle complex parsing logic. Take your time, do thorough research on edge cases in markdown formatting, and ensure the parsed output is perfectly deterministic.
</USER_REQUEST>
```

---

## Phase 03: RAG & Knowledge Organization

```markdown
<USER_REQUEST>
/skill rag-implementation
/skill database-architect

Implement Phase 03: RAG & Knowledge Organization.

**Context:**
With raw DSA problems parsed in Phase 02 (`src/core/ingestion/parser.py`), we must now chunk, embed, and store these problems in a Vector Database to enable semantic search when the system needs to cross-reference similar algorithms.

**Preparation:**
- Review Phase 02's ingestion output schemas.
- Research the optimal chunking strategy for code vs. text to preserve algorithmic context.

**Build:**
- Implement `src/core/rag/embedder.py` (e.g., using OpenAI `text-embedding-3-small`).
- Implement `src/core/rag/vector_store.py` to persist the embeddings locally (e.g., ChromaDB or FAISS).
- Document the chunking and retrieval strategy in `PromptBook/Phase03/01_RAG_Architecture.md`.

**Testing:**
- Create `tests/rag/test_vector_store.py` to verify that embedding similarity queries correctly return the ingested mock problems.

**Instructions:**
Use subagents if you need to research the latest embedding dimensionality best practices. Take as much time as needed to build a highly accurate retrieval system.
</USER_REQUEST>
```

---

## Phase 04: Runtime Architecture & State Ledger

```markdown
<USER_REQUEST>
/skill senior-architect
/skill database-architect

Implement Phase 04: Runtime Architecture & State Ledger.

**Context:**
Relying on the foundations from Phases 01-03, we need to enforce pipeline idempotency. Because rendering a video takes 12 hours, if the pipeline crashes at hour 11, it must be able to resume exactly where it left off. We will manage this using a strict SQLite State Ledger.

**Preparation:**
- Review the Synchronous Batch-Pipeline rules from Phase 01.
- Research SQLite write-ahead logging (WAL) for thread-safe state tracking.

**Build:**
- Implement `src/core/orchestrator/state_ledger.py` utilizing SQLite to track the status (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`) of every video generation step.
- Document the state machine and recovery logic in `PromptBook/Phase04/01_Runtime_Architecture.md`.

**Testing:**
- Write `tests/orchestrator/test_state_ledger.py` to prove that interrupted processes can successfully recover their state from disk.

**Instructions:**
This is the most critical resilience layer of the platform. Delegate to subagents for deep SQLite research if needed. Take your time and ensure flawless transactional integrity.
</USER_REQUEST>
```

---

## Phase 05: Core Data Models & Schemas

```markdown
<USER_REQUEST>
/skill python-pro
/skill llm-structured-output

Implement Phase 05: Core Data Models & Schemas.

**Context:**
With the State Ledger (Phase 04) ready to track data, we must define the strict Python `dataclasses` and `Pydantic` models that represent the data flowing through the pipeline (e.g., `VideoMetadata`, `EducationalPlan`, `RenderSegment`).

**Preparation:**
- Review the SQLite schema from Phase 04 to ensure 1-to-1 mapping.
- Establish Pydantic validation rules to prevent bad data from reaching the rendering engine.

**Build:**
- Create `src/core/models/video.py`, `src/core/models/plan.py`, and `src/core/models/assets.py`.
- Document the data contracts in `PromptBook/Phase05/01_Data_Models.md`.

**Testing:**
- Write `tests/models/test_validation.py` to ensure Pydantic strictly rejects malformed JSON.

**Instructions:**
Feel free to use subagents to rapidly scaffold the boilerplate Pydantic models. Ensure all fields are rigorously typed.
</USER_REQUEST>
```

---

## Phase 06: LLM Provider Abstraction

```markdown
<USER_REQUEST>
/skill llm-application-dev-langchain-agent
/skill python-pro

Implement Phase 06: LLM Provider Abstraction.

**Context:**
Relying on the strict Pydantic models from Phase 05, we need to abstract our interactions with external LLMs (OpenAI, Anthropic) so we can easily swap providers if an API goes down.

**Preparation:**
- Review the Pydantic schemas in `src/core/models/`.
- Research how to wrap external LLM SDKs behind a unified Python `Protocol` or Abstract Base Class.

**Build:**
- Implement `src/core/llm/provider.py` defining the interface.
- Implement `src/core/llm/openai_client.py` and `src/core/llm/anthropic_client.py`.
- Document the provider strategy in `PromptBook/Phase06/01_LLM_Abstraction.md`.

**Testing:**
- Write `tests/llm/test_providers.py` using mock API responses to ensure both clients return identically formatted Pydantic objects.

**Instructions:**
Take your time. Use subagents to research the latest SDK changes for OpenAI/Anthropic. Build a highly resilient wrapper that gracefully handles rate limits and retries.
</USER_REQUEST>
```

---

## Phase 07: Prompt Library & Management

```markdown
<USER_REQUEST>
/skill prompt-engineering-patterns
/skill python-pro

Implement Phase 07: Prompt Library & Management.

**Context:**
With the LLM Abstraction layer (Phase 06) complete, we need a centralized system to load, format, and version the massive system prompts required to generate the educational scripts.

**Preparation:**
- Review the LLM provider interfaces.
- Research best practices for storing prompt templates (e.g., Jinja2 or formatted markdown files).

**Build:**
- Create `src/core/llm/prompt_loader.py` to read versioned prompts from disk.
- Write the foundational prompt templates for "Educational Plan Generation" and "Code Explanation".
- Document the prompt guidelines in `PromptBook/Phase07/01_Prompt_Library.md`.

**Testing:**
- Write `tests/llm/test_prompt_loader.py` to ensure variable interpolation (e.g., inserting a DSA problem into the template) works flawlessly.

**Instructions:**
Prompt engineering is an art. Use subagents to draft and refine the prompt templates. Take all the time needed to ensure the prompts extract maximum reasoning from the LLMs.
</USER_REQUEST>
```

---

## Phase 08: The Workflow Engine

```markdown
<USER_REQUEST>
/skill senior-architect
/skill python-pro

Implement Phase 08: The Workflow Engine.

**Context:**
Now that we have State Ledgers (Phase 04) and LLM capabilities (Phases 06/07), we need the Workflow Engine. This engine will execute a linear sequence of "Nodes" (e.g., Node 1: Ingest, Node 2: Plan, Node 3: Script, Node 4: Render), writing the result of each node to the State Ledger.

**Preparation:**
- Review the Synchronous Batch-Pipeline paradigm (Phase 01) and the State Ledger (Phase 04).
- Define a strict `Node` abstract class.

**Build:**
- Implement `src/core/workflow/engine.py` and `src/core/workflow/node.py`.
- Ensure the engine wraps every node execution in a try/except block that gracefully updates the SQLite ledger to `FAILED` on error.
- Document the engine mechanics in `PromptBook/Phase08/01_Workflow_Engine.md`.

**Testing:**
- Write `tests/workflow/test_engine.py` to verify that the engine correctly halts execution and logs errors if a node fails.

**Instructions:**
You may use subagents to design the sequence diagrams. Build this engine to be as robust and fault-tolerant as possible.
</USER_REQUEST>
```

---

## Phase 09: Plugin SDK

```markdown
<USER_REQUEST>
/skill python-pro
/skill senior-architect

Implement Phase 09: Plugin SDK.

**Context:**
Building on the Workflow Engine (Phase 08), we need an SDK that allows third-party developers to write custom `Node` implementations (e.g., a custom Manim animation node) without modifying the core pipeline code.

**Preparation:**
- Review `src/core/workflow/node.py`.
- Research Python `importlib.metadata` and entry points for dynamic plugin loading.

**Build:**
- Create `src/sdk/plugin_base.py` and `src/core/workflow/plugin_loader.py`.
- Document how developers should structure their plugins in `PromptBook/Phase09/01_Plugin_SDK.md`.

**Testing:**
- Write `tests/workflow/test_plugin_loader.py` to ensure the core pipeline can securely discover and instantiate a mock external plugin.

**Instructions:**
Take your time to design a clean, semantic API surface for developers. Use subagents to prototype the dynamic module loading logic.
</USER_REQUEST>
```

---

## Phase 10: Script & Narration Generation

```markdown
<USER_REQUEST>
/skill llm-application-dev-langchain-agent
/skill prompt-engineering-patterns

Implement Phase 10: Script & Narration Generation.

**Context:**
Utilizing the Workflow Engine (Phase 08) and Prompt Library (Phase 07), implement the specific pipeline nodes responsible for turning a raw DSA problem into a timed, highly engaging YouTube script.

**Preparation:**
- Review the Pydantic data models for `VideoMetadata` (Phase 05).
- Research YouTube engagement metrics to inform the scripting structure (Hook, Context, Solution, Complexity).

**Build:**
- Implement `src/pipeline/nodes/script_generator_node.py`.
- Ensure the node outputs a perfectly structured JSON payload containing the spoken narration and visual cues.
- Document the scripting logic in `PromptBook/Phase10/01_Script_Generation.md`.

**Testing:**
- Write `tests/pipeline/test_script_node.py` mocking the LLM to verify the node correctly parses the JSON script output.

**Instructions:**
Use subagents to research the best pedagogical structures for teaching algorithms. Build the node to aggressively retry if the LLM fails to return valid JSON.
</USER_REQUEST>
```

---

## Phase 11: Media Production: TTS & Audio

```markdown
<USER_REQUEST>
/skill bash-pro
/skill python-pro

Implement Phase 11: Media Production: TTS & Audio.

**Context:**
With the script generated in Phase 10, the pipeline must now convert the text into high-quality audio using local TTS binaries (e.g., Kokoro TTS) and manage the resulting `.wav` artifacts.

**Preparation:**
- Review the `subprocess.run()` rules for isolating external C/C++ binaries.
- Review the State Ledger (Phase 04) to ensure audio artifact paths are persisted to SQLite.

**Build:**
- Implement `src/pipeline/nodes/tts_generator_node.py`.
- Implement robust OS-level error handling (e.g., catching out-of-memory errors from the TTS engine).
- Document the audio pipeline in `PromptBook/Phase11/01_Audio_Production.md`.

**Testing:**
- Write `tests/pipeline/test_tts_node.py` using a mock bash script to simulate the TTS binary outputting a `.wav` file.

**Instructions:**
You are authorized to use subagents to handle the specific CLI flag configurations for the TTS engines. Build this to be highly resilient to OS-level failures.
</USER_REQUEST>
```

---

## Phase 12: Media Production: Animation (Manim)

```markdown
<USER_REQUEST>
/skill python-pro
/skill os-scripting

Implement Phase 12: Media Production: Animation (Manim).

**Context:**
With the audio generated in Phase 11, the pipeline must use Manim (Math Animation Engine) to render the visual representations of the algorithms.

**Preparation:**
- Review the visual cues generated in the script from Phase 10.
- Research how to securely invoke Manim via Python `subprocess.run()` without leaking memory between renders.

**Build:**
- Implement `src/pipeline/nodes/animation_generator_node.py`.
- Ensure the node maps the visual cues to pre-built Manim scene templates.
- Document the rendering boundaries in `PromptBook/Phase12/01_Animation_Production.md`.

**Testing:**
- Write `tests/pipeline/test_animation_node.py` to verify that the node correctly stitches together the Manim CLI commands.

**Instructions:**
Manim rendering is the most computationally expensive part of the pipeline. Use subagents to thoroughly research Manim caching and memory management. Take all the time needed to ensure absolute stability.
</USER_REQUEST>
```

---

## Phase 13: Media Production: Video Assembly (FFmpeg)

```markdown
<USER_REQUEST>
/skill bash-pro
/skill python-pro

Implement Phase 13: Media Production: Video Assembly.

**Context:**
With the `.wav` audio (Phase 11) and `.mp4` Manim animations (Phase 12) sitting on disk, the pipeline must stitch them together, burn in subtitles, and produce the final 4K YouTube video.

**Preparation:**
- Review the artifact paths stored in the State Ledger.
- Research FFmpeg filter graphs for concatenating video and syncing audio.

**Build:**
- Implement `src/pipeline/nodes/video_assembly_node.py`.
- Utilize rigorous `subprocess.run()` constraints to execute FFmpeg.
- Document the FFmpeg architecture in `PromptBook/Phase13/01_Video_Assembly.md`.

**Testing:**
- Write `tests/pipeline/test_assembly_node.py` to validate the generated FFmpeg command strings.

**Instructions:**
FFmpeg commands can be incredibly complex. Delegate to subagents to draft and verify the FFmpeg syntax. Ensure the pipeline gracefully cleans up temporary files after assembly to prevent disk space exhaustion.
</USER_REQUEST>
```

---

## Phase 14: Integration & Production Orchestration

```markdown
<USER_REQUEST>
/skill devops-deploy
/skill observability-engineer

Implement Phase 14: Integration & Production Orchestration.

**Context:**
All individual nodes (Ingestion -> Plan -> Script -> TTS -> Manim -> FFmpeg) are built. We must now integrate them into a single, cohesive, production-ready pipeline executable via a master CLI.

**Preparation:**
- Review all previous nodes and the Workflow Engine (Phase 08).
- Research best practices for building command-line operational tools (`ops.py`).

**Build:**
- Implement `src/cli/ops.py` with commands like `run`, `status`, `resume`, and `health`.
- Implement `src/core/orchestrator/pipeline_runner.py` to link the nodes chronologically.
- Document the operational runbooks and startup procedures in `PromptBook/Phase14/01_Production_Orchestration.md`.

**Testing:**
- Write comprehensive end-to-end integration tests in `tests/production/test_pipeline_e2e.py`.

**Instructions:**
Take your time to orchestrate the entire symphony. Use subagents to draft the operational documentation. Ensure the CLI is highly intuitive for human DevOps engineers.
</USER_REQUEST>
```

---

## Phase 15: Platform Evolution & Analytics

```markdown
<USER_REQUEST>
/skill data-engineer
/skill senior-architect

Implement Phase 15: Platform Evolution & Analytics.

**Context:**
The pipeline is fully operational (Phase 14). To ensure long-term survival, we must implement the Platform Evolution subsystems: Model Fallbacks, Prompt A/B Testing, Analytics Dashboards, and safe Upgrade Managers.

**Preparation:**
- Review the State Ledger (Phase 04) and LLM Provider logic (Phase 06).
- Research moving average calculations for detecting quality regressions in LLM outputs.

**Build:**
- Implement `src/core/evolution/model_manager.py` (Circuit breakers).
- Implement `src/core/evolution/prompt_manager.py` (A/B testing kill-switches).
- Implement `src/cli/evolve.py` for headless analytics extraction.
- Document the evolution architecture in `PromptBook/Phase15/01_Platform_Evolution.md`.

**Testing:**
- Write `tests/evolution/test_evolution_suite.py` to mathematically prove that the regression kill-switch safely aborts failing experimental prompts.

**Instructions:**
You are authorized to spawn subagents to design the analytics data structures. Do all necessary research. Build this evolution layer so the platform can continuously, safely improve itself without human intervention.
</USER_REQUEST>
```
