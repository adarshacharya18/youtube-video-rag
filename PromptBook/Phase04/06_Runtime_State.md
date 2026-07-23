# Phase 4: Runtime State (Canonical Revision)

## Overview
The v1.0 architecture introduced a `StateManager` to track and manage the state of the system, execution contexts, and distributed workflows. This concept has been completely **removed** in the canonical architecture.

## Why v1.0 Was Wrong
- A centralized `StateManager` implies a complex, potentially event-driven or distributed system, which violates the core rule of a sequential batch pipeline.
- It adds unnecessary complexity and violates the rule against a `RuntimeContext` object being passed around.
- Tracking state globally across a pipeline is unnecessary when the pipeline is a simple linear progression.
- The system rules strictly forbid a `StateManager`.

## Canonical Equivalent
In the current canonical architecture:
1. **Orchestrator Tracking**: State is implicitly tracked by the `PipelineOrchestrator` through the linear execution of steps. The orchestrator drives the pipeline (`PipelineOrchestrator.run(slug)`).
2. **No Global State Manager**: There is no global `StateManager` or `RuntimeContext`. Dependencies (`config`, `logger`) are injected via constructors.
3. **Local State**: Any necessary state (like the current `slug` being processed) is passed directly as arguments to the relevant module methods (e.g., `orchestrator.run(slug)`). Data flows naturally from one function's return value to the next function's argument.

## Change Log
- **Removed**: `StateManager` class and global state tracking.
- **Removed**: `RuntimeContext` objects passed between modules.
- **Added**: Orchestrator-managed local state and direct argument passing.
