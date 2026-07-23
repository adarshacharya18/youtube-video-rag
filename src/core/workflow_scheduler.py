"""
Workflow Scheduling Engine.

Manages the queuing, concurrency limits, and scheduled launching of whole Workflows.
Protects system RAM/CPU by throttling concurrent pipeline executions.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from src.core.exceptions import PipelineError


class SchedulerError(PipelineError):
    """Raised when scheduling bounds or configurations fail."""
    pass


class ScheduledWorkflow:
    """
    State container for a pending Workflow Execution.
    Implements mathematical __lt__ for PriorityQueue sorting.
    """
    def __init__(self, workflow_id: str, execute_at: float, priority: int, interval_sec: float = 0) -> None:
        self.job_id = str(uuid.uuid4())
        self.workflow_id = workflow_id
        self.execute_at = execute_at
        self.priority = priority
        self.interval_sec = interval_sec
        self.cancelled = False

    def __lt__(self, other: "ScheduledWorkflow") -> bool:
        # 1. Sort by Priority (Lower number = Higher Priority)
        if self.priority == other.priority:
            # 2. Tie-breaker: Execute older jobs first
            return self.execute_at < other.execute_at
        return self.priority < other.priority


class WorkflowScheduler:
    """
    The master throttling and scheduling daemon.
    """

    def __init__(
        self, 
        launcher_callback: Callable[[str], Awaitable[None]], 
        max_concurrent: int = 2
    ) -> None:
        # Decoupled callback to the Orchestrator's Boot Sequence
        self._launcher = launcher_callback
        self._max_concurrent = max_concurrent
        
        self._queue: asyncio.PriorityQueue[ScheduledWorkflow] = asyncio.PriorityQueue()
        self._jobs: dict[str, ScheduledWorkflow] = {}
        
        self._running_count = 0
        # Semaphore mathematically guarantees we never breach concurrency limits
        self._concurrency_lock = asyncio.Semaphore(max_concurrent)
        
        self._logger = logging.getLogger(__name__)
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Ignites the background scheduling daemon."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._daemon_loop())
        self._logger.info(f"Workflow Scheduler Started. Max Concurrency Resource Limit: {self._max_concurrent}")

    async def stop(self) -> None:
        """Safely halts the daemon loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try: 
                await self._task
            except asyncio.CancelledError: 
                pass

    def schedule_immediate(self, workflow_id: str, priority: int = 10) -> str:
        """Pushes a workflow for immediate execution."""
        job = ScheduledWorkflow(workflow_id, execute_at=time.time(), priority=priority)
        self._jobs[job.job_id] = job
        self._queue.put_nowait(job)
        return job.job_id

    def schedule_delayed(self, workflow_id: str, delay_sec: float, priority: int = 10) -> str:
        """Pushes a workflow to execute after N seconds."""
        job = ScheduledWorkflow(workflow_id, execute_at=time.time() + delay_sec, priority=priority)
        self._jobs[job.job_id] = job
        self._queue.put_nowait(job)
        return job.job_id

    def schedule_recurring(self, workflow_id: str, interval_sec: float, priority: int = 10) -> str:
        """Pushes a workflow that will permanently re-trigger every N seconds."""
        job = ScheduledWorkflow(
            workflow_id, 
            execute_at=time.time() + interval_sec, 
            priority=priority, 
            interval_sec=interval_sec
        )
        self._jobs[job.job_id] = job
        self._queue.put_nowait(job)
        return job.job_id

    def cancel_job(self, job_id: str) -> None:
        """O(1) Cancellation flag manipulation."""
        if job_id in self._jobs:
            self._jobs[job_id].cancelled = True
            del self._jobs[job_id]
            self._logger.info(f"Successfully Cancelled Scheduled Job '{job_id}'")

    async def _daemon_loop(self) -> None:
        """The core polling engine."""
        while self._running:
            try:
                # 1. Fetch highest priority job
                job: ScheduledWorkflow = await self._queue.get()
                
                # 2. Check for soft-cancellation
                if job.cancelled:
                    self._queue.task_done()
                    continue

                # 3. Check Execution Time
                now = time.time()
                if job.execute_at > now:
                    # Not ready yet. Push it back into the queue.
                    self._queue.put_nowait(job)
                    # Gentle sleep to prevent 100% CPU spin-locking if a job is hours away
                    sleep_time = min(1.0, job.execute_at - now)
                    await asyncio.sleep(sleep_time)
                    self._queue.task_done()
                    continue

                # 4. Resource Allocation Check (Semaphore block)
                await self._concurrency_lock.acquire()
                
                # 5. Background Task Spawn (Frees daemon to check queue immediately)
                asyncio.create_task(self._safe_launch(job))
                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Scheduler Daemon Crash: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _safe_launch(self, job: ScheduledWorkflow) -> None:
        """Wraps the actual execution payload with lock releases and recurring reinjection."""
        try:
            self._running_count += 1
            self._logger.info(
                f"Launching Workflow '{job.workflow_id}' (Priority {job.priority}). "
                f"Active Pipelines: {self._running_count}/{self._max_concurrent}"
            )
            
            # Execute the fully-decoupled Workflow Executor Boot sequence
            await self._launcher(job.workflow_id)
            
        except Exception as e:
            self._logger.error(f"Pipeline '{job.workflow_id}' fatally crashed: {e}", exc_info=True)
        finally:
            # Guarantee Resource Release regardless of success or failure
            self._running_count -= 1
            self._concurrency_lock.release()
            
            # Calculate Zero-Drift Recurring Re-injection
            if job.interval_sec > 0 and not job.cancelled:
                job.execute_at = time.time() + job.interval_sec
                self._queue.put_nowait(job)
                self._logger.info(f"Re-scheduled recurring pipeline '{job.workflow_id}' for {job.interval_sec}s from now.")
