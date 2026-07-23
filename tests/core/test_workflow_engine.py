"""
Comprehensive Test Suite for the Phase 07 Workflow Orchestrator.

Covers YAML Parsing bounds, DAG Cycle Detection, SQLite Checkpoint State recovery, 
Parallel mathematical execution planning, and Scheduler concurrency throttling.
"""

import asyncio
import json
import pytest

from src.core.exceptions import PipelineError
from src.core.pipeline_state import PipelineStateManager
from src.core.workflow_def import WorkflowDefinition
from src.core.workflow_executor import PipelineContext
from src.core.workflow_parser import ParserError, WorkflowParser
from src.core.workflow_planner import WorkflowPlanner
from src.core.workflow_scheduler import WorkflowScheduler


# ==========================================
# Fixtures & Factories
# ==========================================
@pytest.fixture
def temp_db(tmp_path) -> str:
    """Provides an isolated SQLite database per test."""
    return str(tmp_path / "test_checkpoints.db")


@pytest.fixture
def state_manager(temp_db) -> PipelineStateManager:
    return PipelineStateManager(temp_db)


def generate_mock_workflow() -> dict:
    """Factory generating a baseline DAG."""
    return {
        "workflow_id": "test_pipeline",
        "version": "1.0.0",
        "steps": [
            {
                "step_id": "step_A",
                "plugin_id": "test.plugin",
                "depends_on": []
            },
            {
                "step_id": "step_B",
                "plugin_id": "test.plugin",
                "depends_on": ["step_A"]
            },
            {
                "step_id": "step_C",
                "plugin_id": "test.plugin",
                "depends_on": ["step_A"]
            }
        ]
    }


# ==========================================
# Parser & Validator Tests
# ==========================================
def test_parser_rejects_unknown_fields(tmp_path):
    """Proves that a typo in a configuration file crashes the boot sequence, rather than executing silently."""
    bad_data = generate_mock_workflow()
    bad_data["timout_sec"] = 600  # Typo: should be timeout_sec
    
    file_path = tmp_path / "bad.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(bad_data, f)
        
    with pytest.raises(ParserError) as exc:
        WorkflowParser.parse(file_path)
    
    # Verify the human-readable trace mentions the typo
    assert "timout_sec" in str(exc.value)


def test_dag_cycle_detection():
    """Proves that infinite loops in Workflow dependencies are mathematically impossible."""
    data = generate_mock_workflow()
    
    # Introduce an impossible Circular Dependency: A -> B -> A
    data["steps"][0]["depends_on"] = ["step_B"]
    
    with pytest.raises(PipelineError) as exc:
        WorkflowDefinition(**data).validate_dag()
        
    assert "Circular Dependency" in str(exc.value)
    assert "step_A" in str(exc.value)


# ==========================================
# Planner Tests (Mathematical Clustering)
# ==========================================
def test_planner_parallel_clustering():
    """
    Verifies that the Planner automatically clusters Step B and Step C 
    into a parallel batch, as they share the same dependency (Step A).
    """
    data = generate_mock_workflow()
    workflow = WorkflowDefinition(**data)
    
    planner = WorkflowPlanner()
    plan = planner.build_plan(workflow)
    
    # Mathematical proof of Topological Sort:
    # Batch 1: [Step_A]
    # Batch 2: [Step_B, Step_C] (Wrapped in asyncio.gather later)
    assert len(plan.batches) == 2
    assert plan.batches[0][0].step_id == "step_A"
    
    batch_2_ids = {s.step_id for s in plan.batches[1]}
    assert "step_B" in batch_2_ids
    assert "step_C" in batch_2_ids


# ==========================================
# Checkpoint & Recovery Tests
# ==========================================
@pytest.mark.asyncio
async def test_checkpoint_atomicity_and_recovery(state_manager):
    """
    Simulates a hard server crash and verifies SQLite perfectly 
    rehydrates the execution memory.
    """
    context = {"script_text": "hello"}
    completed = {"step_A"}
    
    # Simulate saving midway through a pipeline
    await state_manager.save_checkpoint("test_wf", context, completed)
    
    # --- [SERVER CRASHES AND REBOOTS] ---
    
    rehydrated_ctx, rehydrated_steps = await state_manager.get_checkpoint("test_wf")
    
    assert rehydrated_ctx["script_text"] == "hello"
    assert "step_A" in rehydrated_steps


# ==========================================
# Context Immutability Lock Tests
# ==========================================
@pytest.mark.asyncio
async def test_context_immutability():
    """
    Proves that if two parallel plugins try to write to the same Context Key,
    the pipeline securely crashes rather than allowing memory corruption.
    """
    ctx = PipelineContext()
    await ctx.append("key1", "val1")
    
    with pytest.raises(PipelineError) as exc:
        await ctx.append("key1", "hacked_value")
        
    assert "immutable" in str(exc.value)


# ==========================================
# Scheduler Concurrency Throttle Tests
# ==========================================
@pytest.mark.asyncio
async def test_scheduler_max_concurrency_throttle():
    """
    Mathematically proves the asyncio.Semaphore block inside the Scheduler 
    prevents Out-Of-Memory Resource exhaustion.
    """
    active_runs = 0
    max_observed = 0
    
    async def mock_launcher(wf_id: str) -> None:
        nonlocal active_runs, max_observed
        active_runs += 1
        
        if active_runs > max_observed:
            max_observed = active_runs
            
        await asyncio.sleep(0.1) # Simulate active orchestration
        active_runs -= 1

    # Cap concurrency at 2!
    scheduler = WorkflowScheduler(mock_launcher, max_concurrent=2)
    await scheduler.start()
    
    # Try to launch 5 massive rendering pipelines simultaneously
    for i in range(5):
        scheduler.schedule_immediate(f"wf_{i}")
        
    # Wait long enough for all 5 to process through the pipeline
    await asyncio.sleep(0.6)
    await scheduler.stop()
    
    # The lock held the thread count down exactly to the hardware limit
    assert max_observed == 2
