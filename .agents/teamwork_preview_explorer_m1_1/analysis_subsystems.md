# PromptBook Core Architecture & Subsystems Analysis Report

**Author:** explorer_m1_1  
**Target Path:** `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_explorer_m1_1/analysis_subsystems.md`  
**Date:** July 2026 (UTC: 2026-07-23)  
**Status:** Canonical Analysis Completed  

---

## Executive Summary

This document presents a comprehensive architectural analysis of the core PromptBook platform based on `02_Project_Architecture.md`, `09_Plugin_SDK.md`, `10_Event_Driven_Architecture.md`, `11_Workflow_Engine.md`, and `12_Event_Schemas.md`. 

While documents `09`–`12` represent initial designs for asynchronous, event-driven, plugin-managed systems, **`02_Project_Architecture.md` serves as the Master Architecture Specification (Canonical)**. It establishes the **v2.0 synchronous batch-pipeline** running on single-machine Intel Core Ultra 7 hardware. This report documents the exact subsystem boundaries, the synchronous pipeline operational model, and the explicit architectural rejection of legacy asynchronous/event-driven concepts.

---

## 1. Subsystems Analysis

The PromptBook platform is partitioned into seven distinct subsystems across ten modules (`Module 0` through `Module 9`).

### 1.1 Runtime & Orchestration Subsystem
- **Modules & Packages:** `Module 0: Pipeline Orchestrator` (`src/orchestrator/`) and `Shared Services` (`src/core/`).
- **Primary Responsibilities:**
  - Top-level control of sequential pipeline execution for single problem processing.
  - Runtime configuration loading (`src/core/config.py`) resolving CLI overrides, `.env` variables, and `config/pipeline.yaml`.
  - Checkpoint tracking (`src/orchestrator/checkpoint.py`) enabling crash recovery and resumption.
  - Structured log context binding (`src/core/logger.py`) via `structlog` with correlated `pipeline_run_id`.
  - Centralized path resolution (`src/core/paths.py`) relative to `PROJECT_ROOT`.
  - Global exception hierarchy definition (`src/core/exceptions.py` rooted at `PipelineError`).
- **Interface Patterns:**
  - `PipelineOrchestrator` accepts configuration, module protocol instances, and logger via constructor injection.
  - Exposes single primary entry point: `run(slug: str) -> PipelineResult`.
  - Consumes protocol abstractions (`ScraperProtocol`, `TagExplorerProtocol`, etc.) defined in `src/models/protocols.py`.

### 1.2 Plugin Platform
- **Modules & Packages:** Protocol definitions (`src/models/protocols.py`) and concrete implementations (`src/{module}/`).
- **Primary Responsibilities:**
  - Provides a modular, decoupled component architecture where each pipeline module acts as an independent processing filter.
  - Enables seamless substitution of implementations (e.g., swapping `LeetCodeScraper` for `HackerRankScraper`, or `KokoroVoiceSynthesizer` for `ElevenLabsSynthesizer`) without altering pipeline orchestration logic.
- **Interface Patterns:**
  - Protocol contracts built using Python `typing.Protocol` with `@runtime_checkable` decorator.
  - Structural subtyping (PEP 544) requiring zero inheritance from base classes.
  - Single primary action method per module interface (`scrape`, `explore`, `retrieve`, `generate`, `synthesize`, `render`, `assemble`, `upload`, `save`).
  - Inputs and outputs strictly bound to immutable frozen dataclasses (`@dataclass(frozen=True)`).

### 1.3 Workflow Engine
- **Modules & Packages:** `src/orchestrator/pipeline.py` & `src/orchestrator/checkpoint.py`.
- **Primary Responsibilities:**
  - Enforces the deterministic stage dispatch order: `Scraper` ➔ `Tag Explorer` ➔ `RAG Engine` ➔ `Script Generator` ➔ `Voice Synthesizer` ➔ `Manim Renderer` ➔ `Video Assembler` ➔ `YouTube Uploader` ➔ `Memory Store`.
  - Handles inter-stage DTO propagation, cache checks, stage timing accumulation, and failure isolation.
  - Persists stage markers to `data/checkpoints/{slug}/{module}.json`.
