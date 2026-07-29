# Architectural Analysis & Design Report: Milestone 1 Workflow Engine Integration

**Module**: `src/core/workflow/`  
**Explorer Agent**: `explorer_m1_3`  
**Date**: 2026-07-29  

---

## Executive Summary

This report establishes the architectural design for the exports, result objects, and exception/base alignment of the Milestone 1 **Workflow Engine** (`src/core/workflow/`). 

The engine coordinates the sequential, fault-tolerant execution of pipeline nodes (Ingest, Plan, Script, Render), using the SQLite `StateLedger` (`src/core/orchestrator/state_ledger.py`) for state persistence and idempotency.

Key design decisions:
1. **`EngineResult` Data Model**: Defined as a `@dataclass` matching the core structural conventions of `src/core/base.py` (`BasePipelineResult`) and `src/core/orchestrator/state_ledger.py` (`PipelineRunRecord`, `StepExecutionRecord`).
2. **Clean Package Exports (`src/core/workflow/__init__.py`)**: Exposes `Node`, `WorkflowEngine`, and `EngineResult` via an explicit `__all__` list.
3. **Strict Exception Alignment (`src/core/exceptions.py`)**: `WorkflowEngine` intercepts all exceptions (`PipelineError`, `PipelineStageError`, or unhandled `Exception`), maps node failures to `StateLedger` step failure records, marks the run `FAILED`, and returns `EngineResult` gracefully without process crashes.
4. **Base Alignment (`src/core/base.py`)**: `Node` aligns with the structural concept of `PipelineModule`, and `EngineResult` provides bidirectional conversion with `BasePipelineResult`.

---

## 1. Result Object Design: `EngineResult`

### 1.1 Specification & Fields

`EngineResult` encapsulates the outcome of a pipeline execution run. 

```python
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone
from src.core.base import BasePipelineResult

@dataclass
class EngineResult:
    """
    Result object returned by WorkflowEngine after running a pipeline sequence.
    """
    success: bool
    run_id: str
    completed_steps: list[str] = field(default_factory=list)
    failed_step: str | None = None
    error: str | None = None
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_base_result(self, data: Any = None) -> BasePipelineResult[Any]:
        """
        Converts EngineResult to a standard BasePipelineResult for downstream consumption.
        """
        return BasePipelineResult(
            success=self.success,
            data=data or {"run_id": self.run_id, "completed_steps": self.completed_steps},
            error=Exception(self.error) if self.error else None,
            error_message=self.error,
            execution_time_ms=self.execution_time_ms,
        )
```

### 1.2 Dataclass vs Pydantic Model Tradeoff Analysis

| Feature / Criteria | `@dataclass` (Recommended) | Pydantic V2 `BaseModel` |
|---|---|---|
| **Alignment with `src/core/base.py`** | **High** (`BasePipelineResult` is `@dataclass`) | Low (`BasePipelineResult` is not Pydantic) |
| **Alignment with `StateLedger`** | **High** (`PipelineRunRecord` & `StepExecutionRecord` are `@dataclass`) | Medium |
| **Runtime Overhead** | Minimal (native Python) | Slightly higher validation overhead |
| **JSON Serialization** | Straightforward (`asdict` or `json.dumps`) | Built-in `.model_dump_json()` |
| **Primary Use Case in Codebase** | Infrastructure / Engine state objects | Domain data contracts (`VideoMetadata`, `EducationalPlan`) |

**Decision**: Use `@dataclass` for `EngineResult` to maintain total parity with `BasePipelineResult` and `StateLedger` record types.

---

## 2. Module Export Design (`src/core/workflow/__init__.py`)

### 2.1 File Organization

```
src/core/workflow/
├── __init__.py      # Package export facade
├── node.py          # Abstract Node class
└── engine.py        # WorkflowEngine and EngineResult implementation
```

### 2.2 Export Facade Code Specification

```python
"""
Workflow Engine Module.

Provides abstract node definitions, fault-tolerant execution engine,
and execution result objects for the automated DSA video pipeline.
"""

from src.core.workflow.engine import EngineResult, WorkflowEngine
from src.core.workflow.node.py import Node

__all__ = [
    "Node",
    "WorkflowEngine",
    "EngineResult",
]
```

---

## 3. Alignment with Base Protocols & Exception Hierarchy

### 3.1 Alignment with `src/core/base.py`

1. **`BasePipelineResult` Integration**:
   - `EngineResult.success` maps directly to `BasePipelineResult.success`.
   - `EngineResult.error` maps to `BasePipelineResult.error_message`.
   - `EngineResult.to_base_result()` enables seamless adaptation when callers expect generic `BasePipelineResult` instances.

2. **`PipelineModule` Protocol Compliance**:
   - `Node` defines `execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]`.
   - Rather than passing state objects directly from step to step, `Node` reads inputs from `ledger` using `run_id` and writes outputs back to `ledger`. This guarantees true pipeline idempotency.

### 3.2 Alignment with `src/core/exceptions.py`

1. **Exception Handling Lifecycle in `WorkflowEngine`**:
   - `WorkflowEngine` wraps every `node.execute(...)` call in a `try...except Exception as exc` block.
   - If a node throws `PipelineStageError`, `FatalError`, `RetryableError`, or any unhandled `Exception`:
     1. Engine logs the exception via `logger.error(...)`.
     2. Engine calls `ledger.record_step_failure(step_execution_id, error_message=str(exc), error_details={"exception_type": type(exc).__name__, "step_name": node.name})`.
     3. `ledger.record_step_failure` automatically updates the parent `pipeline_runs` table status to `FAILED`.
     4. Engine stops further node execution (short-circuits sequence).
     5. Engine returns `EngineResult(success=False, run_id=run_id, completed_steps=completed, failed_step=node.name, error=str(exc))`.
