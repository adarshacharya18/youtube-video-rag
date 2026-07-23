# Phase 04 Runtime Architecture & Document Suite Audit Report

**Author:** Explorer Agent (Milestone 1 & 2)  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Working Directory:** `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1`  
**Date:** July 23, 2026  

---

## Executive Summary

This report delivers a thorough analysis of `/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase04/01_Runtime_Architecture.md` and an exhaustive audit of all 11 accompanying Phase 04 documents (`02_Application_Runtime.md` through `12_Runtime_Review.md`).

The v2.0 runtime architecture represents a fundamental paradigm shift from a long-running, event-driven application server to a **single-invocation, synchronous batch-pipeline CLI application** with a single composition root in `src/__main__.py`.

While `01_Runtime_Architecture.md` has already been updated to Version 2.0.0, our deep dive identified key ambiguities and minor residual gaps regarding concurrency semantics, pre-flight check placement, metric logging specifics, and CLI exit code standardization. Concrete refinements are formulated to solidify `01_Runtime_Architecture.md` as the ultimate canonical specification.

Furthermore, auditing the remaining 11 Phase 04 documents revealed a clear dichotomy:
- **5 Documents classified as `DELETE (Obsolete v1)`**: Center entirely on forbidden v1 paradigms (DI container frameworks, dynamic module state machines, global telemetry state managers, object-oriented health monitors, and obsolete v1 architecture reviews).
- **6 Documents classified as `KEEP & REWRITE (Necessary v2.0)`**: Address essential runtime aspects for v2.0 (CLI composition root setup, execution context, configuration loading, log metrics, signal shutdown, and synchronous runtime testing), but require complete rewrites to purge lingering v1 terminology (`async/await`, `EventBus`, `PluginManager`, `Container`, `psutil`, etc.) and align with `01_Runtime_Architecture.md`.

---

# Part 1: Deep Dive Analysis & Refinements for `01_Runtime_Architecture.md`

`01_Runtime_Architecture.md` (v2.0.0) successfully establishes the overarching synchronous batch-pipeline paradigm. However, to serve as the unassailable canonical reference, five specific areas require refinement:

### 1.1 Concurrency & Parallelism Semantics
- **Current Ambiguity:** Section 2 and Section 3 state that the runtime is synchronous, but mention that `asyncio` or `threading` is "reserved for future Voice ∥ Manim parallelism only". Section 7.3 then states "No timeout wrappers. Modules are synchronous; there are no hanging async tasks."
- **Inconsistency/Risk:** Mixing mentions of `asyncio` and `threading` creates confusion for implementers. If individual pipeline modules are synchronous, introducing `asyncio` solely for parallel execution of two CPU/I/O-bound subprocess steps (TTS generation and Manim video rendering) introduces unnecessary event loop overhead and async signal handling complexity.
- **Refinement:** Clarify that **thread-based execution** (`concurrent.futures.ThreadPoolExecutor` or `ThreadPool`) within `PipelineOrchestrator` is the preferred mechanism for Vector 2 (Voice ∥ Manim) execution. `asyncio` is not used in the runtime or orchestrator shell.

### 1.2 Execution Location of Pre-Flight Validation
- **Current Ambiguity:** Section 3 states pre-flight checks are "simple validation in `load_config()` or the orchestrator". Section 6 Step 4 places pre-flight validation between logging initialization and module wiring in `src/__main__.py`.
- **Refinement:** Explicitly define pre-flight checks as a standalone synchronous helper function `run_preflight_checks(config: PipelineConfig)` called directly in `src/__main__.py` right after logger configuration and before module instantiation. It checks:
  1. Binary availability on OS `PATH` (`shutil.which("ffmpeg")`).
  2. Data directory existence/writeability (`ensure_dir()`).
  3. Essential API secret presence in `config`.
  It raises `ConfigurationError` immediately on failure to enforce fail-fast behavior.

### 1.3 Standardizing CLI Exit Codes
- **Current Ambiguity:** Section 7.2 and 7.3 state `sys.exit(1)` for both SIGINT interruption and fatal pipeline errors.
- **Refinement:** Standardize POSIX CLI exit codes in `src/__main__.py`:
  - `0`: Pipeline execution completed successfully (`PipelineResult.success == True`).
  - `1`: Fatal error (uncaught `PipelineError`, `ConfigurationError`, or unrecoverable critical module failure).
  - `130`: Interrupted by user signal (`SIGINT` / `Ctrl+C`, matching standard Unix 128 + 2).

