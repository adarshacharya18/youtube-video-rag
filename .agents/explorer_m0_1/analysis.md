# Phase 14 Milestone M0 Exploration Analysis Report

## Executive Summary
This report provides a comprehensive architectural investigation of the video generation pipeline codebase at `/home/adarsh/Documents/Youtube-Channel/src/` in preparation for Phase 14 Integration & Production Orchestration. It catalogs existing workflow engine components, state management primitives, event bus mechanisms, and pipeline node implementations (`ScriptGeneratorNode`, `AnimationGeneratorNode`, `VideoAssemblyNode`), details how data/artifacts flow across step boundaries via the SQLite `StateLedger`, and proposes the detailed design for `src/core/orchestrator/pipeline_runner.py` and master CLI integration.

---

## 1. Codebase Inventory & Component Assessment

### 1.1 Core Workflow Engine (`src/core/workflow/`)
* **`src/core/workflow/node.py` (`Node` Abstract Base Class)**
  * **Role**: Interface contract for all modular execution nodes in the pipeline.
  * **Key Interface Methods**:
    * `@property name(self) -> str`: Unique step identifier (e.g., `'ingest'`, `'plan'`, `'script_generator'`, `'voice_generator'`, `'animation_generator'`, `'video_assembly'`).
    * `execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]`: Step processing logic. Communicates strictly via `StateLedger` using `run_id`.
    * `get_run_record(run_id, ledger) -> PipelineRunRecord`: Fetches run record from `StateLedger` or raises `PipelineStageError`.
    * `get_completed_step_outputs(run_id, ledger) -> dict[str, dict[str, Any]]`: Returns mapping of all completed step names to their recorded `output_payload` dictionaries.
    * `get_step_output(run_id, ledger, step_name) -> dict[str, Any]`: Retrieves specific prior step's output payload or raises `PipelineStageError`.
  * **Constraint Enforcement**: Direct in-memory state object passing between node instances is strictly prohibited. Nodes communicate exclusively via SQLite `StateLedger`.

* **`src/core/workflow/engine.py` (`WorkflowEngine`)**
  * **Role**: Synchronous, fault-tolerant execution orchestrator.
  * **Key Attributes & Methods**:
    * `__init__(self, nodes: Sequence[Node], ledger: Optional[StateLedger] = None, event_bus: Optional[EventBus] = None)`
    * `run(run_id: str) -> EngineResult` (aliases: `execute`, `run_pipeline`).
  * **Execution Lifecycle**:
    1. Validates `run_id` existence in `StateLedger`.
    2. Retrieves previously completed step records via `ledger.get_completed_steps(run_id)`.
    3. Iterates sequentially over `self.nodes`:
       * **Idempotency Check**: If `node.name` is recorded as `COMPLETED` in `StateLedger`, execution is skipped, its cached `output_payload` is loaded into `outputs`, and execution advances to the next node.
       * **Step Start**: Calls `ledger.record_step_start(run_id, node.name)` -> returns `step_id`. Emits `NodeStarted(run_id, node.name, step_id)` on `EventBus`.
       * **Execution**: Invokes `node.execute(run_id, self.ledger)`.
       * **Completion**: Calls `ledger.record_step_completion(step_id, output)`, emits `NodeCompleted(run_id, node.name, step_id, output)`.
       * **Failure Trap**: Catches any exception, records failure via `ledger.record_step_failure(step_id, error_message, error_details)` (which updates parent run status to `FAILED`), emits `NodeFailed(...)`, halts loop, and returns `EngineResult(success=False, failed_step=node.name, status=StepStatus.FAILED)`.

### 1.2 Event Bus Architecture (`src/core/events/`)
* **`src/core/events/bus.py` (`EventBus`)**
  * **Event Models**:
    * `BaseEvent(timestamp: str)`
    * `NodeStarted(run_id: str, node_name: str, step_id: str)`
    * `NodeCompleted(run_id: str, node_name: str, step_id: str, output: Any)`
    * `NodeFailed(run_id: str, node_name: str, step_id: str, error_message: str, error_details: Any)`
  * **Fault Tolerance**: `EventBus.publish(event)` catches and suppresses all exceptions raised by subscriber listeners, guaranteeing listener failures never halt core pipeline execution.

### 1.3 Persistence & State Tracking (`src/core/orchestrator/state_ledger.py`)
* **`StateLedger`**
  * **Storage Engine**: SQLite in WAL mode with `busy_timeout=5000` and thread locking (`threading.Lock()`).
  * **Schemas**:
    * `pipeline_runs`: `pipeline_run_id` (PK), `slug`, `status`, `created_at`, `updated_at`, `metadata`.
    * `step_executions`: `step_execution_id` (PK), `pipeline_run_id` (FK), `step_name`, `status`, `input_payload`, `output_payload`, `error_message`, `error_details`, `created_at`, `updated_at`.
  * **Status States** (`StepStatus` Enum): `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`.