2. **Preventing Application Crashes**:
   - As required by Phase 08 R2 and `PROJECT.md`, exceptions during node execution are captured gracefully without unhandled process termination.

---

## 4. Full Component Code Designs

### 4.1 `src/core/workflow/node.py`

```python
"""
Abstract Node Base Class for Workflow Engine.
"""

from abc import ABC, abstractmethod
from typing import Any
from src.core.orchestrator.state_ledger import StateLedger


class Node(ABC):
    """
    Abstract Base Class for pipeline execution nodes.
    
    Nodes must strictly communicate through the SQLite StateLedger using run_id.
    In-memory state passing between nodes is prohibited to preserve pipeline idempotency.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier name of the pipeline node/step."""
        pass

    @abstractmethod
    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        """
        Execute the node logic.
        
        Args:
            run_id: Pipeline run identifier in StateLedger.
            ledger: Active StateLedger instance for reading inputs and writing outputs.
            
        Returns:
            Dictionary containing output artifacts/payload produced by this step.
        """
        pass
```

### 4.2 `src/core/workflow/engine.py`

```python
"""
Fault-tolerant Workflow Execution Engine.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Any

from src.core.base import BasePipelineResult
from src.core.exceptions import PipelineStageError
from src.core.logger import get_logger
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow.node import Node

logger = get_logger(__name__)


@dataclass
class EngineResult:
    """Result object returned by WorkflowEngine after running a pipeline sequence."""

    success: bool
    run_id: str
    completed_steps: list[str] = field(default_factory=list)
    failed_step: str | None = None
    error: str | None = None
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_base_result(self, data: Any = None) -> BasePipelineResult[Any]:
        """Converts EngineResult to a standard BasePipelineResult."""
        return BasePipelineResult(
            success=self.success,
            data=data or {"run_id": self.run_id, "completed_steps": self.completed_steps},
            error=PipelineStageError(self.error) if self.error else None,
            error_message=self.error,
            execution_time_ms=self.execution_time_ms,
        )


class WorkflowEngine:
    """
    Sequential fault-tolerant workflow engine for executing Node sequences.
    """

    def __init__(self, nodes: list[Node], ledger: StateLedger):
        self.nodes = nodes
        self.ledger = ledger

    def run_pipeline(self, run_id: str) -> EngineResult:
        """
        Executes the sequence of nodes for a given run_id.
        Checks for existing completed steps to enforce idempotency and allow resume.
        Wraps node execution in try/except to record failure to StateLedger and return EngineResult.
        """
        start_time = time.perf_counter()
        completed_steps_map = self.ledger.get_completed_steps(run_id)
        completed_step_names: list[str] = list(completed_steps_map.keys())

        logger.info(
            "Starting workflow execution",
            run_id=run_id,
            total_nodes=len(self.nodes),
            already_completed=completed_step_names,
        )

        for node in self.nodes:
            # Idempotency check: Skip node if already completed in prior run
            if node.name in completed_step_names:
                logger.info("Skipping already completed step", step_name=node.name, run_id=run_id)
                continue

            step_exec_id = self.ledger.record_step_start(run_id, step_name=node.name)
            try:
                logger.info("Executing node", step_name=node.name, run_id=run_id)
                output_payload = node.execute(run_id, self.ledger)
                self.ledger.record_step_completion(step_exec_id, output_payload=output_payload)
                completed_step_names.append(node.name)
            except Exception as exc:
                error_msg = str(exc) or type(exc).__name__
                logger.error(
                    "Node execution failed",
                    step_name=node.name,
                    run_id=run_id,
                    error=error_msg,
                    exc_info=True,
                )
                self.ledger.record_step_failure(
                    step_exec_id,
                    error_message=error_msg,
                    error_details={"exception_type": type(exc).__name__, "step_name": node.name},
                )
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return EngineResult(
                    success=False,
                    run_id=run_id,
                    completed_steps=completed_step_names,
                    failed_step=node.name,
                    error=error_msg,
                    execution_time_ms=elapsed_ms,
                )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info("Workflow execution completed successfully", run_id=run_id)
        return EngineResult(
            success=True,
            run_id=run_id,
            completed_steps=completed_step_names,
            failed_step=None,
            error=None,
            execution_time_ms=elapsed_ms,
        )
```

---

## 5. Verification & Test Plan

1. **Unit Test Coverage (`tests/workflow/test_engine.py`)**:
   - Verify `EngineResult` default fields, serialization, and `to_base_result()` conversion.
   - Verify `WorkflowEngine` successful execution with mock nodes.
   - Verify `WorkflowEngine` resume/idempotency when steps are already marked `COMPLETED` in `StateLedger`.
   - Verify `WorkflowEngine` fault handling when a mock node raises `PipelineStageError` or standard `Exception`, asserting:
     - `EngineResult.success` is `False`.
     - `EngineResult.failed_step` matches failing node name.
     - `EngineResult.error` contains exception text.
     - `StateLedger` database records run status as `FAILED`.
2. **Alignment Verification**:
   - Validate `pytest tests/core/test_exceptions.py` and `pytest tests/core/test_base.py` pass without regression.