### 1.4 Observability via `structlog` Context Bindings
- **Current Ambiguity:** Section 3 correctly notes that `psutil`, Prometheus, and `MetricsRegistry` are removed, but does not explicitly specify how step execution timing and retries are recorded.
- **Refinement:** Add a dedicated subsection in Section 4 detailing structlog metric convention:
  - Execution timing is measured using standard `time.perf_counter()` inside `PipelineOrchestrator`.
  - Log events must include structured keys: `logger.info("stage_completed", stage="voice", duration_sec=round(elapsed, 3), run_id=context.pipeline_run_id)`.
  - Retries logged by `@retry` decorator emit `warning` events with `attempt`, `delay`, and `exception`.

### 1.5 Module Inventory & Memory Store Clarification
- **Current Ambiguity:** Section 6 lists 9 modules wired in `src/__main__.py`, including `JSONMemoryStore(config.pipeline, logger)`.
- **Refinement:** Clarify config mapping: `JSONMemoryStore` takes `config.memory` (or `config`) and `logger`. Confirm that all 9 components (`LeetCodeScraper`, `GeminiTagExplorer`, `ChromaRAGEngine`, `GeminiScriptGenerator`, `KokoroVoiceSynthesizer`, `ManimAnimationRenderer`, `FFmpegVideoAssembler`, `YouTubeAPIUploader`, `JSONMemoryStore`) implement discrete protocols and are wired in `src/__main__.py` via manual constructor injection.

---

# Part 2: Audit & Classification of Phase 04 Documents (02–12)

The 11 remaining Phase 04 documents were evaluated against canonical decisions (`02_Project_Architecture.md`, `04_Folder_Structure.md`, and `01_Runtime_Architecture.md`).

### Classification Overview

```
Phase 04 Document Suite
├── 01_Runtime_Architecture.md [CANONICAL SPECIFICATION - KEEP & REFINE]
├── 02_Application_Runtime.md   [KEEP & REWRITE] -> Target: src/__main__.py specification
├── 03_Runtime_Context.md       [KEEP & REWRITE] -> Target: PipelineContext domain specification
├── 04_Service_Container.md     [DELETE]          -> Forbidden DI container framework
├── 05_Module_Lifecycle.md      [DELETE]          -> Forbidden dynamic lifecycle state machine
├── 06_Runtime_State.md         [DELETE]          -> Forbidden global state manager / psutil
├── 07_Health_Check_System.md   [DELETE]          -> Forbidden HealthMonitor object model
├── 08_Configuration_Runtime.md [KEEP & REWRITE] -> Target: src/core/config.py runtime spec
├── 09_Runtime_Metrics.md       [KEEP & REWRITE] -> Target: structlog metrics specification
├── 10_Runtime_Shutdown.md      [KEEP & REWRITE] -> Target: Signal handling & checkpointing spec
├── 11_Runtime_Tests.md         [KEEP & REWRITE] -> Target: Synchronous test suite specification
└── 12_Runtime_Review.md        [DELETE]          -> Obsolete review of eliminated v1 paradigms
```

---

### Detailed Analysis of "DELETE (Obsolete v1)" Documents (5 Files)

#### 1. `04_Service_Container.md`
- **Current Contents:** Defines `Container`, `Scope`, `ResolverProtocol`, `register_singleton()`, `register_factory()`, `register_scoped()`, `resolve()`, `CircularDependencyError`, and `ValidationError` in `src/core/container.py`.
- **Why It Must Be Deleted:** Architecture §11.3 Rule 1 explicitly states: *"No DI framework. No Container, Scope, or ResolverProtocol classes."* Architecture Decision 4 (§15) mandates manual constructor injection in `src/__main__.py`. Appendix A of `01_Runtime_Architecture.md` explicitly marks `src/core/container.py` as a forbidden file.

