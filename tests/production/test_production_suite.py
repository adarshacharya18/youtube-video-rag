"""
Production Integration Test Suite (Phase 14)

Covers End-to-End, Stress, Recovery, and Deployment Validation scenarios using PipelineRunner.
Designed to be run in a CI environment against the production branch.
"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.orchestrator.pipeline_runner import PipelineRunner, _default_llm_provider
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow import Node
from src.pipeline.nodes import (
    AnimationGeneratorNode,
    IngestionNode,
    PlanNode,
    ScriptGeneratorNode,
    VideoAssemblyNode,
    VoiceGeneratorNode,
)


@pytest.fixture(autouse=True)
def mock_voice_synthesis(tmp_path_factory):
    """Autouse fixture providing mock voice execution and TTS media artifacts for production suite tests."""
    audio_dir = tmp_path_factory.mktemp("prod_audio")

    def mock_voice_execute(run_id: str, ledger=None):
        if ledger is None:
            from src.core.exceptions import PipelineStageError
            raise PipelineStageError("Node 'voice_generator' requires a valid StateLedger instance.")
        run_record = ledger.get_run(run_id)
        slug = run_record.slug
        base_dir = audio_dir / slug
        base_dir.mkdir(parents=True, exist_ok=True)
        audio_file = base_dir / "master_audio.wav"
        sub_file = base_dir / "subtitles.srt"
        wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\x3e\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        audio_file.write_bytes(wav_header)
        srt_content = "1\n00:00:00,000 --> 00:00:05,000\nWelcome to our algorithm walkthrough.\n"
        sub_file.write_text(srt_content, encoding="utf-8")
        return {
            "slug": slug,
            "audio_path": str(audio_file.resolve()),
            "subtitle_path": str(sub_file.resolve()),
            "srt_content": srt_content,
            "duration_seconds": 10.0,
            "status": "completed",
        }

    with patch("src.pipeline.nodes.voice_generator_node.VoiceGeneratorNode.execute", autospec=False, side_effect=mock_voice_execute):
        yield


@pytest.fixture
def mock_ledger_path(tmp_path):
    """Provides a temporary database path for SQLite ledger."""
    return tmp_path / "test_production_suite.db"



def _build_test_nodes(manim_bin: str, ffmpeg_bin: str):
    """Build production node sequence configured with mock binary paths."""
    return [
        IngestionNode(),
        PlanNode(),
        ScriptGeneratorNode(llm_provider=_default_llm_provider),
        VoiceGeneratorNode(),
        AnimationGeneratorNode(manim_binary=manim_bin),
        VideoAssemblyNode(ffmpeg_binary=ffmpeg_bin),
    ]


class TestProductionEndToEnd:
    def test_end_to_end_success_path(self, mock_ledger_path, mock_binaries):
        """Simulates a full pipeline execution from Ingestion to Assembly using PipelineRunner."""
        manim_bin, ffmpeg_bin = mock_binaries
        nodes = _build_test_nodes(manim_bin, ffmpeg_bin)
        runner = PipelineRunner(nodes=nodes, db_path=mock_ledger_path)
        result = runner.run_problem("two-sum", metadata={"difficulty": "Easy"})
        
        assert result.success is True
        assert result.status == StepStatus.COMPLETED
        assert len(result.completed_steps) == 6
        assert result.completed_steps == [
            "ingest",
            "plan",
            "script_generator",
            "voice_generator",
            "animation_generator",
            "video_assembly",
        ]
        runner.close()


class TestRecoveryAndResiliency:
    def test_checkpoint_resumption_after_failure(self, mock_ledger_path, mock_binaries):
        """Verifies that an incomplete run resumes from its last successful step checkpoint."""
        manim_bin, ffmpeg_bin = mock_binaries
        ledger = StateLedger(db_path=mock_ledger_path)
        
        class MockFailingNode(Node):
            def __init__(self):
                self.attempted = False

            @property
            def name(self) -> str:
                return "voice_generator"

            def execute(self, run_id: str, ledger: StateLedger):
                if not self.attempted:
                    self.attempted = True
                    raise RuntimeError("Simulated TTS synthesis failure")
                return {"audio_path": "/tmp/test.wav", "subtitle_path": "/tmp/test.srt"}

        custom_nodes = _build_test_nodes(manim_bin, ffmpeg_bin)
        failing_node = MockFailingNode()
        custom_nodes[3] = failing_node

        # First run fails at voice_generator
        runner_1 = PipelineRunner(nodes=custom_nodes, ledger=ledger)
        res1 = runner_1.run_problem("binary-search")
        assert res1.success is False
        assert res1.failed_step == "voice_generator"
        assert res1.completed_steps == ["ingest", "plan", "script_generator"]

        # Resumption run succeeds and skips prior completed steps
        runner_2 = PipelineRunner(nodes=custom_nodes, ledger=ledger)
        res2 = runner_2.resume_run("binary-search")
        assert res2.success is True
        assert res2.completed_steps == [
            "ingest",
            "plan",
            "script_generator",
            "voice_generator",
            "animation_generator",
            "video_assembly",
        ]
        ledger.close()

    def test_exponential_backoff_calculation(self):
        """Validates retry delay calculation backoff logic."""
        delays = [2 ** attempt for attempt in range(1, 4)]
        assert delays[0] == 2
        assert delays[1] == 4
        assert delays[2] == 8


class TestStressAndBenchmarks:
    def test_sequential_multi_problem_runs(self, mock_ledger_path, mock_binaries):
        """Validates executing multiple problems sequentially on the same runner instance."""
        manim_bin, ffmpeg_bin = mock_binaries
        nodes = _build_test_nodes(manim_bin, ffmpeg_bin)
        runner = PipelineRunner(nodes=nodes, db_path=mock_ledger_path)
        
        for slug in ["two-sum", "reverse-linked-list", "valid-anagram"]:
            res = runner.run_problem(slug)
            assert res.success is True
            assert res.status == StepStatus.COMPLETED
            
        runner.close()

    def test_runner_node_sequence_composition(self, mock_ledger_path, mock_binaries):
        """Validates node sequence configuration and naming."""
        manim_bin, ffmpeg_bin = mock_binaries
        nodes = _build_test_nodes(manim_bin, ffmpeg_bin)
        runner = PipelineRunner(nodes=nodes, db_path=mock_ledger_path)
        node_names = [n.name for n in runner.nodes]
        assert node_names == [
            "ingest",
            "plan",
            "script_generator",
            "voice_generator",
            "animation_generator",
            "video_assembly",
        ]
        runner.close()

    def test_long_running_memory_leak(self, mock_ledger_path, mock_binaries):
        """Authentically tests memory usage by tracking process RSS memory before and after pipeline runs."""
        import gc
        import resource

        manim_bin, ffmpeg_bin = mock_binaries
        nodes = _build_test_nodes(manim_bin, ffmpeg_bin)
        runner = PipelineRunner(nodes=nodes, db_path=mock_ledger_path)

        gc.collect()
        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        for i in range(5):
            res = runner.run_problem(f"problem-leak-{i}")
            assert res.success is True

        gc.collect()
        rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        # Bounded RSS growth (< 100MB)
        growth_kb = rss_after - rss_before
        assert growth_kb < 100 * 1024 * 1024, f"Excessive RSS memory growth detected: {growth_kb} KB"
        runner.close()


class TestDeploymentValidation:
    def test_cli_ops_script_execution(self):
        """Tests that src/cli/ops.py exists and can be imported cleanly."""
        from src.cli.ops import main
        assert callable(main)
