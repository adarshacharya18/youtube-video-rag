"""
Workflow Executor Engine.

Orchestrates the mathematically sorted Directed Acyclic Graph (DAG).
Handles parallel scaling, Pause/Resume interception, Context injection,
Retries, Timeouts, and Atomic SQLite Checkpointing.
"""

import asyncio
import logging
from typing import Any, Optional, Protocol

from src.core.event_bus import EventBus
from src.core.events import Event
from src.core.exceptions import PipelineError
from src.core.plugin_manager import PluginManager
from src.core.workflow_def import StepDefinition, WorkflowDefinition
from src.core.workflow_planner import ExecutionPlan


class PipelineContext:
    """
    Append-Only state ledger. 
    Thread-safe implementation preventing two parallel plugins from colliding in memory.
    """
    def __init__(self, data: Optional[dict[str, Any]] = None) -> None:
        self._data = data or {}
        self._lock = asyncio.Lock()
        
    async def append(self, key: str, value: Any) -> None:
        async with self._lock:
            if key in self._data:
                raise PipelineError(f"Context Violation: Key '{key}' is immutable and already exists.")
            self._data[key] = value

    def get_snapshot(self) -> dict[str, Any]:
        """Returns a safe, decoupled copy for Plugin execution."""
        return self._data.copy()


class StateManagerProtocol(Protocol):
    """Duck-typed interface for the SQLite Persistence layer."""
    async def save_checkpoint(self, workflow_id: str, context: dict[str, Any], completed_steps: set[str]) -> None: ...
    async def update_state(self, workflow_id: str, state: str) -> None: ...


class WorkflowExecutor:
    """The master Execution Engine."""

    def __init__(
        self, 
        plugin_manager: PluginManager, 
        event_bus: EventBus,
        state_manager: StateManagerProtocol
    ) -> None:
        self._plugins = plugin_manager
        self._bus = event_bus
        self._state = state_manager
        self._logger = logging.getLogger(__name__)
        
        # Concurrency & Interruption Signals
        self._pause_event = asyncio.Event()
        self._pause_event.set() # True means 'allowed to run'
        self._cancel_flag = False

    async def execute_plan(
        self, 
        workflow: WorkflowDefinition, 
        plan: ExecutionPlan, 
        context: PipelineContext, 
        completed_steps: set[str]
    ) -> None:
        """Drives the mathematically sorted Execution Batches."""
        await self._state.update_state(workflow.workflow_id, "RUNNING")
        
        for batch_idx, batch in enumerate(plan.batches):
            # 1. Interruption Check (Pause Boundary)
            if not self._pause_event.is_set():
                await self._state.update_state(workflow.workflow_id, "PAUSING")
                self._logger.info("Pipeline PAUSED... Waiting for safe resume signal.")
                await self._pause_event.wait()
                await self._state.update_state(workflow.workflow_id, "RUNNING")
                
            # 2. Interruption Check (Cancel Boundary)
            if self._cancel_flag:
                await self._state.update_state(workflow.workflow_id, "CANCELLING")
                self._logger.warning("Pipeline Cancelled by Administrator.")
                break
                
            self._logger.info(f"Executing Batch {batch_idx + 1}/{len(plan.batches)} ({len(batch)} tasks concurrently).")
            
            # 3. Parallel Execution Blast
            tasks = [self._execute_step(workflow.workflow_id, step, context) for step in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 4. Result Processing & Safety Checks
            for step, result in zip(batch, results):
                if isinstance(result, Exception):
                    self._logger.error(f"Step '{step.step_id}' triggered FATAL CASCADING FAILURE: {result}")
                    await self._state.update_state(workflow.workflow_id, "FAILED")
                    # Rethrowing halts the Pipeline and prevents the Checkpoint from updating
                    raise result
                else:
                    completed_steps.add(step.step_id)
            
            # 5. Atomic Checkpoint Commit
            await self._state.save_checkpoint(
                workflow_id=workflow.workflow_id, 
                context=context.get_snapshot(),
                completed_steps=completed_steps
            )
            self._logger.info(f"Checkpoint Committed securely. {len(completed_steps)} total steps completed.")

        if not self._cancel_flag:
             await self._state.update_state(workflow.workflow_id, "COMPLETED")
             await self._bus.publish(Event(topic="pipeline.completed", payload={"id": workflow.workflow_id}))

    async def _execute_step(self, workflow_id: str, step: StepDefinition, context: PipelineContext) -> None:
        """Executes a single step. Handles Timeouts, Retries, and Conditional Skipping."""
        
        # Condition Filter
        if not self._evaluate_conditions(step, context.get_snapshot()):
            self._logger.info(f"Step '{step.step_id}' SKIPPED due to configuration conditions.")
            return

        plugin = self._plugins.get_plugin(step.plugin_id)
        if not plugin:
            raise PipelineError(f"Plugin '{step.plugin_id}' vanished from RAM during execution.")
            
        await self._bus.publish(Event(topic=f"step.{step.step_id}.starting", payload={}))
        
        attempt = 0
        max_attempts = step.retry_policy.max_retries + 1
        
        while attempt < max_attempts:
            attempt += 1
            try:
                # Strict Execution Timeout Shield
                # Assuming the plugin exposes an execute() method
                coro = getattr(plugin, "execute", None)
                if not coro or not asyncio.iscoroutinefunction(coro):
                    raise PipelineError(f"Plugin '{step.plugin_id}' lacks a valid async execute() entrypoint.")
                
                # Combine dynamic context with hardcoded YAML parameters
                artifacts = await asyncio.wait_for(
                    coro(context=context.get_snapshot(), **step.parameters), 
                    timeout=step.timeout_sec
                )
                
                # Append artifacts to global Context securely
                if artifacts and isinstance(artifacts, dict):
                    for k, v in artifacts.items():
                         await context.append(k, v)
                         
                await self._bus.publish(Event(topic=f"step.{step.step_id}.completed", payload={}))
                return
                
            except asyncio.TimeoutError:
                self._logger.warning(f"Step '{step.step_id}' timed out after {step.timeout_sec}s.")
                if attempt == max_attempts:
                    raise PipelineError(f"Step '{step.step_id}' FATAL Timeout.")
                    
            except Exception as e:
                self._logger.warning(f"Step '{step.step_id}' failed attempt {attempt}/{max_attempts}: {e}")
                if attempt == max_attempts:
                    raise PipelineError(f"Step '{step.step_id}' EXHAUSTED {step.retry_policy.max_retries} retries.") from e
                    
            # Exponential Backoff
            delay = step.retry_policy.initial_delay_sec * (step.retry_policy.backoff_factor ** (attempt - 1))
            self._logger.info(f"Step '{step.step_id}' backing off for {delay} seconds...")
            await asyncio.sleep(delay)

    def _evaluate_conditions(self, step: StepDefinition, context_data: dict[str, Any]) -> bool:
        """Evaluates simple equality conditions to determine if a step should execute."""
        for key, expected in step.conditions.items():
            if context_data.get(key) != expected:
                return False
        return True

    # -----------------------------------------------------
    # Admin Control Signals
    # -----------------------------------------------------
    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    def cancel(self) -> None:
        self._cancel_flag = True