#### 2. `05_Module_Lifecycle.md`
- **Current Contents:** Defines `ModuleLifecycle` state machine, `ModuleState` Enum (`DISCOVERED`, `LOADED`, `INITIALIZED`, `VALIDATED`, `RUNNING`, `PAUSED`, `STOPPED`, `FAILED`, `RECOVERED`, `SHUTDOWN`), `execute_with_timeout`, `recover()`, and `src/core/module_lifecycle.py`.
- **Why It Must Be Deleted:** Architecture §17.8 explicitly avoids plugin discovery and dynamic loading. Modules in v2.0 are simple, stateless callables/classes instantiated once at startup and executed sequentially by `PipelineOrchestrator`. No state machine or dynamic lifecycle hooks exist. `src/core/module_lifecycle.py` is forbidden.

#### 3. `06_Runtime_State.md`
- **Current Contents:** Defines `StateManager`, `RuntimeStateSnapshot`, `ResourceUsage`, active pipeline sets, queue lengths, plugin statuses, and `psutil` OS metrics in `src/core/state.py`.
- **Why It Must Be Deleted:** Architecture §2.2 defines the system as a single-invocation CLI batch pipeline processing one problem per execution. There are no background queue depths, active multi-pipeline registries, or dynamic plugin state tables. Pipeline execution state is managed directly by `PipelineOrchestrator` and persisted via `CheckpointManager`. `src/core/state.py` is forbidden.

#### 4. `07_Health_Check_System.md`
- **Current Contents:** Defines `HealthMonitor`, `HealthStatus` Enum (`HEALTHY`, `DEGRADED`, `UNHEALTHY`), `HealthReport`, and `src/core/health.py` with active background resource/plugin probing.
- **Why It Must Be Deleted:** Architecture §8.4 Rule 5 and `01_Runtime_Architecture.md` §3 & §6 specify that health checks are simple synchronous pre-flight validations (verifying FFmpeg existence on PATH, directory access, secret presence) executed directly in `src/__main__.py` or `load_config()`. Object-oriented health monitoring classes and status state machines are forbidden. `src/core/health.py` is forbidden.

#### 5. `12_Runtime_Review.md`
- **Current Contents:** Architectural review evaluating Phase 04 v1 components (`ApplicationRuntime` state machine, `StateManager`, `MetricsRegistry`, `HealthMonitor`, `RuntimeContext`, `ConfigManager`, upgraded DI Container, Event Bus, PluginLoader, DLQ).
- **Why It Must Be Deleted:** Reviewing and recommending features for an obsolete v1 architecture (Event Bus, Plugin Manager, DLQ, async lifecycle hooks, DI containers) is invalid and misleading. In v2.0, runtime architecture is governed exclusively by `01_Runtime_Architecture.md`.

---

### Detailed Analysis of "KEEP & REWRITE (Necessary v2.0)" Documents (6 Files)

#### 1. `02_Application_Runtime.md`
- **v2.0 Runtime Aspect:** Synchronous Application Setup & Composition Root.
- **Current v1 Violations:** `ApplicationRuntime` state machine class, `src/core/runtime.py`, `RuntimeState` enum, `SubsystemProtocol`, `async start/stop/reload`, DI Container resolution, `event_bus`, `plugin_manager`, `workflow_engine`.
- **Rewrite Purpose:** Provide the concrete, complete specification for `src/__main__.py`.

#### 2. `03_Runtime_Context.md`
- **v2.0 Runtime Aspect:** Execution Context & Stage Data Flow.
- **Current v1 Violations:** `src/core/context.py`, `EventBusProxy`, `PluginRegistryProxy`, `WorkflowManagerProxy`, `MetricsProxy`, `CancellationToken`, `asyncio.Event`, plugin proxy firewalls.
- **Rewrite Purpose:** Specify the immutable execution context (`PipelineContext` in `src/domain/context.py` or `src/orchestrator/pipeline.py`) carrying `pipeline_run_id`, `slug`, `config`, `logger`, `working_dir`, and `temp_dir` across pipeline stages.

