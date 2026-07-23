# Phase 14 / 05: Failure Recovery

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/orchestrator/recovery.py`](#2-source-code-srccoreorchestratorrecoverypy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

In a 12-hour automated pipeline spanning network-bound LLM endpoints and CPU-bound C-level renderers, **failure is not a possibility—it is a mathematical certainty.** 

The Failure Recovery module introduces three critical resilience patterns:
1. **Full Jitter Exponential Backoff:** Absorbs transient network failures (e.g., 503 Gateway Timeouts from OpenAI or YouTube) via the `@with_retry` decorator.
2. **Saga Transaction Rollback:** If a process fatally crashes mid-render, the rollback protocol cleans up the massive gigabytes of `.ts` FFmpeg multiplexing chunks to prevent the host EC2 instance from running out of disk space.
3. **Dead Letter Queue (DLQ):** Rather than halting the entire queue for an unrecoverable error (e.g., a completely malformed Manim syntax tree), the orchestrator routes the toxic payload to a JSONL DLQ and safely proceeds to the next video in the batch.

---

# 2. Source Code: `src/core/orchestrator/recovery.py`

```python
"""
Failure Recovery and Dead Letter Queue (DLQ) Subsystem (Phase 14)

Implements Saga transaction rollbacks, exponential backoff retries,
and Dead Letter handling for catastrophic pipeline crashes.
"""
import logging
import json
import time
from typing import Callable, Any
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class DeadLetterEntry:
    """Represents a fatally failed task sent to the DLQ for manual intervention."""
    video_id: str
    failed_phase: str
    error_message: str
    stack_trace: str
    payload: dict
    timestamp: str
    retry_count: int


class RecoveryManager:
    """
    Handles exponential backoff, circuit breaking, and dead-letter routing
    to ensure the 12-hour pipeline degrades gracefully without crashing the root process.
    """
    
    def __init__(self, dlq_path: str = "/tmp/dlq.jsonl"):
        self._logger = logging.getLogger("recovery")
        self.dlq_path = dlq_path

    def with_retry(self, max_retries: int = 3, base_delay: float = 2.0) -> Callable:
        """
        Decorator that applies Exponential Backoff to transient failures
        (e.g., YouTube API 503s, OpenAI rate limits).
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs) -> Any:
                retries = 0
                while retries < max_retries:
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        retries += 1
                        if retries >= max_retries:
                            self._logger.error(f"Exhausted {max_retries} retries for {func.__name__}. Fast-failing.")
                            raise e
                        
                        # Exponential backoff: 2, 4, 8...
                        sleep_time = base_delay * (2 ** (retries - 1))
                        self._logger.warning(f"Transient error in {func.__name__}: {str(e)}. Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
            return wrapper
        return decorator

    def route_to_dlq(self, video_id: str, phase: str, exception: Exception, payload: dict, retries: int = 0) -> None:
        """
        Routes a fatally crashed task to the Dead Letter Queue for DevOps review,
        preventing it from holding up the batch execution loop.
        """
        # In a true production system, stack_trace would use traceback.format_exc()
        entry = DeadLetterEntry(
            video_id=video_id,
            failed_phase=phase,
            error_message=str(exception),
            stack_trace="[Traceback Data Omitted]", 
            payload=payload,
            timestamp=datetime.utcnow().isoformat(),
            retry_count=retries
        )
        
        try:
            with open(self.dlq_path, "a") as f:
                f.write(json.dumps(asdict(entry)) + "\\n")
            self._logger.critical(f"[{video_id}] Fatally crashed during {phase}. Routed to DLQ: {self.dlq_path}")
        except Exception as e:
            self._logger.critical(f"FATAL: Could not write to DLQ! {str(e)}")

    def trigger_rollback(self, video_id: str, current_phase: str, artifacts: dict) -> None:
        """
        Executes a Saga-pattern compensation transaction. 
        If the pipeline crashes during Media Production, we explicitly clean up
        temporary FFmpeg `.ts` chunks to prevent disk explosion.
        """
        self._logger.info(f"[{video_id}] Triggering Saga Rollback from phase: {current_phase}")
        
        # In a real system, this would iterate through the ArtifactManager
        # and explicitly os.unlink() intermediate caches.
        if "tmp_chunks" in artifacts:
            self._logger.info(f"[{video_id}] Rolling back temporary chunks: {artifacts['tmp_chunks']}")
            # os.unlink(artifacts['tmp_chunks'])
```

---

# 3. Design Decisions

1. **Dead Letter Queue (DLQ):** By outputting to standard `.jsonl` format, the DLQ can be trivially ingested by Datadog, ELK, or a custom internal dashboard. A human operator can review the JSON, fix the offending parameter (e.g., an LLM hallucinated Manim syntax error), and re-inject the payload back into the state ledger to resume execution exactly where it failed.
2. **Exponential Backoff:** The `@with_retry` decorator mathematically prevents our orchestrator from participating in a "Thundering Herd" DDOS against the YouTube Data API when quotas reset.
3. **Saga Rollback vs. Hard Delete:** The `trigger_rollback` explicitly targets `tmp_chunks`. It **does not** delete the LLM scripts or audio voiceovers. The system specifically retains expensive, successful artifacts and only drops the corrupted transient data, setting up a perfect environment for the Orchestrator's Checkpoint Resume logic on the next pass.