---

## 2. Pipeline Node Inventory & Data Flow Analysis

### 2.1 Existing Pipeline Nodes (`src/pipeline/nodes/`)

| Node Class | Step Name (`name`) | Primary Inputs (from `StateLedger`) | Primary Outputs (to `StateLedger`) | Key Logic / Subsystems |
|---|---|---|---|---|
| `ScriptGeneratorNode` | `"script_generator"` | Prior outputs: `"plan"`, `"educational_plan"`, `"ingest"`, or run metadata `slug`. | `{"script": dict, "slug": str, "topic": str, "status": "completed"}` | LLM prompt rendering + Error-Feedback Retry Loop validating against Pydantic `YouTubeScript` schema. |
| `AnimationGeneratorNode` | `"animation_generator"` | Prior output: `"script_generator"` (`slug`, `visual_cues`). | `{"slug": str, "segments": list[RenderSegment], "render_count": int, "output_directory": str, "status": "completed"}` | Maps visual cues to Manim scene templates (`ArrayScene`, `TreeScene`, etc.), renders MP4s via isolated subprocesses with SHA-256 caching. |
| `VideoAssemblyNode` | `"video_assembly"` | Prior output: `"animation_generator"` (`segments`) and `"voice_generator"`/`"script_generator"` (`audio_path`, `subtitle_path`, `srt_content`). | Dict representation of `AssembledVideo` model (`slug`, `final_video_path`, `total_duration_seconds`, `file_size_bytes`, `segments`, `assembled_at`). | Combines MP4 animation clips, WAV voice audio, and SRT subtitles using FFmpeg via `VideoAssembler` into 4K video. |

### 2.2 Complete 6-Stage Chronological Sequence

To construct the complete `Ingestion -> Plan -> Script -> TTS -> Manim -> FFmpeg` pipeline:

```
┌────────────────────────┐
│  Stage 1: Ingestion    │ step_name: "ingest"
└───────────┬────────────┘
            │ Output: { slug, title, problem_description, difficulty, code, constraints, examples }
            ▼
┌────────────────────────┐
│  Stage 2: Plan         │ step_name: "plan"
└───────────┬────────────┘
            │ Output: { slug, topic, difficulty, plan_sections, teaching_plan }
            ▼
┌────────────────────────┐
│  Stage 3: Script       │ step_name: "script_generator" (ScriptGeneratorNode)
└───────────┬────────────┘
            │ Output: { script: YouTubeScript, slug, topic, status: "completed" }
            ▼
      ┌─────┴───────────────────────────────────┐
      │                                         │
      ▼                                         ▼
┌────────────────────────┐            ┌────────────────────────┐
│  Stage 4: TTS          │            │  Stage 5: Manim        │
│  (voice_generator)     │            │  (animation_generator) │
└───────────┬────────────┘            └─────────┬──────────────┘
            │ Output: { audio_path,             │ Output: { segments: list[RenderSegment],
            │   subtitle_path, srt_content }    │   output_directory, render_count }
            │                                   │
            └─────────────────┬─────────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │  Stage 6: FFmpeg       │ step_name: "video_assembly"
                  │  (video_assembly)      │ (VideoAssemblyNode)
                  └────────────────────────┘
                              │ Output: AssembledVideo model dict
                              ▼
                  Final 4K Video Artifact
```

---

## 3. Detailed Design Proposal for `src/core/orchestrator/pipeline_runner.py`

### 3.1 Architecture Overview
`PipelineRunner` serves as the high-level orchestration wrapper over `WorkflowEngine`, `StateLedger`, and `EventBus`. It provides a clean, production-grade interface for launching, resuming, querying, and managing multi-stage video generation pipeline runs.

### 3.2 Detailed Class Blueprint