#### 3. `08_Configuration_Runtime.md`
- **v2.0 Runtime Aspect:** Synchronous Configuration Loading & Immutable Initialization.
- **Current v1 Violations:** `ConfigManager` class, `src/core/config_manager.py`, `hot_reload()`, `set_override()`, `set_profile()`, Pydantic `.model_dump()`.
- **Rewrite Purpose:** Re-anchor specification to `src/core/config.py` (`load_config()`). Document the synchronous configuration loading hierarchy (.env -> pipeline.yaml -> CLI flags), validation, fail-fast behavior, and immutable `PipelineConfig` instantiation.

#### 4. `09_Runtime_Metrics.md`
- **v2.0 Runtime Aspect:** Runtime Observability & Structured Log Metrics.
- **Current v1 Violations:** `MetricsRegistry` class, `src/core/metrics.py`, `increment()`, `set_gauge()`, `record_time()`, Prometheus/Grafana exporter hooks, sliding window arrays.
- **Rewrite Purpose:** Re-anchor specification to `src/core/logger.py` (`structlog`). Document how structured JSON logs capture timing (`time.perf_counter()`), stage execution metrics, retry events, and failure counts without custom metric registries.

#### 5. `10_Runtime_Shutdown.md`
- **v2.0 Runtime Aspect:** Synchronous Runtime Interruption & Teardown Framework.
- **Current v1 Violations:** `asyncio.wait_for`, Event Bus draining, DLQ flushing, Plugin Manager shutdown, `MetricsRegistry` JSON dump.
- **Rewrite Purpose:** Anchor specification to `src/__main__.py` (signal handling) and `src/orchestrator/pipeline.py` (checkpoint saving). Specify POSIX signal registration (`SIGINT`/`SIGTERM`), thread-safe shutdown flag, checkpoint serialization upon interruption, and standard exit codes (0, 1, 130).

#### 6. `11_Runtime_Tests.md`
- **v2.0 Runtime Aspect:** Synchronous Runtime Test Suite Specification.
- **Current v1 Violations:** `pytest-asyncio`, `AsyncMock`, `ApplicationRuntime` async tests, DI Container validation tests, event bus timeout tests, config hot-reload tests, `tests/core/test_runtime.py`.
- **Rewrite Purpose:** Specify pure synchronous test suite in `tests/core/test_main.py` and `tests/orchestrator/test_pipeline.py`. Test CLI arg parsing, `load_config()` fail-fast validation, pre-flight check failures, manual DI wiring, signal interruption, and exit codes.

---

# Part 3: Exact Guidelines for KEEP & REWRITE Documents

Below are the detailed, actionable guidelines for rewriting each of the 6 KEPT documents to strictly comply with `01_Runtime_Architecture.md`.

---

### Guideline 1: `02_Application_Runtime.md` (Target: `src/__main__.py`)

1. **Title & Header:**
   - Change title to `# Phase04/02_Application_Runtime.md — Application Entry Point & Composition Root`.
   - Update Document Version to `2.0.0`.
2. **File Mapping:**
   - Primary target file: `src/__main__.py`.
   - Explicitly note that `src/core/runtime.py` is **NOT** created.
3. **Core Specification:**
   - Document `main()` function execution flow in `src/__main__.py`:
     ```python
     def main() -> None:
         # 1. Parse CLI arguments (slug, --force-regenerate, --dry-run)
         # 2. config = load_config()
         # 3. configure_logging(config)
         # 4. run_preflight_checks(config)
         # 5. Wire 9 concrete modules via manual constructor injection
         # 6. Register signal handlers (SIGINT, SIGTERM)
         # 7. orchestrator = PipelineOrchestrator(config, scraper, tags, ...)
         # 8. result = orchestrator.run(slug=args.slug)
         # 9. sys.exit(0 if result.success else 1)
     ```
4. **Mandatory Deletions:**
   - Remove `ApplicationRuntime` class, `RuntimeState` enum, `SubsystemProtocol`, `async start()`, `async stop()`, `restart()`, `reload()`, and DI Container references.

---

### Guideline 2: `03_Runtime_Context.md` (Target: `src/domain/context.py` / `src/orchestrator/pipeline.py`)

1. **Title & Header:**
   - Change title to `# Phase04/03_Runtime_Context.md — Pipeline Execution Context`.
   - Update Document Version to `2.0.0`.
2. **File Mapping:**
   - Primary target data structure: `PipelineContext` in `src/domain/context.py` (or `src/orchestrator/pipeline.py`).
   - Explicitly note that `src/core/context.py` is **NOT** created (`src/core/` has 7 files only).