- **Interface Patterns:**
  - Direct, synchronous stage invocation loop inside `PipelineOrchestrator.run()`.
  - Returns `PipelineResult` dataclass containing full status, DTO references, module timings, and error tuples.

### 1.4 Persistence Layer
- **Modules & Packages:** `src/core/serialization.py`, `src/core/cache.py`, `src/memory/`, and `data/` storage layout.
- **Primary Responsibilities:**
  - Manages storage for intermediate artifacts in `data/` (`scraped/`, `tags/`, `rag/`, `scripts/`, `voice/`, `animation/`, `output/`, `uploads/`, `checkpoints/`, `memory/`).
  - Implements zero-dependency JSON serialization/deserialization for frozen dataclasses (`serialize`, `deserialize`), supporting ISO 8601 timestamps, relative POSIX paths, enum values, and visual parameter type discriminators (`_type`).
  - Provides content-addressed file caching (`FileCache`) and historical execution tracking (`JSONMemoryStore`).
- **Interface Patterns:**
  - Serialization functions: `serialize(obj: Any, path: Path) -> None` and `deserialize(path: Path, cls: type[T]) -> T`.
  - Cache management API: `FileCache.get()`, `FileCache.put()`, `FileCache.invalidate()`.
  - Memory contract: `MemoryStoreProtocol` (`save`, `has_been_generated`, `get_record`, `get_all_tags`, `get_problems_by_tag`, `get_failed_runs`).

### 1.5 RAG Platform
- **Modules & Packages:** `Module 3: RAG Knowledge Engine` (`src/rag/`).
- **Primary Responsibilities:**
  - Indexes DSA Markdown documents from `data/knowledge_base/` using topic-aware text splitting (`chunker.py`).
  - Generates text embeddings using Gemini API (`text-embedding-004`).
  - Maintains persistent local vector index in ChromaDB at `data/vector_store/chroma/`.
  - Executes semantic retrieval and pedagogical re-ranking to ground script generation.
- **Interface Patterns:**
  - Implements `RAGEngineProtocol`.
  - Primary retrieval method: `retrieve(problem: ScrapedProblem, tags: TagKnowledge) -> RAGContext`.
  - Knowledge base indexing method: `index_knowledge_base() -> int`.

### 1.6 Educational Content Platform
- **Modules & Packages:** `Module 1: Scraper` (`src/scraper/`), `Module 2: Tag Explorer` (`src/tags/`), and `Module 4: Script Generator` (`src/script/`).
- **Primary Responsibilities:**
  - **Scraper:** Fetches LeetCode problem description, tags, constraints, examples, and accepted C++ solution via GraphQL API (`ScrapedProblem`).
  - **Tag Explorer:** Enriches raw tags with pattern family mappings, prerequisite concepts, related problems, and visual animation styles (`TagKnowledge`).
  - **Script Generator:** Prompts Gemini LLM to construct a 10-section narration script (`VideoScript`) with embedded typed `VisualParams` for animations and `SEOMetadata` for YouTube.
- **Interface Patterns:**
  - `ScraperProtocol`: `scrape(slug: str) -> ScrapedProblem`.
  - `TagExplorerProtocol`: `explore(problem: ScrapedProblem) -> TagKnowledge`.
  - `ScriptGeneratorProtocol`: `generate(problem, tags, rag_context, memory) -> VideoScript`.
  - Type-safe `VisualParams` tagged union (`ArrayVisualParams | LinkedListVisualParams | TreeVisualParams | GraphVisualParams | HashMapVisualParams | StackQueueVisualParams | CodeVisualParams | ComplexityVisualParams | GenericVisualParams`).

### 1.7 Media Production Subsystem
- **Modules & Packages:** `Module 5: Voice` (`src/voice/`), `Module 6: Manim` (`src/animation/`), `Module 7: Assembly` (`src/assembly/`), `Module 8: YouTube` (`src/youtube/`).
- **Primary Responsibilities:**
  - **Voice:** Local TTS speech synthesis via Kokoro-82M model using OpenVINO (NPU/CPU), generating 24kHz WAV section clips and timing manifest (`VoiceResult`).
  - **Manim:** Programmatic rendering of 1080p@30fps MP4 clips using Manim Community dark-themed scene templates, synchronized to voice section durations (`AnimationResult`).
  - **Assembly:** FFmpeg muxing, clip concatenation, audio normalization to -14 LUFS, thumbnail frame generation (`AssembledVideo`).
  - **YouTube:** Resumable video upload via YouTube Data API v3 using Google OAuth 2.0 with complete SEO metadata (`UploadResult`).
