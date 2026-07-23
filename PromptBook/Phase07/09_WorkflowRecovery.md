# Phase 07 / 09: Workflow Recovery Implementation

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/workflow_recovery.py`](#2-source-code-srccoreworkflow_recoverypy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Workflow Recovery Engine**. 

While the Executor handles the happy-path execution, the Recovery Engine is the designated disaster response team. It provides intelligent **Failure Classification**, determining if a crashed pipeline can be safely resumed or if it is irrecoverably corrupted. 

It exposes tools to seamlessly Rehydrate Context and Resume from Checkpoints, securely Rollback and purge OS artifacts of failed runs, and runs a passive daemon sweep to detect and kill **Zombie Workflows** (pipelines that crashed without properly signaling their demise).

---

# 2. Source Code: `src/core/workflow_recovery.py`

```python
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
```

---

# 3. Design Decisions

### 3.1 Failure Classification Mechanics
A FAILED pipeline is not inherently safe to resume. If a pipeline generates a `/tmp/script.md` on Monday, fails on Tuesday, and an Admin tries to resume it on Thursday, there is a massive risk that the Linux `/tmp` folder was auto-purged on Wednesday. The `classify_failure()` method runs `state.validate_artifacts()`. If it detects the OS deleted the files out from under the pipeline, it marks it as `CORRUPTED`, strictly blocking the `resume_workflow()` function from executing and throwing a massive Python exception.

### 3.2 Automated Artifact Rollback
When a workflow is irreparably `CORRUPTED` or explicitly cancelled by an Admin, we cannot simply delete the Database row. Over time, terabytes of half-rendered MP4 files would pile up on the hard drive. The `rollback_workflow()` intelligently iterates over every Key/Value pair in the JSON Context. If a string looks like an absolute file path (`/` + `.`), it securely queries the OS and permanently deletes the orphaned file, preventing SSD exhaustion.

### 3.3 Zombie Sweep (Dead Workflow Detection)
If a Python thread suffers a catastrophic Segmentation Fault (Segfault), it won't throw a standard Exception—the pipeline will simply instantly die. Because it never threw an error, the SQLite Database will permanently say the state is `RUNNING`. The `sweep_dead_workflows()` acts as an automated Garbage Collector. It scans the DB for any `RUNNING` pipeline that hasn't written a checkpoint in over 24 hours, flags it as a `FAILED` Zombie, and fires a Webhook alert to the engineering team.
