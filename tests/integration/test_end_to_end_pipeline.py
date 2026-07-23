"""
End-to-End Integration Tests (Phase 14)

Validates the full chronological pipeline from Phase 09 (Scraping) through Phase 13 (Publishing)
without executing actual LLM API calls or launching multi-hour C-level renders.
"""
import pytest
from unittest.mock import MagicMock

from src.core.orchestrator.pipeline import PipelineOrchestrator
from src.core.media.artifact_manager import ArtifactManager


@pytest.fixture
def mock_artifact_manager(tmp_path):
    """Provides a zero-byte ephemeral disk space for artifact tracking."""
    manager = ArtifactManager(str(tmp_path))
    return manager


@pytest.fixture
def orchestrator(mock_artifact_manager):
    """
    Builds the Orchestrator and stubs all heavy external subsystems.
    This guarantees sub-millisecond execution times in CI/CD.
    """
    orc = PipelineOrchestrator(artifact_manager=mock_artifact_manager)
    
    orc.scraper = MagicMock()
    orc.rag = MagicMock()
    orc.planner = MagicMock()
    orc.voice = MagicMock()
    orc.renderer = MagicMock()
    orc.assembler = MagicMock()
    orc.publisher = MagicMock()
    
    return orc


def test_full_successful_pipeline_run(orchestrator):
    """Verifies a clean, end-to-end traversal of all phase states."""
    
    # Configure Mocks
    orchestrator.scraper.scrape.return_value = {"problem": "Two Sum"}
    orchestrator.rag.generate_context.return_value = "RAG Context"
    orchestrator.planner.generate.return_value = ("Script", "AnimPlan", "NarrPlan")
    
    # Execute
    url = "https://leetcode.com/problems/two-sum"
    result = orchestrator.run_single_problem(url)
    
    # Assert Success
    assert result is True
    
    # Verify Phase Transitions
    state = orchestrator._load_or_create_state(url)
    assert state.status == "completed"
    assert state.current_phase == "DONE"
    
    # Verify Every Subsystem Was Successfully Bridged
    orchestrator.scraper.scrape.assert_called_once()
    orchestrator.rag.generate_context.assert_called_once()
    orchestrator.planner.generate.assert_called_once()
    orchestrator.voice.generate_voice.assert_called_once()
    orchestrator.renderer.render_scene.assert_called_once()
    orchestrator.assembler.assemble_final_video.assert_called_once()
    orchestrator.publisher.upload_video.assert_called_once()


def test_crash_resumption_idempotency(orchestrator):
    """
    Simulates a mid-pipeline crash (e.g. at Phase 13 Media) and verifies
    that upon reboot, Phases 09-12 are STRICTLY bypassed.
    """
    url = "https://leetcode.com/problems/resume-test"
    
    # Force the ledger into an interrupted Phase 13 state (Simulated Crash)
    state = orchestrator._load_or_create_state(url)
    state.current_phase = "PHASE_13"
    orchestrator._save_state(state)
    
    # Execute Pipeline
    result = orchestrator.run_single_problem(url)
    
    # Assert Success
    assert result is True
    
    # CRITICAL: Verify Bypassed Subsystems (LLM and API costs saved!)
    orchestrator.scraper.scrape.assert_not_called()
    orchestrator.rag.generate_context.assert_not_called()
    orchestrator.planner.generate.assert_not_called()
    
    # CRITICAL: Verify Resumed Subsystems
    orchestrator.voice.generate_voice.assert_called_once()
    orchestrator.renderer.render_scene.assert_called_once()
    orchestrator.assembler.assemble_final_video.assert_called_once()
    orchestrator.publisher.upload_video.assert_called_once()


def test_batch_circuit_breaker(orchestrator):
    """
    Verifies that a catastrophic failure in one video does not crash the
    entire batch run, allowing DevOps to review the workflow report later.
    """
    # Force the planner to simulate a catastrophic API outage
    orchestrator.planner.generate.side_effect = Exception("OpenAI API Outage")
    
    urls = ["problem1", "problem2", "problem3"]
    results = orchestrator.run_batch(urls)
    
    # Assert the loop elegantly finished despite the internal crashes
    assert results["success"] == 0
    assert results["failed"] == 3
    assert len(results["errors"]) == 3
    
    # Verify the error messages were trapped gracefully
    assert "OpenAI API Outage" in results["errors"][0]
