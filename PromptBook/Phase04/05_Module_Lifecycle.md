# Phase 4: Module Lifecycle (Canonical Revision)

## Overview
In the v1.0 architecture, the system included a complex `ModuleLifecycle` state machine to manage the states of various components (e.g., initializing, running, paused, stopped). This concept has been explicitly **removed** in the canonical architecture.

## Why v1.0 Was Wrong
- The `ModuleLifecycle` introduced unnecessary state management overhead.
- It violated the requirement for a simple, sequential batch pipeline.
- The pipeline does not require dynamic loading, pausing, or hot-reloading of modules, making a lifecycle state machine over-engineered.
- The system rules strictly forbid a `ModuleLifecycle` state machine.

## Canonical Equivalent
In the current canonical architecture:
1. **Stateless Modules**: Modules are purely stateless callables or simple classes. They receive `config` and `logger` via constructor injection at startup.
2. **Sequential Execution**: The orchestrator (`PipelineOrchestrator`) manages the execution flow. It calls modules sequentially as part of a single-pipeline batch system.
3. **No State Machine**: There is no state machine to manage module states. Modules are initialized once in the composition root (`src/__main__.py`) and executed sequentially.

## Change Log
- **Removed**: `ModuleLifecycle` state machine.
- **Removed**: Dynamic module state transitions (e.g., starting, stopping, paused).
- **Added**: Stateless module pattern with constructor injection.
- **Added**: Orchestrator-driven sequential execution.
