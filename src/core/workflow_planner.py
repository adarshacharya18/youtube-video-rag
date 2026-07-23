"""
Workflow Execution Planner.

Converts a static WorkflowDefinition into a mathematically sorted Directed Acyclic Graph (DAG) 
Execution Plan. Supports parallel group clustering and crash-recovery planning.
"""

import graphlib
import logging

from src.core.exceptions import PipelineError
from src.core.workflow_def import StepDefinition, WorkflowDefinition


class PlannerError(PipelineError):
    """Raised when the engine fails to compile an execution plan (e.g., Deadlocks)."""
    pass


class ExecutionPlan:
    """
    Represents a mathematically sorted list of execution batches.
    All steps within a single batch are guaranteed to have zero cross-dependencies,
    allowing them to be executed completely in parallel.
    """
    def __init__(self, batches: list[list[StepDefinition]]) -> None:
        self.batches = batches


class WorkflowPlanner:
    """
    The intelligence engine that calculates the optimal path through the DAG.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def build_plan(self, workflow: WorkflowDefinition) -> ExecutionPlan:
        """
        Parses the WorkflowDefinition and sorts it into execution batches.
        """
        # 1. Initialize Python's native C-optimized Topological Sorter
        sorter = graphlib.TopologicalSorter()
        step_map = {step.step_id: step for step in workflow.steps}
        
        # 2. Register all dependencies
        for step in workflow.steps:
            sorter.add(step.step_id, *step.depends_on)
            
        try:
            sorter.prepare()
        except graphlib.CycleError as e:
            raise PlannerError(f"Fatal Cycle detected during planning: {e}") from e

        batches: list[list[StepDefinition]] = []
        
        # 3. Calculate Maximum Parallel Groupings
        while sorter.is_active():
            # get_ready() natively returns ALL nodes that have zero unresolved dependencies.
            # This mathematically represents the absolute maximum parallel execution threshold.
            ready_nodes = sorter.get_ready()
            
            if not ready_nodes:
                raise PlannerError("Deadlock detected: Unresolvable dependencies prevent execution.")
                
            batch_steps = [step_map[node_id] for node_id in ready_nodes]
            batches.append(batch_steps)
            
            # Mark these nodes as complete to unlock the next layer of the graph
            for node_id in ready_nodes:
                sorter.done(node_id)
                
        self._logger.info(
            f"Built Execution Plan with {len(batches)} sequential batches for '{workflow.workflow_id}'"
        )
        return ExecutionPlan(batches=batches)

    def build_recovery_plan(
        self, 
        workflow: WorkflowDefinition, 
        completed_step_ids: set[str]
    ) -> ExecutionPlan:
        """
        Compiles an Execution Plan, but scrubs steps that were successfully 
        completed during a previous run. 
        Essential for Crash Recovery and Pause/Resume logic.
        """
        # Generate the master mathematically perfect plan
        master_plan = self.build_plan(workflow)
        
        recovery_batches: list[list[StepDefinition]] = []
        
        # Filter out nodes that have already successfully written to the SQLite State Checkpoints
        for batch in master_plan.batches:
            filtered_batch = [step for step in batch if step.step_id not in completed_step_ids]
            
            # If the batch still has work to do, append it
            if filtered_batch:
                recovery_batches.append(filtered_batch)
                
        remaining_steps = sum(len(b) for b in recovery_batches)
        self._logger.info(
            f"Built Recovery Plan for '{workflow.workflow_id}'. "
            f"Resuming with {remaining_steps} steps remaining."
        )
        
        return ExecutionPlan(batches=recovery_batches)
