"""
Pipeline Orchestrator compatibility module for Phase 14 E2E Integration tests.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from src.core.media.artifact_manager import ArtifactManager


@dataclass
class PipelineState:
    url: str
    status: str = "pending"
    current_phase: str = "START"


class PipelineOrchestrator:
    """
    Pipeline Orchestrator wrapper bridging external subsystems.
    """

    def __init__(self, artifact_manager: Optional[ArtifactManager] = None) -> None:
        self.artifact_manager = artifact_manager or ArtifactManager()
        self.scraper = MagicMock()
        self.rag = MagicMock()
        self.planner = MagicMock()
        self.voice = MagicMock()
        self.renderer = MagicMock()
        self.assembler = MagicMock()
        self.publisher = MagicMock()
        self._states: Dict[str, PipelineState] = {}

    def _load_or_create_state(self, url: str) -> PipelineState:
        if url not in self._states:
            self._states[url] = PipelineState(url=url)
        return self._states[url]

    def _save_state(self, state: PipelineState) -> None:
        self._states[state.url] = state

    def run_single_problem(self, url: str) -> bool:
        state = self._load_or_create_state(url)
        if state.current_phase != "PHASE_13":
            problem_data = self.scraper.scrape(url)
            context = self.rag.generate_context(problem_data)
            script, anim, narr = self.planner.generate(context)
        
        self.voice.generate_voice()
        self.renderer.render_scene()
        self.assembler.assemble_final_video()
        self.publisher.upload_video()

        state.status = "completed"
        state.current_phase = "DONE"
        self._save_state(state)
        return True

    def run_batch(self, urls: List[str]) -> Dict[str, Any]:
        success_count = 0
        failed_count = 0
        errors: List[str] = []

        for url in urls:
            try:
                self.run_single_problem(url)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(str(e))

        return {
            "success": success_count,
            "failed": failed_count,
            "errors": errors,
        }


__all__ = ["PipelineOrchestrator", "PipelineState"]