```python
"""
Pipeline Runner Orchestrator for Phase 14 Production Execution.

Chronologically links all pipeline nodes (Ingestion -> Plan -> Script -> TTS -> Manim -> FFmpeg)
into a cohesive, crash-resilient execution pipeline with step resumption and event tracking.
"""

from pathlib import Path
from typing import Any, List, Optional, Sequence

from src.core.events import BaseEvent, EventBus
from src.core.exceptions import PipelineError
from src.core.logger import get_logger
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow import EngineResult, Node, WorkflowEngine
from src.pipeline.nodes import (
    AnimationGeneratorNode,
    ScriptGeneratorNode,
    VideoAssemblyNode,
)

logger = get_logger(__name__)


class PipelineRunner:
    """
    Production Orchestrator for end-to-end DSA video generation pipelines.
    
    Coordinates node sequence construction, state ledger tracking, event bus emissions,
    crash resumption, and operational metrics reporting.
    """

    def __init__(
        self,
        nodes: Optional[Sequence[Node]] = None,
        ledger: Optional[StateLedger] = None,
        event_bus: Optional[EventBus] = None,
        db_path: str = "data/state_ledger.db",
    ) -> None:
        self.ledger = ledger if ledger is not None else StateLedger(db_path)
        self.event_bus = event_bus if event_bus is not None else EventBus()
        self.nodes = list(nodes) if nodes else self._build_default_nodes()
        self.engine = WorkflowEngine(
            nodes=self.nodes,
            ledger=self.ledger,
            event_bus=self.event_bus,
        )

    def _build_default_nodes(self) -> List[Node]:
        """Construct the default 6-stage production node sequence."""
        # Note: Concrete wrappers for Ingestion, Plan, and TTS nodes will be included
        return [
            ScriptGeneratorNode(),
            AnimationGeneratorNode(),
            VideoAssemblyNode(),
        ]

    def run_problem(
        self,
        slug: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> EngineResult:
        """
        Execute pipeline for a problem slug. Automatically creates run or resumes existing run.
        """
        existing_run = self.ledger.get_run_by_slug(slug)
        if existing_run is not None and existing_run.status != StepStatus.COMPLETED:
            logger.info("Resuming existing incomplete run for slug", slug=slug, run_id=existing_run.pipeline_run_id)
            run_id = existing_run.pipeline_run_id
        else:
            run_id = self.ledger.create_run(slug, metadata=metadata)
            logger.info("Created new pipeline run", slug=slug, run_id=run_id)

        return self.engine.run(run_id)

    def resume_run(self, run_id: str) -> EngineResult:
        """Resume an existing pipeline run by run_id."""
        run_record = self.ledger.get_run(run_id)
        if run_record is None:
            raise PipelineError(f"Cannot resume: run_id '{run_id}' not found in StateLedger.")
        logger.info("Resuming pipeline run", run_id=run_id, slug=run_record.slug)
        return self.engine.run(run_id)

    def get_status(self, run_id_or_slug: str) -> dict[str, Any]:
        """Query execution status and progress for a run_id or slug."""
        run_record = self.ledger.get_run(run_id_or_slug)
        if run_record is None:
            run_record = self.ledger.get_run_by_slug(run_id_or_slug)
        if run_record is None:
            return {"found": False, "query": run_id_or_slug}

        completed_steps = self.ledger.get_completed_steps(run_record.pipeline_run_id)
        return {
            "found": True,
            "run_id": run_record.pipeline_run_id,
            "slug": run_record.slug,
            "status": run_record.status.value if hasattr(run_record.status, "value") else str(run_record.status),
            "created_at": run_record.created_at,
            "updated_at": run_record.updated_at,
            "completed_steps": list(completed_steps.keys()),
            "total_nodes": len(self.nodes),
        }

    def subscribe_event(self, event_type: type, listener: Any) -> None:
        """Subscribe external listener to pipeline event bus."""
        self.event_bus.subscribe(event_type, listener)
```

---

## 4. Master CLI Integration (`src/cli/ops.py`)

To fulfill Requirement R1 in Phase 14 (`ops.py` Master CLI commands: `run`, `status`, `resume`, `health`):
* `ops.py run --slug <slug>`: Calls `PipelineRunner.run_problem(slug)`.
* `ops.py resume --run-id <run_id>`: Calls `PipelineRunner.resume_run(run_id)`.
* `ops.py status [--run-id <id> / --slug <slug>]`: Invokes `PipelineRunner.get_status(...)`.
* `ops.py health`: Checks SQLite connectivity, FFmpeg binary availability, Manim availability, and output directory write permissions.

---

## 5. Summary of Recommended Implementation Actions for Milestone M1

1. **Implement `PipelineRunner` in `src/core/orchestrator/pipeline_runner.py`**:
   - Link nodes, handle `run_problem`, `resume_run`, `get_status`, and delegate execution to `WorkflowEngine`.
2. **Update Master CLI (`src/cli/ops.py`)**:
   - Add `run` and `resume` subparsers and connect `status` and `health` commands to real `StateLedger` and `PipelineRunner` calls.
3. **Write E2E Integration Tests in `tests/production/test_pipeline_e2e.py`**:
   - Test end-to-end execution across nodes.
   - Test crash resumption idempotency (skipping completed steps).
   - Test failure propagation and state ledger recording.
4. **Draft Operational Documentation (`PromptBook/Phase14/01_Production_Orchestration.md`)**:
   - Document CLI usage, runbook recovery procedures, and pipeline architecture.
