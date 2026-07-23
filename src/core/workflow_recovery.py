"""
Workflow Recovery Engine.

Manages autonomous and manual recovery of FAILED or ZOMBIE workflows.
Supports Checkpoint Resumption, Artifact Rollback, and Failure Classification.
"""

import asyncio
import logging
import sqlite3
from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path
from typing import Optional

from src.core.exceptions import PipelineError
from src.core.pipeline_state import PipelineStateManager
from src.core.workflow_def import WorkflowDefinition
from src.core.workflow_executor import PipelineContext, WorkflowExecutor
from src.core.workflow_planner import WorkflowPlanner


class FailureClassification(Enum):
    """Categorizes the severity of a Pipeline crash to dictate the Recovery Strategy."""
    TRANSIENT = "transient"        # e.g., Network timeout (Safe to Auto-Resume)
    FATAL = "fatal"                # e.g., Unknown Plugin (Requires Code Fix)
    CORRUPTED = "corrupted"        # e.g., Missing OS Artifacts (Requires Rollback)


class WorkflowRecoveryManager:
    """Disaster Recovery and State Mutator Engine."""

    def __init__(
        self, 
        state_manager: PipelineStateManager, 
        planner: WorkflowPlanner,
        executor: WorkflowExecutor,
        alert_callback: Optional[Callable[[str, str], Awaitable[None]]] = None
    ) -> None:
        self._state = state_manager
        self._planner = planner
        self._executor = executor
        self._alert = alert_callback
        self._logger = logging.getLogger(__name__)

    async def classify_failure(self, workflow_id: str) -> FailureClassification:
        """
        Diagnoses the health of a failed pipeline's Checkpoint Data.
        Determines the optimal recovery strategy.
        """
        context, completed = await self._state.get_checkpoint(workflow_id)
        if not context and not completed:
            return FailureClassification.FATAL  # Unknown workflow or catastrophic DB loss
            
        # Check if the Operating System deleted required files while the pipeline was paused/failed
        artifacts_intact = await self._state.validate_artifacts(workflow_id)
        if not artifacts_intact:
            self._logger.error(f"Classification [CORRUPTED]: Workflow '{workflow_id}' lost physical OS files.")
            return FailureClassification.CORRUPTED
            
        return FailureClassification.TRANSIENT

    async def resume_workflow(self, workflow: WorkflowDefinition) -> None:
        """
        Rehydrates the Pipeline Context and executes a mathematically filtered 
        Execution Plan that skips previously completed steps.
        """
        workflow_id = workflow.workflow_id
        
        classification = await self.classify_failure(workflow_id)
        if classification == FailureClassification.CORRUPTED:
            raise PipelineError(f"Cannot resume '{workflow_id}'. Checkpoint is physically corrupted. Run Rollback.")
            
        # 1. Rehydrate Context & State
        raw_context, completed_steps = await self._state.get_checkpoint(workflow_id)
        context = PipelineContext(raw_context)
        
        # 2. Build Mathematical Recovery Plan
        recovery_plan = self._planner.build_recovery_plan(workflow, completed_steps)
        
        if not recovery_plan.batches:
            self._logger.info(f"Workflow '{workflow_id}' has zero pending steps. Marking as COMPLETED.")
            await self._state.update_state(workflow_id, "COMPLETED")
            return
            
        self._logger.info(f"Resuming Workflow '{workflow_id}' securely from checkpoint.")
        
        # 3. Inject directly into the Executor
        await self._executor.execute_plan(workflow, recovery_plan, context, completed_steps)

    async def rollback_workflow(self, workflow_id: str) -> None:
        """
        Executes a destructive rollback. Purges physical OS artifacts generated 
        by the failed pipeline and wipes the SQLite Checkpoint.
        """
        raw_context, _ = await self._state.get_checkpoint(workflow_id)
        deleted_files = 0
        
        # 1. Destructively purge OS files referenced in the Context
        for key, value in raw_context.items():
            if isinstance(value, str) and value.startswith("/") and "." in value:
                path = Path(value)
                if path.exists():
                    try:
                        path.unlink()
                        deleted_files += 1
                    except Exception as e:
                        self._logger.warning(f"Rollback warning: Failed to delete physical artifact '{path}': {e}")
                        
        # 2. Hard-mark the Pipeline as CANCELLED to allow DB Retention Pruning
        await self._state.update_state(workflow_id, "CANCELLED")
        self._logger.info(f"Rollback Complete for '{workflow_id}'. Purged {deleted_files} physical artifacts.")

    async def sweep_dead_workflows(self, timeout_hours: int = 24) -> int:
        """
        Zombie Detection. 
        Scans SQLite for workflows marked RUNNING where `updated_at` is suspiciously old.
        """
        def _scan() -> list[str]:
            # Accessing the private db path from StateManager for advanced querying
            with sqlite3.connect(self._state._db_path) as conn:
                cursor = conn.execute(f"""
                    SELECT workflow_id FROM checkpoints 
                    WHERE state = 'RUNNING' 
                      AND updated_at < datetime('now', '-{timeout_hours} hours')
                """)
                return [row[0] for row in cursor.fetchall()]
                
        zombies = await asyncio.to_thread(_scan)
        
        for zombie_id in zombies:
            self._logger.error(f"ZOMBIE DETECTED: '{zombie_id}' has been RUNNING for >{timeout_hours}h without checkpointing.")
            await self._state.update_state(zombie_id, "FAILED")
            
            if self._alert:
                await self._alert("CRITICAL", f"Zombie Workflow Terminated: '{zombie_id}'")
        
        return len(zombies)
