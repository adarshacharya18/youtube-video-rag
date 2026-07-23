## 2026-07-23T06:47:30Z
<USER_REQUEST>
You are a Worker subagent for Milestone 3 of the Phase 04 documentation audit and alignment project.

Your working directory is `/home/adarsh/Documents/Youtube-Channel/.agents/worker_m3`. Please create your directory and write `progress.md` and `handoff.md` there.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

TASK:
Rewrite the remaining 6 architecturally necessary Phase 04 documents in `/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase04/` so they strictly align with `01_Runtime_Architecture.md` (v2.0.0 synchronous batch-pipeline, single composition root):

1. `02_Application_Runtime.md`: Rewrite as `src/__main__.py` specification (CLI entry point, `load_config()`, `configure_logging()`, `run_preflight_checks()`, manual DI constructor injection of 9 modules, `PipelineOrchestrator` run, signal registration, POSIX exit codes 0/1/130). Remove `ApplicationRuntime` state machine, `RuntimeState` enum, `SubsystemProtocol`, `async start/stop/reload`, DI Container resolution, `event_bus`, `plugin_manager`, `workflow_engine`.

2. `03_Runtime_Context.md`: Rewrite as `PipelineContext` domain specification (`src/domain/context.py`). Define immutable dataclass (`pipeline_run_id`, `slug`, `config`, `logger`, `working_dir`, `temp_dir`). Remove `EventBusProxy`, `PluginRegistryProxy`, `WorkflowManagerProxy`, `MetricsProxy`, `CancellationToken`, `asyncio.Event`, and plugin proxy firewalls.

3. `08_Configuration_Runtime.md`: Rewrite as `src/core/config.py` runtime config loading spec (`load_config()`). Document single-pass load (.env -> YAML -> CLI flags), validation, fail-fast `ConfigurationError`, immutable `PipelineConfig`. Remove `ConfigManager` class, `hot_reload()`, `set_override()`, `set_profile()`, Pydantic `.model_dump()`.

4. `09_Runtime_Metrics.md`: Rewrite as `src/core/logger.py` observability & metrics specification via `structlog`. Detail structured JSON metrics format (`time.perf_counter()`, `duration_sec`, `stage_completed`, `@retry` warnings). Remove `MetricsRegistry` class, `increment()`, `set_gauge()`, `record_time()`, Prometheus hooks, `psutil`, and sliding window metric arrays.

5. `10_Runtime_Shutdown.md`: Rewrite as signal handling & checkpointing teardown specification (`src/__main__.py` & `src/orchestrator/pipeline.py`). Detail POSIX signal handlers (`SIGINT`, `SIGTERM`), `threading.Event`, stage interruption checks, checkpoint serialization, exit code 130. Remove `asyncio.wait_for`, Event Bus draining, DLQ flushing, Plugin Manager teardown, and `MetricsRegistry` JSON serialization.

6. `11_Runtime_Tests.md`: Rewrite as synchronous runtime test suite specification (`tests/core/test_main.py` & `tests/orchestrator/test_pipeline.py`). Detail pure synchronous pytest tests (CLI parsing, `load_config()` fail-fast, pre-flight failures, manual DI wiring, signal interruption, exit codes). Remove `pytest-asyncio`, `AsyncMock`, `ApplicationRuntime` async tests, DI container tests, hot-reload tests, event bus mocks.

CRITICAL REQUIREMENT:
Ensure ZERO references remain to forbidden terms across all 6 files: `async/await`, `EventBus`, `PluginManager`, `Container`, `HealthCheck`, `StateManager`, `ModuleState`, `ModuleLifecycle`, `DeadLetterQueue`, `psutil`.

Write your handoff report to `/home/adarsh/Documents/Youtube-Channel/.agents/worker_m3/handoff.md`. Send a message to the orchestrator referencing your handoff file.
</USER_REQUEST>
