"""Empirical Test Harness for Phase 14 M1 Challenger 2.

Empirical verification of crash recovery, step idempotency, state ledger tracking,
and resumption capabilities in PipelineRunner and src/cli/ops.py resume.
"""

import json
from pathlib import Path
import tempfile
from typing import Any, Dict, Optional
import pytest

from src.cli.ops import main as ops_main
from src.core.exceptions import PipelineError, ScriptGenerationError
from src.core.orchestrator.pipeline_runner import PipelineRunner, _default_llm_provider
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow.node import Node
from src.pipeline.nodes import (
    AnimationGeneratorNode,
    IngestionNode,
    PlanNode,
    ScriptGeneratorNode,
    VideoAssemblyNode,
    VoiceGeneratorNode,
)


class FailingMockNode(Node):
    """Mock Node that can be dynamically toggled to fail or succeed."""

    def __init__(self, step_name: str, should_fail: bool = False):
        self._name = step_name
        self.should_fail = should_fail
        self.execution_count = 0

    @property
    def name(self) -> str:
        return self._name

    def execute(self, run_id: str, ledger: Optional[StateLedger] = None) -> Dict[str, Any]:
        self.execution_count += 1
        if self.should_fail:
            raise RuntimeError(f"Simulated crash in node {self._name} on attempt {self.execution_count}")
        return {"step": self._name, "status": "success", "count": self.execution_count}


def test_crash_recovery_step3_failure_and_resume(tmp_path):
    """
    Test scenario 1: Custom node pipeline crash & resume
    1. Execute pipeline with 5 nodes where Step 3 fails.
    2. Inspect StateLedger: verify steps 1 and 2 COMPLETED, step 3 FAILED, run FAILED.
    3. Fix step 3 failure.
    4. Call `runner.resume_run(run_id)`.
    5. Verify steps 1 and 2 SKIPPED, step 3-5 COMPLETED, run status COMPLETED.
    """
    db_path = tmp_path / "crash_test.db"

    node1 = FailingMockNode("step1_ingest", should_fail=False)
    node2 = FailingMockNode("step2_plan", should_fail=False)
    node3 = FailingMockNode("step3_script", should_fail=True)
    node4 = FailingMockNode("step4_tts", should_fail=False)
    node5 = FailingMockNode("step5_assembly", should_fail=False)

    nodes = [node1, node2, node3, node4, node5]

    runner = PipelineRunner(nodes=nodes, db_path=db_path)
    slug = "two-sum-crash-test"

    # Step 1: Execute pipeline expecting crash at step 3
    result1 = runner.run_problem(slug=slug)
    assert not result1.success
    assert result1.failed_step == "step3_script"
    assert result1.status == StepStatus.FAILED
    assert result1.completed_steps == ["step1_ingest", "step2_plan"]
    assert "Simulated crash in node step3_script" in result1.error

    run_id = result1.run_id

    # Step 2: Inspect StateLedger directly
    ledger = StateLedger(db_path)
    run_rec = ledger.get_run(run_id)
    assert run_rec is not None
    assert run_rec.status == StepStatus.FAILED

    completed_steps_map = ledger.get_completed_steps(run_id)
    assert "step1_ingest" in completed_steps_map
    assert "step2_plan" in completed_steps_map
    assert "step3_script" not in completed_steps_map
    assert "step4_tts" not in completed_steps_map
    assert "step5_assembly" not in completed_steps_map

    # Check node execution counts so far
    assert node1.execution_count == 1
    assert node2.execution_count == 1
    assert node3.execution_count == 1
    assert node4.execution_count == 0
    assert node5.execution_count == 0

    # Step 3: Fix Node 3 failure flag
    node3.should_fail = False

    # Step 4: Resume execution via PipelineRunner.resume_run
    runner_resume = PipelineRunner(nodes=nodes, db_path=db_path)
    result2 = runner_resume.resume_run(run_id)

    # Step 5: Verify resumption outcome
    assert result2.success
    assert result2.status == StepStatus.COMPLETED
    assert result2.skipped_steps == ["step1_ingest", "step2_plan"]
    assert result2.completed_steps == ["step1_ingest", "step2_plan", "step3_script", "step4_tts", "step5_assembly"]

    # Verify execution counts: Steps 1 & 2 should NOT have re-executed
    assert node1.execution_count == 1
    assert node2.execution_count == 1
    assert node3.execution_count == 2
    assert node4.execution_count == 1
    assert node5.execution_count == 1

    # Check updated run record in StateLedger
    run_rec_after = ledger.get_run(run_id)
    assert run_rec_after.status == StepStatus.COMPLETED

    runner.close()
    runner_resume.close()
    ledger.close()