3. **Core Specification:**
   - Define immutable dataclass:
     ```python
     @dataclass(frozen=True)
     class PipelineContext:
         pipeline_run_id: str
         slug: str
         config: PipelineConfig
         logger: structlog.BoundLogger
         working_dir: Path
         temp_dir: Path
     ```
   - Specify helper methods (e.g., `for_stage(stage_name: str) -> PipelineContext` to return context with logger bound to stage name).
4. **Mandatory Deletions:**
   - Remove `EventBusProxy`, `PluginRegistryProxy`, `WorkflowManagerProxy`, `MetricsProxy`, `MemoryProxy`, `CancellationToken`, `asyncio.Event`, and all plugin firewall concepts.

---

### Guideline 3: `08_Configuration_Runtime.md` (Target: `src/core/config.py`)

1. **Title & Header:**
   - Change title to `# Phase04/08_Configuration_Runtime.md — Runtime Configuration Loading`.
   - Update Document Version to `2.0.0`.
2. **File Mapping:**
   - Primary target file: `src/core/config.py` (`load_config()` function).
   - Explicitly note that `src/core/config_manager.py` is **NOT** created.
3. **Core Specification:**
   - Document single-pass configuration loading algorithm:
     1. Read environment variables from `.env` via `python-dotenv`.
     2. Read YAML parameters from `config/pipeline.yaml` via `PyYAML`.
     3. Apply CLI argument overrides (`--force-regenerate`, `--dry-run`).
     4. Validate required fields (API keys, output paths, numeric bounds).
     5. Return immutable `@dataclass(frozen=True)` `PipelineConfig`.
   - Document fail-fast behavior: raise `ConfigurationError` immediately on validation failure.
4. **Mandatory Deletions:**
   - Remove `ConfigManager` class, `hot_reload()`, `set_override()`, `set_profile()`, Pydantic `.model_dump()`, and dynamic profile switching.

---

### Guideline 4: `09_Runtime_Metrics.md` (Target: `src/core/logger.py`)

1. **Title & Header:**
   - Change title to `# Phase04/09_Runtime_Metrics.md — Runtime Observability & Structured Logging`.
   - Update Document Version to `2.0.0`.
2. **File Mapping:**
   - Primary target file: `src/core/logger.py` (`structlog` configuration and logging helpers).
   - Explicitly note that `src/core/metrics.py` is **NOT** created.
3. **Core Specification:**
   - Specify structured JSON log event format for metrics:
     ```json
     {
       "timestamp": "2026-07-23T12:00:00Z",
       "level": "info",
       "event": "stage_completed",
       "pipeline_run_id": "c39a2f10-...",
       "slug": "two-sum",
       "stage": "manim",
       "duration_sec": 45.21,
       "status": "success"
     }
     ```
   - Document timing capture pattern using `time.perf_counter()` inside orchestrator.
   - Document retry event logging format (`@retry` decorator logging `attempt`, `delay`, `exception`).
4. **Mandatory Deletions:**
   - Remove `MetricsRegistry` class, `increment()`, `set_gauge()`, `record_time()`, Prometheus/Grafana hooks, `psutil`, and sliding window metric arrays.

---

### Guideline 5: `10_Runtime_Shutdown.md` (Target: `src/__main__.py` & `src/orchestrator/pipeline.py`)

1. **Title & Header:**
   - Change title to `# Phase04/10_Runtime_Shutdown.md — Interruption & Teardown Framework`.
   - Update Document Version to `2.0.0`.
2. **File Mapping:**
   - Primary target files: `src/__main__.py` (signal registration) and `src/orchestrator/pipeline.py` (checkpoint saving).
3. **Core Specification:**
   - Document POSIX signal handling flow:
     ```python
     shutdown_event = threading.Event()

     def signal_handler(signum, frame):
         logger.warning("Shutdown signal received", signal=signum)
         shutdown_event.set()

     signal.signal(signal.SIGINT, signal_handler)
     signal.signal(signal.SIGTERM, signal_handler)
     ```
   - Document orchestrator interruption check between module stages:
     - If `shutdown_event.is_set()`: save checkpoint via `CheckpointManager`, log interruption, exit with code 130.
   - Document exit code convention: `0` (success), `1` (fatal error), `130` (SIGINT).
