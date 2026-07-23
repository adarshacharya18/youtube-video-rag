# Phase04/10_Runtime_Shutdown.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Target Environment:** Intel Core Ultra 7 155H · Ubuntu 25.10 LTS · Python 3.12 · Intel Arc GPU  
**Document Version:** 2.0.0  
**Status:** Canonical — Supersedes v1.0.0 after architectural audit.

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Signal Handling Architecture: `src/__main__.py`](#2-signal-handling-architecture-src__main__py)
3. [Interstage Interruption: `src/orchestrator/pipeline.py`](#3-interstage-interruption-srcorchestratorpipelinepy)
4. [Standard POSIX CLI Exit Codes](#4-standard-posix-cli-exit-codes)
5. [Design Decisions & Architecture Compliance](#5-design-decisions--architecture-compliance)
6. [Change Log](#6-change-log)

---

# 1. Executive Summary

This document specifies the **Signal Handling & Shutdown Architecture**.

In the v2.0.0 canonical architecture, the pipeline is a strict **synchronous, sequential batch script**. Therefore, we completely reject asynchronous cancellation tokens, threading event flags, and complex state management on teardown. 

When the user or operating system sends an interruption signal (`SIGINT` via Ctrl+C, or `SIGTERM`), the runtime relies on the standard Python behavior of raising a `KeyboardInterrupt` (or explicitly raising it in the signal handler). The `PipelineOrchestrator` catches this exception at the top level, logs the interruption cleanly, and exits.

### Teardown Principles
- **No CancellationToken:** `threading.Event()` flags or async tokens are not used. 
- **Signal Trap:** `signal.signal()` is registered at the entry point (`src/__main__.py`) to convert `SIGTERM` into `KeyboardInterrupt` (while `SIGINT` does this by default).
- **Graceful Unwinding:** The active synchronous module is interrupted naturally by the `KeyboardInterrupt`.
- **Top-Level Catch:** The orchestrator's `run()` method uses a simple `try...except KeyboardInterrupt` block.
- **POSIX Exit Code 130:** The process terminates immediately with exit code `130` (standard 128 + SIGINT).

---

# 2. Signal Handling Architecture: `src/__main__.py`

Signal handlers are registered during application startup in the composition root. We map `SIGTERM` to raise a `KeyboardInterrupt`, standardizing both termination signals into Python's native exception flow.

```python
import signal
import sys
import argparse
from src.core.logger import get_logger
from src.core.config import load_config
# ... module imports ...
from src.orchestrator.pipeline import PipelineOrchestrator


def handle_sigterm(signum: int, frame: object) -> None:
    """
    POSIX signal handler for SIGTERM.
    Raises KeyboardInterrupt to reuse the standard SIGINT flow.
    """
    raise KeyboardInterrupt()


def main() -> None:
    # Register signal handler for SIGTERM
    # SIGINT (Ctrl+C) naturally raises KeyboardInterrupt in Python
    signal.signal(signal.SIGTERM, handle_sigterm)

    config = load_config()
    logger = get_logger("pipeline")
    
    # ... composition root instantiation ...
    
    orchestrator = PipelineOrchestrator(
        config=config,
        logger=logger,
        # ... wire dependencies ...
    )
    
    # Simple CLI argument parsing
    parser = argparse.ArgumentParser(description="DSA Video Pipeline")
    parser.add_argument("slug", help="LeetCode problem slug")
    args = parser.parse_args()

    # The orchestrator handles the KeyboardInterrupt internally
    orchestrator.run(slug=args.slug)

if __name__ == "__main__":
    main()
```

---

# 3. Interstage Interruption: `src/orchestrator/pipeline.py`

The `PipelineOrchestrator` is the single driver of the pipeline. Since modules are synchronous and stateless, an interrupt exception will bubble up to `run()`, where it is safely caught.

```python
"""
Pipeline Orchestrator.
"""

import sys
from src.core.config import PipelineConfig
from structlog.stdlib import BoundLogger
# ... module type hints ...


class PipelineOrchestrator:
    def __init__(
        self,
        config: PipelineConfig,
        logger: BoundLogger,
        # ... modules ...
    ) -> None:
        self.config = config
        self.logger = logger
        # ... store modules ...

    def run(self, slug: str) -> None:
        """
        Runs the sequential pipeline.
        Catches standard Python KeyboardInterrupt for clean shutdown.
        """
        self.logger.info("pipeline_started", slug=slug)
        
        try:
            # Stage 1: Scraper
            self.logger.info("stage_started", stage="scraper", slug=slug)
            # scraper_data = self.scraper.scrape(slug)
            
            # Stage 2: Tags
            self.logger.info("stage_started", stage="tags", slug=slug)
            # tags_data = self.tags.generate(scraper_data)
            
            # ... additional stages ...
            
            self.logger.info("pipeline_completed", slug=slug, status="SUCCESS")

        except KeyboardInterrupt:
            self.logger.warning(
                "pipeline_execution_interrupted",
                slug=slug,
                msg="User or OS initiated shutdown. Exiting cleanly."
            )
            sys.exit(130)
        except Exception as e:
            self.logger.error("pipeline_failed", slug=slug, error=str(e))
            sys.exit(1)
```

---

# 4. Standard POSIX CLI Exit Codes

The application entry point returns standardized exit codes matching Linux shell expectations:

| Exit Code | Classification | Cause / Condition |
|---|---|---|
| `0` | Success | Pipeline execution completed all requested stages successfully. |
| `1` | Fatal Failure | Unrecoverable exception, `ConfigurationError`, or pre-flight validation error. |
| `130` | Interrupted | User or system sent `SIGINT` (`Ctrl+C`) or `SIGTERM`, triggering graceful exit. |

---

# 5. Design Decisions & Architecture Compliance

1. **No CancellationToken:** Removes the complexity of passing threading events or cancellation tokens into synchronous modules. Matches Rule 20.
2. **No StateManager Checkpoints:** As a simple batch system, state is implicitly tracked by the orchestrator. If an interrupt occurs, the script simply halts. Caching at the module level (handled natively inside modules like `cache.py`) ensures work isn't fully lost, but no complex `PipelineContext` check-pointing is used. (Rule 17)
3. **No Event Bus Draining:** Since there is no message broker or pub/sub architecture, there are no queues to flush on teardown. (Rule 1 & 7)
4. **Synchronous Unwinding:** Fits the architectural mandate of "No async/await throughout". Everything is a blocking call that unwinds safely when `KeyboardInterrupt` is raised.

---

# 6. Change Log

- **Removed `CancellationToken` / `threading.Event()`:** Completely removed the `shutdown_event` check between pipeline stages. Replaced with standard Python `KeyboardInterrupt` handling.
- **Removed `RuntimeContext` & Checkpointing:** Removed `save_checkpoint(context=self.context)`. Pipeline execution state is not maintained via a central state manager; the orchestrator acts purely sequentially.
- **Refactored `src/__main__.py`:** Aligned signal handling with canonical rules, directly hooking `SIGTERM` to `KeyboardInterrupt`.
- **Removed Asynchronous Teardowns:** Eliminated references to plugin teardowns, event bus draining, or DLQ flushing, as those components do not exist in the canonical architecture.