def test_production_nodes_crash_and_ops_cli_resume(tmp_path, monkeypatch):
    """
    Test scenario 2: Production Pipeline Nodes & ops.py CLI resume
    1. Run standard production pipeline for a problem slug.
    2. Monkeypatch ScriptGeneratorNode.execute to raise ScriptGenerationError on attempt 1.
    3. Run via `ops.py run --slug ops-resume-test`.
    4. Confirm run fails at step 'script_generator', steps 'ingest' & 'plan' COMPLETED in StateLedger.
    5. Remove monkeypatch (allowing ScriptGeneratorNode to succeed).
    6. Execute `ops.py resume --slug ops-resume-test --json`.
    7. Confirm steps 'ingest' & 'plan' are SKIPPED, steps 'script_generator', 'voice_generator',
       'animation_generator', 'video_assembly' COMPLETE, and overall status is COMPLETED.
    """
    db_path = tmp_path / "ops_production_test.db"
    slug = "ops-resume-test"

    attempt_counter = {"count": 0}

    original_execute = ScriptGeneratorNode.execute

    def flaky_script_execute(self_node, run_id, ledger=None):
        attempt_counter["count"] += 1
        if attempt_counter["count"] == 1:
            raise ScriptGenerationError("Simulated LLM rate-limit / timeout crash in script_generator")
        return original_execute(self_node, run_id, ledger)

    def mock_voice_execute(self_node, run_id, ledger=None):
        run_record = ledger.get_run(run_id)
        return {"slug": run_record.slug, "audio_path": "mock.wav", "status": "completed"}

    def mock_anim_execute(self_node, run_id, ledger=None):
        run_record = ledger.get_run(run_id)
        return {"slug": run_record.slug, "segments": [], "status": "completed"}

    def mock_assembly_execute(self_node, run_id, ledger=None):
        run_record = ledger.get_run(run_id)
        return {"slug": run_record.slug, "status": "completed"}

    monkeypatch.setattr(ScriptGeneratorNode, "execute", flaky_script_execute)
    monkeypatch.setattr(VoiceGeneratorNode, "execute", mock_voice_execute)
    monkeypatch.setattr(AnimationGeneratorNode, "execute", mock_anim_execute)
    monkeypatch.setattr(VideoAssemblyNode, "execute", mock_assembly_execute)

    # 1. Run ops.py run command (expect failure at script_generator)
    exit_code_run = ops_main(["run", "--slug", slug, "--db", str(db_path), "--json"])
    assert exit_code_run == 1

    # 2. Inspect StateLedger
    ledger = StateLedger(db_path)
    run_rec = ledger.get_run_by_slug(slug)
    assert run_rec is not None
    assert run_rec.status == StepStatus.FAILED

    run_id = run_rec.pipeline_run_id

    completed_map = ledger.get_completed_steps(run_id)
    assert "ingest" in completed_map
    assert "plan" in completed_map
    assert "script_generator" not in completed_map
    ledger.close()

    # 3. Execute ops.py resume CLI (second execution will succeed since attempt_counter["count"] becomes 2)
    exit_code_resume = ops_main(["resume", "--run-id", run_id, "--db", str(db_path), "--json"])
    assert exit_code_resume == 0

    # 4. Verify in StateLedger that run is now COMPLETED
    ledger_after = StateLedger(db_path)
    run_rec_final = ledger_after.get_run(run_id)
    assert run_rec_final.status == StepStatus.COMPLETED

    all_completed = ledger_after.get_completed_steps(run_id)
    assert "ingest" in all_completed
    assert "plan" in all_completed
    assert "script_generator" in all_completed
    assert "voice_generator" in all_completed
    assert "animation_generator" in all_completed
    assert "video_assembly" in all_completed
    ledger_after.close()


def test_step_idempotency_on_repeated_runs(tmp_path):
    """
    Verify that calling run_problem on an already COMPLETED run without force=True
    creates a new run, but if an incomplete run exists it resumes it automatically.
    """
    db_path = tmp_path / "idempotency.db"

    node1 = FailingMockNode("ingest", should_fail=False)
    node2 = FailingMockNode("plan", should_fail=False)
    nodes = [node1, node2]

    runner = PipelineRunner(nodes=nodes, db_path=db_path)
    slug = "idempotent-test"

    # First run completes
    res1 = runner.run_problem(slug=slug)
    assert res1.success
    assert node1.execution_count == 1
    assert node2.execution_count == 1

    # Second run without force creates new run because previous was COMPLETED
    res2 = runner.run_problem(slug=slug)
    assert res2.success
    assert res2.run_id != res1.run_id
    assert node1.execution_count == 2
    assert node2.execution_count == 2

    runner.close()


def test_multistage_crash_and_incremental_resumption(tmp_path):
    """
    Verify incremental recovery across multiple consecutive failures:
    - Step 1 passes, Step 2 fails.
    - Resume: Step 2 passes, Step 3 fails.
    - Resume: Step 3 passes -> pipeline COMPLETED.
    """
    db_path = tmp_path / "multi_crash.db"

    node1 = FailingMockNode("step1", should_fail=False)
    node2 = FailingMockNode("step2", should_fail=True)
    node3 = FailingMockNode("step3", should_fail=True)
    nodes = [node1, node2, node3]

    runner = PipelineRunner(nodes=nodes, db_path=db_path)
    slug = "multi-crash-slug"

    # Attempt 1: Fails at step2
    res1 = runner.run_problem(slug=slug)
    assert not res1.success
    assert res1.failed_step == "step2"
    assert res1.completed_steps == ["step1"]

    run_id = res1.run_id

    # Fix step2, step3 still fails
    node2.should_fail = False

    # Attempt 2: Resumes, step1 skipped, step2 completes, fails at step3
    res2 = runner.resume_run(run_id)
    assert not res2.success
    assert res2.failed_step == "step3"
    assert res2.skipped_steps == ["step1"]
    assert res2.completed_steps == ["step1", "step2"]

    # Fix step3
    node3.should_fail = False

    # Attempt 3: Resumes, step1 & step2 skipped, step3 completes -> COMPLETED
    res3 = runner.resume_run(run_id)
    assert res3.success
    assert res3.skipped_steps == ["step1", "step2"]
    assert res3.completed_steps == ["step1", "step2", "step3"]

    assert node1.execution_count == 1
    assert node2.execution_count == 2
    assert node3.execution_count == 2

    runner.close()