- **Interface Patterns:**
  - `VoiceSynthesizerProtocol`: `synthesize(script: VideoScript) -> VoiceResult`.
  - `AnimationRendererProtocol`: `render(script: VideoScript, voice: VoiceResult) -> AnimationResult`.
  - `VideoAssemblerProtocol`: `assemble(voice: VoiceResult, animation: AnimationResult, script: VideoScript) -> AssembledVideo`.
  - `YouTubeUploaderProtocol`: `upload(video: AssembledVideo, metadata: SEOMetadata) -> UploadResult`.

---

## 2. v2.0 Synchronous Batch-Pipeline Operation

The v2.0 PromptBook pipeline operates as a **single-machine, synchronous batch pipeline** optimized for determinism, crash recovery, and simple debugging.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          PIPELINE ORCHESTRATOR                          │
│                    (Sequential Dispatch · Checkpoint)                    │
└──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬─────────┘
       │      │      │      │      │      │      │      │      │
       ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼
   ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐
   │Scraper│Tags │ RAG  │Script│Voice │Manim │Assem.│YouTube│Memory│
   └──────┘└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘
```

### 2.1 Single Composition Root
- **Location:** `src/__main__.py` (or `src/bootstrap.py`).
- **Role:** It is the **only** file in the project permitted to import concrete class implementations (`LeetCodeScraper`, `GeminiTagExplorer`, `ChromaRAGEngine`, `GeminiScriptGenerator`, `KokoroVoiceSynthesizer`, `ManimAnimationRenderer`, `FFmpegVideoAssembler`, `YouTubeAPIUploader`, `JSONMemoryStore`).
- **Bootstrap Flow:**
  1. Load application config via `load_config()`.
  2. Instantiate root `structlog` logger.
  3. Instantiate concrete module classes, passing config objects and loggers.
  4. Instantiate `PipelineOrchestrator`, injecting module instances as protocol abstractions.
  5. Invoke `orchestrator.run(slug=args.slug)`.

### 2.2 Deterministic Stage Execution
- The pipeline executes stages in strict linear sequence:
  `Scraper` ➔ `Tags` ➔ `RAG` ➔ `Script` ➔ `Voice` ➔ `Manim` ➔ `Assembly` ➔ `YouTube` ➔ `Memory`.
- **Inter-Module Contracts:** Each stage consumes immutable DTOs from prior stages and outputs its own immutable DTO.
- **Checkpoint Resilience:** After completing each stage, the orchestrator writes a marker to `data/checkpoints/{slug}/{module}.json`. On pipeline rerun, existing checkpoints are detected, allowing execution to resume from the last successful stage.
- **Caching Boundary:** Modules persist outputs to `data/{module_dir}/{slug}...`. Cache hits allow the orchestrator to bypass module execution while retaining checkpoint state. Re-running with `--force-regenerate` purges both caches and checkpoints.

### 2.3 Step-by-Step Function Calls
- All execution is driven by direct, synchronous Python function calls on protocol interfaces. There are no asynchronous event loops or background pub/sub dispatchers.
- Sequential orchestrator call pattern:
  ```python
  scraped_problem = self._scraper.scrape(slug)
  self._checkpoint.save(slug, "scraper")

  tag_knowledge = self._tag_explorer.explore(scraped_problem)
  self._checkpoint.save(slug, "tags")

  rag_context = self._rag_engine.retrieve(scraped_problem, tag_knowledge)
  self._checkpoint.save(slug, "rag")

  video_script = self._script_generator.generate(scraped_problem, tag_knowledge, rag_context, memory_record)
  self._checkpoint.save(slug, "script")

  voice_result = self._voice_synthesizer.synthesize(video_script)
  self._checkpoint.save(slug, "voice")

  animation_result = self._animation_renderer.render(video_script, voice_result)
  self._checkpoint.save(slug, "animation")

  assembled_video = self._video_assembler.assemble(voice_result, animation_result, video_script)
  self._checkpoint.save(slug, "assembly")

  upload_result = self._youtube_uploader.upload(assembled_video, video_script.seo_metadata)
  self._checkpoint.save(slug, "youtube")

  self._memory_store.save(memory_record)
  ```

---

## 3. Forbidden Concepts & Architectural Rejections

The master specification (`02_Project_Architecture.md`, Section 17) explicitly rejects several asynchronous and event-driven patterns proposed in preliminary design documents (`09`, `10`, `11`, `12`).

### 3.1 Mapping of Forbidden Concepts to v2.0 Replacements

| Forbidden Concept / Term | Originating Early Doc | Architectural Rationale for Rejection | Clean v2.0 Replacement |
|---|---|---|---|
| **`async/await` / Async loops** | `09_Plugin_SDK.md`, `10_Event_Driven_Architecture.md` | Mixing async I/O with heavy CPU/NPU/GPU computations (OpenVINO TTS, Manim rendering, FFmpeg encoding) causes event loop blocking and complex thread pool bridging without throughput gain on single-machine batch runs. | **Synchronous step-by-step function calls**. Heavy rendering tasks are isolated in dedicated subprocesses. |
| **`EventBus`** | `10_Event_Driven_Architecture.md`, `12_Event_Schemas.md` | Pub/Sub messaging requires event registries, envelope schemas, priority queues, topic routing, and correlation tracing. This adds unnecessary operational overhead for a linear single-machine pipeline. | **Centralized `PipelineOrchestrator`** invoking protocol methods directly with typed dataclass DTO arguments. |
| **`PluginManager`** | `09_Plugin_SDK.md` | Dynamic plugin discovery, topological dependency sorting, and runtime plugin loading (`importlib`) introduce indirection, debugging obscurity, and brittle import order issues. | **Explicit wiring in Composition Root** (`src/__main__.py`) using manual constructor injection. |
| **`Container` / `DI container`** | `09_Plugin_SDK.md` | Third-party DI frameworks or service locators obscure dependency graphs and create framework lock-in for a system with only 9 modules. | **Manual constructor injection** using standard Python `__init__` signatures and `typing.Protocol`. |
| **`HealthCheck`** | `09_Plugin_SDK.md` | Runtime state polling (`check_health() -> PluginHealth`) is unnecessary overhead for stateless, single-invocation batch modules. | **Fail-fast protocol assertion** (`isinstance(module, Protocol)`) at startup, and explicit exceptions (`PipelineError`) during execution. |
| **`Module Lifecycle`** | `09_Plugin_SDK.md` | State machines (`UNINITIALIZED` -> `INITIALIZING` -> `ACTIVE` -> `STOPPING` -> `STOPPED`) add state management complexity inside every module. | **Stateless protocol implementations**. Modules are instantiated once with configuration and remain ready to process inputs. |
| **`DeadLetter queue` (DLQ)** | `10_Event_Driven_Architecture.md` | Message brokers use DLQs for unparseable or repeatedly failed events. A single-machine pipeline does not use message queues. | **File-based checkpoints** (`data/checkpoints/`), domain exception hierarchy (`PipelineError`), `@retry` backoff decorator, and structured JSON logs (`structlog`). |

---

## 4. Summary & Verification Matrix

| Architecture Requirement | Implementation / Specification Reference | Status |
|---|---|---|
| **Subsystem Boundaries** | 7 defined subsystems mapped across 10 modules (`src/`) | Verified |
| **Interface Style** | Structural subtyping via `@runtime_checkable` `typing.Protocol` | Verified |
| **Data Transfer** | Immutable frozen dataclasses (`@dataclass(frozen=True)`) | Verified |
| **Composition Root** | `src/__main__.py` wires concrete implementations to protocols | Verified |
| **Execution Flow** | Synchronous sequential batch pipeline | Verified |
| **Persistence** | File-based JSON caching and checkpoints under `data/` | Verified |
| **Prohibited Terms Excluded** | Zero dependency on async loops, EventBus, PluginManager, DLQs, etc. | Verified |