4. **Mandatory Deletions:**
   - Remove `asyncio.wait_for`, Event Bus draining, DLQ flushing, Plugin Manager teardown, and `MetricsRegistry` JSON serialization.

---

### Guideline 6: `11_Runtime_Tests.md` (Target: `tests/core/test_main.py` & `tests/orchestrator/test_pipeline.py`)

1. **Title & Header:**
   - Change title to `# Phase04/11_Runtime_Tests.md — Synchronous Runtime Test Suite`.
   - Update Document Version to `2.0.0`.
2. **File Mapping:**
   - Primary target files: `tests/core/test_main.py` and `tests/orchestrator/test_pipeline.py`.
   - Explicitly note that `tests/core/test_runtime.py` is renamed/replaced by `test_main.py`.
3. **Core Specification:**
   - Document pure synchronous `pytest` test cases:
     1. `test_cli_argument_parsing()`: Verify argparse parses slug and flags correctly.
     2. `test_load_config_missing_env()`: Verify `ConfigurationError` raised when `.env` missing.
     3. `test_preflight_checks_ffmpeg_missing()`: Mock `shutil.which` to return `None`, verify pre-flight failure.
     4. `test_manual_di_wiring()`: Verify all 9 module instances are instantiated and injected into `PipelineOrchestrator`.
     5. `test_orchestrator_execution_success()`: Verify `main()` exits with 0 on pipeline success.
     6. `test_signal_interruption()`: Simulate SIGINT during pipeline execution, verify checkpoint saved and exit code 130 returned.
4. **Mandatory Deletions:**
   - Remove `pytest-asyncio`, `AsyncMock`, `ApplicationRuntime` async tests, DI container validation tests, hot-reload tests, and event bus mocks.

---

# Part 4: Phase 04 Restructuring Action Plan

To transition Phase 04 documentation to complete canonical compliance, the following sequential steps must be performed by document editors/writers:

| Step | Target Document | Action | Summary of Changes |
|---|---|---|---|
| 1 | `01_Runtime_Architecture.md` | **REFINE** | Add explicit concurrency semantics (threading for parallel steps), pre-flight helper location, exit code standards (0, 1, 130), and structlog metric key conventions. |
| 2 | `02_Application_Runtime.md` | **REWRITE** | Rewrite as `src/__main__.py` specification. Specify CLI parsing, `load_config()`, `configure_logging()`, pre-flight checks, manual DI wiring, orchestrator run, signal handling. |
| 3 | `03_Runtime_Context.md` | **REWRITE** | Rewrite as `PipelineContext` specification (`src/domain/context.py`). Remove all plugin proxy protocols and `CancellationToken`. |
| 4 | `04_Service_Container.md` | **DELETE** | Delete file. (DI Container framework is forbidden). |
| 5 | `05_Module_Lifecycle.md` | **DELETE** | Delete file. (Dynamic module state machine is forbidden). |
| 6 | `06_Runtime_State.md` | **DELETE** | Delete file. (Global state manager & psutil are forbidden). |
| 7 | `07_Health_Check_System.md` | **DELETE** | Delete file. (Object-oriented HealthMonitor is forbidden). |
| 8 | `08_Configuration_Runtime.md` | **REWRITE** | Rewrite as `src/core/config.py` runtime loading spec. Remove `ConfigManager` and hot-reloading. |
| 9 | `09_Runtime_Metrics.md` | **REWRITE** | Rewrite as `src/core/logger.py` observability spec. Remove `MetricsRegistry` and Prometheus hooks. |
| 10 | `10_Runtime_Shutdown.md` | **REWRITE** | Rewrite as signal handling & checkpointing spec in `src/__main__.py`. Remove event bus drain & DLQ. |
| 11 | `11_Runtime_Tests.md` | **REWRITE** | Rewrite as synchronous `test_main.py` test suite spec. Remove `pytest-asyncio` and async mocks. |
| 12 | `12_Runtime_Review.md` | **DELETE** | Delete file. (Obsolete review of eliminated v1 paradigms). |

---
**End of Analysis Report.**
