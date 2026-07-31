# Phase 14 Context

## Scope Summary
Phase 14 delivers Integration & Production Orchestration for the YouTube DSA Video Generation Pipeline.

## Key Files to Create/Update
1. `src/cli/ops.py` — Master operational CLI (`run`, `status`, `resume`, `health`).
2. `src/core/orchestrator/pipeline_runner.py` — Production pipeline runner orchestrating all nodes in order: Ingestion -> Plan -> Script -> TTS -> Manim -> FFmpeg.
3. `PromptBook/Phase14/01_Production_Orchestration.md` — Operational runbooks and system startup procedures.
4. `tests/production/test_pipeline_e2e.py` — Comprehensive end-to-end integration tests.

## Key Dependencies & Architecture
- Workflow Engine (`src/core/workflow/engine.py` / `node.py`)
- Event Bus (`src/core/events/bus.py`)
- Existing pipeline nodes:
  - Ingestion / DSA Problem ingestion
  - Plan generation
  - Script generation (`src/pipeline/nodes/script_generator_node.py`)
  - TTS / Narration generation
  - Animation generation (`src/pipeline/nodes/animation_generator_node.py`)
  - Video Assembly (`src/pipeline/nodes/video_assembly_node.py`)
