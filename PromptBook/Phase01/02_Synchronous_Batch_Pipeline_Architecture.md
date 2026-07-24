# Synchronous Batch-Pipeline Architecture Overview

## Executive Summary
This document outlines the architectural blueprint for the **DSA YouTube Video Content & RAG Batch Pipeline**. The architecture deliberately employs a **Synchronous Batch-Pipeline** (Pipes & Filters) pattern, favoring deterministic execution, strict type safety, clear debugging traces, and modular stage isolation.

## Architectural Mandates & Anti-Patterns

### 1. Explicit Architectural Guarantees
- **Synchronous Sequential Execution**: Stages run sequentially in a predictable, linear batch pipeline. Each pipeline step takes a strongly-typed input payload, performs processing, and returns a strongly-typed `BasePipelineResult` output.
- **Explicit Component Instantiation**: Components are instantiated directly or via simple factory functions. Dynamic Dependency Injection (DI) containers and complex reflection magic are **strictly forbidden**.
- **No Complex Async Event Buses**: Async message queues, dynamic event buses, microservice pub/sub topologies, and reactive streams are **strictly forbidden**. Execution flow must remain simple, inspectable, and synchronously debuggable.

### 2. Pipeline Core Abstractions (`src/core/base.py`)
The architecture rests upon simple, explicit protocols:
- `PipelineModule[T_contra, T_co]`: Unified interface for every stage in the batch pipeline. Defines a single primary method `execute(payload: T_contra) -> T_co`.
- `BasePipelineResult[T]`: Standardized execution wrapper encapsulating success status, output data payload, execution metrics (timestamps, durations), and error details.
- `Service` & `Repository`: Stateless domain logic encapsulation and persistent storage contracts.

### 3. Pipeline Execution Flow
```
[ Input Trigger / CLI ]
        │
        ▼
┌────────────────────────┐
│ 1. Configuration Load  │  (Pydantic V2 Settings, .env hydration)
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│ 2. Scraper / Ingestion │  (Problem / Metadata extraction)
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│ 3. RAG Context Engine  │  (Vector Store retrieval & knowledge synthesis)
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│ 4. Script Generation   │  (LLM Prompt Assembly & Output parsing)
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│ 5. Media & Voice Gen   │  (Manim Animations & Kokoro TTS audio)
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│ 6. Video Assembly      │  (FFmpeg render & video stitching)
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│ 7. Upload / Artifacts  │  (YouTube API uploader & checkpoint saving)
└────────────────────────┘
```

## Error Handling & Reliability Strategy
- All errors inherit from `PipelineError` in `src.core.exceptions`.
- Operational exceptions are categorized into:
  - `RetryableError`: Transient failures (network timeout, rate limits) allowing stage retry.
  - `FatalError`: Unrecoverable errors (bad configuration, authentication failure, invalid schema) halting execution immediately.
- Pipeline execution stops deterministically on fatal errors, preserving checkpoint state for easy resumption.

## Structural Logging & Observability
- All pipeline stages log via `structlog.get_logger(__name__)`.
- Log records include key contextual metrics (e.g., `stage_name`, `input_id`, `execution_time_ms`).
- In production, log events are emitted as JSON objects; in local development, key-value console logs are formatted for readability.
