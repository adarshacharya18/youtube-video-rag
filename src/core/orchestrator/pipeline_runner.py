"""
Pipeline Runner Orchestrator for Phase 14 Production Execution.

Chronologically links all pipeline nodes (Ingestion -> Plan -> Script -> TTS -> Manim -> FFmpeg)
into a cohesive, crash-resilient execution pipeline with step resumption and event tracking.
"""

from pathlib import Path
from typing import Any, List, Optional, Sequence, Union

from src.core.events import EventBus
from src.core.exceptions import PipelineError
from src.core.logger import get_logger
from src.core.orchestrator.state_ledger import PipelineRunRecord, StateLedger, StepStatus
from src.core.workflow import EngineResult, Node, WorkflowEngine
from src.pipeline.nodes import (
    AnimationGeneratorNode,
    IngestionNode,
    PlanNode,
    ScriptGeneratorNode,
    VideoAssemblyNode,
    VoiceGeneratorNode,
)

logger = get_logger(__name__)


def _default_llm_provider(prompt: str) -> dict[str, Any]:
    """Default structured LLM provider fallback for pipeline runner execution."""
    import re
    slug = "problem-slug"
    m_slug = re.search(r"slug:\s*'([^']+)'", prompt)
    if m_slug:
        slug = m_slug.group(1)

    topic = slug.replace("-", " ").title()
    m_topic = re.search(r"topic\s*'([^']+)'", prompt)
    if m_topic:
        topic = m_topic.group(1)

    return {
        "topic": topic,
        "slug": slug,
        "difficulty": "Medium",
        "hook": {
            "title": "Hook",
            "narration": f"Can you solve {topic} efficiently?",
            "visual_cues": [
                {
                    "cue_id": "cue_01",
                    "animation_type": "title_card",
                    "description": f"Show title card for {topic}",
                    "timestamp_seconds": 0.0,
                    "parameters": {},
                }
            ],
            "estimated_duration": 5.0,
        },
        "context": {
            "title": "Context",
            "narration": f"Let's break down the requirements for {topic}.",
            "visual_cues": [],
            "estimated_duration": 10.0,
        },
        "solution": {
            "title": "Solution",
            "narration": "Here is the optimal algorithm implementation.",
            "code_snippet": "def solution():\n    pass",
            "visual_cues": [],
            "estimated_duration": 15.0,
        },
        "complexity": {
            "title": "Complexity",
            "narration": "Time complexity is O(N) and space complexity is O(1).",
            "time_complexity": "O(N)",
            "space_complexity": "O(1)",
            "visual_cues": [],
            "estimated_duration": 5.0,
        },
        "total_duration": 35.0,
        "spoken_narration": [f"Can you solve {topic} efficiently?"],
        "visual_cues": [
            {
                "cue_id": "cue_01",
                "animation_type": "title_card",
                "description": f"Show title card for {topic}",
                "timestamp_seconds": 0.0,
                "parameters": {},
            }
        ],
    }


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
        db_path: Union[str, Path] = "data/state_ledger.db",
    ) -> None:
        """
        Initialize PipelineRunner.

        Args:
            nodes: Optional custom sequence of Node instances. Defaults to the 6-stage production sequence.
            ledger: Optional StateLedger instance. Defaults to StateLedger(db_path).
            event_bus: Optional EventBus instance. Defaults to a new EventBus().
            db_path: Database path used if ledger is not explicitly provided.
        """
        self.ledger: StateLedger = ledger if ledger is not None else StateLedger(db_path)
        self.event_bus: EventBus = event_bus if event_bus is not None else EventBus()
        self.nodes: List[Node] = list(nodes) if nodes is not None else self._build_default_nodes()
        self.engine: WorkflowEngine = WorkflowEngine(
            nodes=self.nodes,
            ledger=self.ledger,
            event_bus=self.event_bus,
        )

    def _build_default_nodes(self) -> List[Node]:
        """
        Construct the default 6-stage chronological production node sequence:
        Ingestion -> Plan -> Script -> TTS -> Manim -> FFmpeg
        """
        return [
            IngestionNode(),
            PlanNode(),
            ScriptGeneratorNode(llm_provider=_default_llm_provider),
            VoiceGeneratorNode(),
            AnimationGeneratorNode(),
            VideoAssemblyNode(),
        ]

    def run_problem(
        self,
        slug: str,
        metadata: Optional[dict[str, Any]] = None,
        force: bool = False,
    ) -> EngineResult:
        """
        Execute pipeline for a problem slug.

        If force=False and an existing incomplete run exists for the slug, it automatically
        resumes that run. If the existing run is COMPLETED (or force=True), a new run is created.

        Args:
            slug: Problem or workflow identifier.
            metadata: Optional metadata dictionary for new run creation.
            force: If True, always creates a new pipeline run regardless of existing state.

        Returns:
            EngineResult: Execution result from WorkflowEngine.
        """
        if not force:
            existing_run = self.ledger.get_run_by_slug(slug)
            if existing_run is not None and existing_run.status != StepStatus.COMPLETED:
                logger.info(
                    "Resuming existing incomplete run for slug",
                    slug=slug,
                    run_id=existing_run.pipeline_run_id,
                    status=existing_run.status,
                )
                return self.engine.run(existing_run.pipeline_run_id)

        run_id = self.ledger.create_run(slug, metadata=metadata)
        logger.info("Created new pipeline run", slug=slug, run_id=run_id)
        return self.engine.run(run_id)

    def create_and_run(
        self,
        slug: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> EngineResult:
        """
        Create a new pipeline run for a problem slug and execute it.

        Args:
            slug: Problem or workflow identifier.
            metadata: Optional metadata dictionary.

        Returns:
            EngineResult: Execution result from WorkflowEngine.
        """
        return self.run_problem(slug, metadata=metadata, force=True)

    def resume_run(self, run_id_or_slug: str) -> EngineResult:
        """
        Resume an existing pipeline run by run_id or slug from its exact checkpoint in StateLedger.

        Args:
            run_id_or_slug: Pipeline run ID (e.g. 'run_123...') or problem slug (e.g. 'two-sum').

        Returns:
            EngineResult: Execution result from WorkflowEngine.

        Raises:
            PipelineError: If run_id_or_slug is not found in StateLedger.
        """
        run_record = self.ledger.get_run(run_id_or_slug)
        if run_record is None:
            run_record = self.ledger.get_run_by_slug(run_id_or_slug)

        if run_record is None:
            logger.error("Cannot resume: run or slug not found in StateLedger", query=run_id_or_slug)
            raise PipelineError(f"Cannot resume: run or slug '{run_id_or_slug}' not found in StateLedger.")

        logger.info(
            "Resuming pipeline run from StateLedger checkpoint",
            run_id=run_record.pipeline_run_id,
            slug=run_record.slug,
            current_status=run_record.status,
        )
        return self.engine.run(run_record.pipeline_run_id)

    def get_status(self, run_id_or_slug: str) -> dict[str, Any]:
        """
        Query execution status and step details for a run_id or slug.

        Args:
            run_id_or_slug: Pipeline run ID or problem slug.

        Returns:
            dict containing found status, run details, completed steps, and total nodes.
        """
        run_record = self.ledger.get_run(run_id_or_slug)
        if run_record is None:
            run_record = self.ledger.get_run_by_slug(run_id_or_slug)

        if run_record is None:
            return {"found": False, "query": run_id_or_slug}

        completed_steps = self.ledger.get_completed_steps(run_record.pipeline_run_id)
        status_val = run_record.status.value if hasattr(run_record.status, "value") else str(run_record.status)

        step_details = []
        for name, rec in completed_steps.items():
            step_details.append({
                "step_name": name,
                "step_id": rec.step_execution_id,
                "status": rec.status.value if hasattr(rec.status, "value") else str(rec.status),
                "created_at": rec.created_at,
                "updated_at": rec.updated_at,
            })

        return {
            "found": True,
            "run_id": run_record.pipeline_run_id,
            "slug": run_record.slug,
            "status": status_val,
            "created_at": run_record.created_at,
            "updated_at": run_record.updated_at,
            "completed_steps": list(completed_steps.keys()),
            "total_nodes": len(self.nodes),
            "step_details": step_details,
        }

    def subscribe_event(self, event_type: type, listener: Any) -> None:
        """Subscribe external listener to pipeline event bus lifecycle events."""
        self.event_bus.subscribe(event_type, listener)

    def run(self, run_id: str) -> EngineResult:
        """Alias for WorkflowEngine.run(run_id)."""
        return self.engine.run(run_id)

    def close(self) -> None:
        """Close state ledger connection."""
        if hasattr(self.ledger, "close"):
            self.ledger.close()

    def __enter__(self) -> "PipelineRunner":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
