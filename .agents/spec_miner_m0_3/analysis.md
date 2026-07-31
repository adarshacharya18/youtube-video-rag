# Phase 14 Production Orchestration & End-to-End Pipeline Specification Analysis

**System Target:** Automated Data Structures & Algorithms (DSA) Educational YouTube Video Pipeline  
**Target Environment:** Intel Core Ultra 7 155H · Intel Arc GPU · Intel AI Boost NPU · Ubuntu 25.10 LTS · Python 3.12  
**Document Version:** 1.0.0  
**Status:** Spec Mining Analysis Complete  
**Target Output File:** `PromptBook/Phase14/01_Production_Orchestration.md`  

---

## 1. Architectural Principles & Requirements Analysis

### 1.1 Phase 14 Mission & Scope
Phase 14 ("Integration & Production Orchestration") is the final operational phase of the pipeline. It unifies all 13 prior architectural phases into a single, cohesive, fault-tolerant 12-hour batch processing engine controlled by a master operations CLI (`src/cli/ops.py`) and a pipeline orchestrator (`src/core/orchestrator/pipeline_runner.py` / `WorkflowEngine`).

### 1.2 Mandated Phase 14 Requirements
* **R1. Implement Master CLI (`src/cli/ops.py`):** Unified command-line interface for human DevOps/SRE engineers providing commands: `run`, `status`, `resume`, `health`, `benchmark`, `deploy`, `rollback`, `diagnose`, and `report`.
* **R2. Implement Pipeline Orchestrator (`src/core/orchestrator/pipeline_runner.py`):** Links all individual pipeline nodes (Ingestion $\rightarrow$ Taxonomy $\rightarrow$ RAG Retrieval $\rightarrow$ Curation $\rightarrow$ Script Generator $\rightarrow$ Code Execution Trace $\rightarrow$ Vis Spec $\rightarrow$ LLM Audit $\rightarrow$ Audio/TTS $\rightarrow$ Animation/Manim $\rightarrow$ Subtitle/Graphics $\rightarrow$ Video Assembly $\rightarrow$ YouTube Publishing) into a single, crash-safe, idempotent workflow execution loop using `StateLedger` and `EventBus`.
* **R3. Draft Operational Runbooks (`PromptBook/Phase14/01_Production_Orchestration.md`):** Documents operational runbooks, system startup procedures, troubleshooting guides, resume protocols, circuit breakers, hardware lock semantics, and health check mechanisms.
* **R4. End-to-End Integration Testing (`tests/production/test_pipeline_e2e.py`):** Verifies full end-to-end execution, node linking, crash recovery, and CLI invocation.

---

## 2. End-to-End Pipeline Execution Specification

The synchronous 12-hour batch pipeline transforms a raw LeetCode problem slug (e.g., `two-sum`, `lru-cache`) into a broadcast-grade 4K/1080p YouTube video with multi-track audio and burned-in subtitles.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        SYNCHRONOUS 12-HOUR BATCH QUEUE DISPATCHER                      │
└───────────────────────────┬────────────────────────────────────────────┘
                                            │
  ┌─────────────────────────────────────────┼─────────────────────────────────────────┐
  ▼                                         ▼                                         ▼
┌──────────────────────┐          ┌──────────────────────┐          ┌──────────────────────┐
│  Problem Slug #1     │          │  Problem Slug #2     │          │  Problem Slug #N     │
│  (5-12 min pipeline) │ ───────► │  (5-12 min pipeline) │ ───────► │  (5-12 min pipeline) │
└──────────────────────┘          └──────────────────────┘          └──────────────────────┘
```

### 2.1 Chronological Node Pipeline Execution Sequence

| Step | Phase / Node Name | Input Artifact | Output Payload / Artifact | Core Function & Resilience Logic |
|---|---|---|---|---|
| 1 | **Phase 01: Ingestion Engine** (`IngestionNode`) | Problem URL / Slug (e.g. `two-sum`) | `ScrapeCompletePayload`, `NormalizedDocument` | Scrapes LeetCode problem description, constraints, and test cases. Validates HTML/JSON format. Emits `scraper.v1.problem_scraped`. |
| 2 | **Phase 02: Taxonomy Manager** (`TaxonomyNode`) | `NormalizedDocument` | `TaxonifiedDocument`, `IndexReadyPayload` | Classifies problem into 3-tier ontology (`DataStructure`, `Algorithm`, `Pattern`) and updates Knowledge Graph in SQLite `MetadataStore`. |
| 3 | **Phase 03: RAG Retrieval** (`RAGNode`) | `TaxonifiedDocument` | `RAGContextResponse` | Performs ChromaDB vector embedding & similarity lookup (similarity score $\ge 0.75$). Retries on API rate limits; falls back to SQLite FTS5 if ChromaDB locks. |
| 4 | **Phase 04: Problem Curation** (`CurationNode`) | `RAGContextResponse` | `CurationPlan` | Builds learning objectives, difficulty target, and pedagogical structure. |
| 5 | **Phase 05/11: Script Generator** (`ScriptGeneratorNode`) | `CurationPlan`, RAG Context | `VideoScriptPayload` (`script.json`) | Generates structured JSON script (Hook, Context, Solution, Complexity). Enforces strict Pydantic validation. **Aggressive Error-Feedback Loop**: catches `ValidationError`/`JSONDecodeError` and feeds exact error back to LLM for retry. |
| 6 | **Phase 06: Sandboxed Code Trace** (`CodeExecutorNode`) | `VideoScriptPayload` | `CodeExecutionTrace` | Executes algorithm in sandboxed environment. Traps zero-division/timeouts ($>5\text{s}$) and outputs variable state snapshots. |
| 7 | **Phase 07: Visualization Spec** (`VisSpecNode`) | `CodeExecutionTrace`, Script | `VisualizationSpec` | Computes 1920x1080 canvas layout, bounding boxes, and scene timeline directives. |
| 8 | **Phase 12: Quality Audit** (`LLMAuditNode`) | `VisualizationSpec`, Script | `ApprovedScriptPayload` / `ReviewReport` | Adversarial LLM-as-a-Judge fact-checks math and logic. If score $< 70/100$ or `CRITICAL` error, triggers self-correction loop back to Phase 05. |
| 9 | **Phase 08: Voice Synthesis** (`VoiceNode`) | `ApprovedScriptPayload` | `AudioArtifact` (`master_audio.wav`) | Synthesizes neural audio via Kokoro-82M model using OpenVINO NPU cross-process file lock (`/var/lock/openvino_npu.lock`). Normalizes audio to $-14.0$ LUFS. |
| 10 | **Phase 09/12: Manim Render** (`AnimationGeneratorNode`) | `VisualizationSpec`, Script | `RenderedScene` (`scene_*.mp4`) | Renders 1080p60 Manim animations via isolated `subprocess.run()`. Governed by `GPU_SEMAPHORE = 1` ($\le 3,500\text{ MB}$ VRAM). **Partial Render Retention**: if scene rendering fails, retains preceding completed MP4s and marks `artifact_registry.json` as `PARTIAL_RENDER`. |
| 11 | **Phase 11: Subtitle & Graphic** (`AssetNode`) | `master_audio.wav`, Script | `AssetPayload` (`subtitles.srt`, `thumb.png`) | Generates WhisperX forced timestamp alignment (`.srt`) and Pillow thumbnail render (strictly $< 2.0\text{ MB}$). |
| 12 | **Phase 10/13: Video Assembly** (`VideoAssemblyNode`) | `.wav`, `scene_*.mp4`, `.srt` | `FinalVideoArtifact` (`final_video.mp4`) | Assembles final 4K video using FFmpeg QSV hardware acceleration (`taskset -c 0-11` P-Cores). Performs BGM audio ducking and subtitle burn-in. Cleans up intermediate scratch files. |
| 13 | **Phase 13: YouTube Publisher** (`PublishingNode`) | `final_video.mp4`, `thumb.png`, `.srt` | `YoutubePublishedPayload` | Uploads video via YouTube Data API v3 using OAuth credential pool rotation. On 403 `QuotaExceededError` (10,000 unit/day limit), saves payload to `data/upload_queue/` for auto-dispatch at 00:00 PST. |

---

## 3. Master Operations CLI Specification (`src/cli/ops.py`)

The Master Operations CLI serves as the primary command-line tool for SRE and DevOps operators.

### 3.1 Command Interface Matrix

| Command | Arguments / Flags | Primary Purpose | Implementation Logic & Dependencies |
|---|---|---|---|
| `run` | `--slug <slug>` / `--slug-file <file>`, `--config <path>`, `--force` | Trigger end-to-end execution for single or batch problems. | Instantiates `WorkflowEngine` & `PipelineRunner`, loads blueprint, iterates over node sequence. |
| `status` | `--watch`, `--run-id <id>` | Query live execution status from SQLite State Ledger. | Reads `pipeline_runs` and `step_executions` tables in `StateLedger`. Displays phase status, active slug, hardware utilization. |
| `resume` | `--run-id <id>`, `--checkpoint <path>` | Resume execution from last successful step checkpoint. | Rehydrates state from `StateLedger.get_completed_steps()`, skipping completed steps idempotently. |
| `health` | `--check-type {liveness,readiness}` | Inspect system dependency status & hardware lock files. | Probes FFmpeg binary, Manim binary, SQLite DB connection, Arc GPU driver (`/dev/dri/renderD128`), OpenVINO NPU lock (`/var/lock/openvino_npu.lock`), ChromaDB. |
| `benchmark` | `--config <path>` | Trigger hardware profiling against rendering engines. | Measures CPU, GPU VRAM peak allocation, and rendering throughput. |
| `deploy` | `--environment {staging,production}` | Automate pre-flight checks and release packaging. | Invokes `scripts/deploy.py`, verifies tests, produces `.tar.gz` release asset with SHA-256 log. |
| `rollback` | `--file <backup.sqlite>` | Restore State Ledger from SQLite database backup file. | Restores target database file into active `StateLedger` path. |
| `diagnose` | `--dlq-path <path>` | Parse Dead Letter Queue (.jsonl) and print stack traces. | Reads `/tmp/dlq.jsonl`, formats JSON payloads, prints failed phase and verbatim exception trace. |
| `report` | `--batch-id <id>`, `--output <path>` | Generate batch execution Markdown metrics report. | Queries `StateLedger` for completed/failed run counts, total render time, and API token usage. |

---

## 4. Operational Runbooks & Runtime Controls Specification

### 4.1 6-Step System Startup Pre-Flight Bootstrap
Before executing batch workloads, the orchestrator MUST perform a 6-step pre-flight check:
1. **Config Loading & Validation:** Parse `config/pipeline.yaml`, validate `.env` environment variables and CLI flags.
2. **Structured Logging Setup:** Initialize `structlog` with JSON formatting, binding UUIDv4 `pipeline_run_id`.
3. **Plugin Platform Bootstrap:** Load plugins from `src/plugins/`, perform semver validation, and perform topological DAG sorting.
4. **Declarative Workflow Verification:** Parse workflow blueprint (`config/workflows/pipeline_v1.yaml`), execute Kahn's cycle detection algorithm.
5. **Hardware & Resource Lock Validation:**
   - OpenVINO NPU driver (`/dev/accel/accel0`) & lock file (`/var/lock/openvino_npu.lock`).
   - Intel Arc GPU Level Zero driver (`/dev/dri/renderD128`).
   - FFmpeg binary and QSV hardware encoder availability.
   - ChromaDB connection ping (`data/vector_store/chroma/`).
6. **Checkpoint Recovery & Queue Detection:** Check `CheckpointManager` for existing partial run checkpoint and `data/upload_queue/` for pending offline YouTube uploads.

### 4.2 Graceful Shutdown & Saga Compensation Protocol
* **POSIX Signal Handling:** Traps `SIGINT` (Ctrl+C) and `SIGTERM`.
* **In-Flight Task Draining:** Grants 30s grace period for active nodes (e.g. FFmpeg render) to finish.
* **Saga Compensation Engine:** If a run fails or is aborted:
  1. Emits `[COMPENSATE_TASK]` events in reverse DAG order.
  2. **Partial Render Retention (`PARTIAL_RENDER`):** Retains completed scene MP4s (`scene_1.mp4`) in `data/animation/{slug}/` and registers checksums in `artifact_registry.json`.
  3. **Database Transaction Rollback:** Executes DB savepoint rollbacks for Phase 01–03 writes in SQLite and ChromaDB to avoid duplicate key errors on retry.
  4. **Ephemeral Asset Cleanup:** Unlinks intermediate scratch frames in `/tmp/` while retaining valid master audio WAVs.
  5. Teardowns plugins in reverse topological order and flushes buffers.

### 4.3 System Health Checks & Resource Locks
* **Liveness Probe:** Response time $<100\text{ ms}$ on main event loop.
* **Readiness Probe:** Checks driver paths, cross-process lock availability, storage write permissions.
* **Cross-Process NPU File Lock:** Enforces `fcntl.flock` on `/var/lock/openvino_npu.lock` across process boundaries protecting `/dev/accel/accel0`.
* **GPU VRAM Concurrency Semaphore:** `GPU_SEMAPHORE = asyncio.Semaphore(1)` restricts heavy Manim rendering to 1 concurrent slot ($\le 3,500\text{ MB}$ VRAM allocation out of 8GB shared VRAM).
* **Circuit Breaker Batch Queue Pause:** After 5 consecutive node failures, circuit breaker enters `OPEN` state, pausing batch queue dispatch for a 60s cooldown period instead of failing all remaining queue items into DLQ. Uses **Full Jitter Exponential Backoff**:
  $$T = \text{random}\left(0,\, \min\left(T_{\text{max}},\, T_{\text{base}} \cdot 2^k\right)\right) \quad (T_{\text{base}}=2.0\text{s}, T_{\text{max}}=60.0\text{s})$$

### 4.4 Incident Response & Troubleshooting Runbooks
1. **Dead Letter Queue (DLQ) Backlog:**
   - Command: `python -m src.cli.ops diagnose`
   - Action: Inspect `/tmp/dlq.jsonl`, pretty-print stack traces, re-drive events via `ops dlq redrive`.
2. **Corrupted Vector Database Index:**
   - Symptom: `VectorStoreError: Index checksum mismatch`.
   - Action: `rm -rf data/vector_store/chroma/*` followed by `python -m src.cli index rebuild --source data/metadata.db`.
3. **Stale Hardware Resource Lock / Process Hang:**
   - Symptom: Readiness check failure `DeviceOrResourceBusyError`.
   - Action: `pkill -9 -f "manim render" && pkill -9 -f "ffmpeg"`, `rm -f /var/lock/openvino_npu.lock`, re-run `ops health`.
4. **LLM Syntax Hallucination in Manim Scene:**
   - Symptom: Scene render fails due to Cairo/Python syntax error.
   - Action: Run `ops diagnose`, locate cached Jinja scene script, fix syntax error manually, execute `ops resume`.
5. **YouTube API Quota Limit Exceeded:**
   - Symptom: HTTP 403 `quotaExceeded`.
   - Action: Automatically saved to `data/upload_queue/{slug}_upload.json`; offline worker auto-dispatches at 00:00 PST quota reset.

---

## 5. Specification Mining Discovery Tables

### 5.1 Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Master CLI | `ops run` | Triggers end-to-end execution for single or batch problems. | Problem slug / slug file, config path | Execution logs, exit code 0/1 | Catches exceptions, logs error, populates DLQ | `ORIGINAL_REQUEST.md`, `PromptBook/Phase14/11_Operations_CLI.md` |
| 2 | Master CLI | `ops status` | Queries active execution state of pipeline runs from SQLite ledger. | `--watch` flag, optional `--run-id` | Formatted status table / JSON | Returns error message if DB inaccessible | `ORIGINAL_REQUEST.md`, `PromptBook/Phase14/11_Operations_CLI.md` |
| 3 | Master CLI | `ops resume` | Rehydrates state from ledger and resumes execution at failed step. | `--run-id` or `--checkpoint` path | Resumed execution outcome | Throws error if run_id not found in ledger | `ORIGINAL_REQUEST.md`, `PromptBook/Phase14/01_Production_Architecture.md` |
| 4 | Master CLI | `ops health` | Runs pre-flight hardware, driver, DB, and lock file readiness checks. | `--check-type {liveness, readiness}` | Health JSON report, exit code 0/1 | Exit code 1 if driver missing or lock held | `ORIGINAL_REQUEST.md`, `PromptBook/Phase14/01_Production_Architecture.md` |
| 5 | Master CLI | `ops benchmark` | Profiles CPU, GPU VRAM peak memory, and render throughput. | Benchmark config | Benchmark metrics output | Reports resource allocation error | `PromptBook/Phase14/11_Operations_CLI.md` |
| 6 | Master CLI | `ops deploy` | Pre-flight checks and release package generator (`scripts/deploy.py`). | Release target | `.tar.gz` package & SHA-256 log | Aborts on script missing or test failure | `PromptBook/Phase14/11_Operations_CLI.md`, `PromptBook/Phase14/12_Operational_Documentation.md` |
| 7 | Master CLI | `ops rollback` | Restores State Ledger database from backup file. | `--file <backup.sqlite>` | Restoration status | Aborts if backup file missing/corrupted | `PromptBook/Phase14/11_Operations_CLI.md` |
| 8 | Master CLI | `ops diagnose` | Parses Dead Letter Queue JSONL file and pretty-prints stack traces. | `--dlq-path` (default `/tmp/dlq.jsonl`) | Pretty-printed stack traces & failed phases | Reports clean DLQ if file absent | `PromptBook/Phase14/11_Operations_CLI.md` |
| 9 | Master CLI | `ops report` | Generates batch execution metrics summary report in Markdown. | `--batch-id`, `--output` path | Batch summary metrics | Returns error if ledger record empty | `PromptBook/Phase14/11_Operations_CLI.md` |
| 10 | Pipeline Orchestrator | `PipelineRunner` / `WorkflowEngine` | Links 13 nodes into chronological, crash-safe, idempotent DAG. | `run_id`, node sequence | `EngineResult` object | Traps node exceptions, records failure in ledger | `ORIGINAL_REQUEST.md`, `PromptBook/Phase14/02_End_to_End_Workflows.md` |
| 11 | Resilience | Step Idempotency Check | Checks completed steps in SQLite `StateLedger` before node execution. | Node name, `run_id` | Skipped step execution | None (safe skip) | `src/core/workflow/engine.py`, `PromptBook/Phase14/01_Production_Architecture.md` |
| 12 | Resilience | Partial Render Retention | Preserves completed scene MP4s when rendering fails on a later scene. | Scene renders, checksums | `PARTIAL_RENDER` artifact record | Retains valid MP4s on disk for resume | `PromptBook/Phase14/01_Production_Architecture.md` |
| 13 | Hardware Locks | NPU Cross-Process Lock | Enforces exclusive access to `/dev/accel/accel0` using `fcntl.flock`. | Lock file `/var/lock/openvino_npu.lock` | Lock handle context | Blocks until lock released or timeout | `PromptBook/Phase14/01_Production_Architecture.md` |
| 14 | Hardware Locks | GPU VRAM Concurrency Limit | Limits Manim rendering to 1 active slot via `asyncio.Semaphore(1)`. | Rendering request | Acquired semaphore slot | Throws timeout if slot unavailable | `PromptBook/Phase14/01_Production_Architecture.md` |
| 15 | Resilience | Circuit Breaker Queue Pause | Pauses batch queue dispatch for 60s cooldown when 5 failures occur. | Node execution errors | `OPEN` state, 60s pause | Prevents cascading DLQ flooding | `PromptBook/Phase14/01_Production_Architecture.md` |
| 16 | Publishing | Offline Upload Queue | Saves video payload to `data/upload_queue/` on YouTube API 403 quota error. | `QuotaExceededError` | Queued JSON item file | Auto-resumes dispatch at 00:00 PST | `PromptBook/Phase14/01_Production_Architecture.md` |
| 17 | Script Node | Error-Feedback Retry Loop | Aggressively retries LLM script generation by feeding Pydantic errors back. | `ValidationError`, `JSONDecodeError` | Fixed script JSON | Max 3 retries before raising error | `ORIGINAL_REQUEST.md`, `src/pipeline/nodes/script_generator_node.py` |
| 18 | Video Node | Subprocess Temporary Cleanup | Manages and unlinks scratch files after assembly to prevent disk full. | Temporary directory paths | Cleaned disk space | Ensures cleanup in `finally` block | `ORIGINAL_REQUEST.md`, `src/pipeline/nodes/video_assembly_node.py` |

### 5.2 Edge Cases & Observed Behaviors

| # | Feature | Input | Observed / Expected Behavior |
|---|---------|-------|------------------------------|
| 1 | Pipeline Resumption | Mid-pipeline crash at Phase 09 (Manim render) | Engine reads `StateLedger`, detects completed steps (Phase 01–08), skips them, and resumes execution directly at Phase 09. |
| 2 | Partial Render Retention | Scene 4 fails during Manim render after Scenes 1–3 completed | Scenes 1–3 `.mp4` files are preserved on disk. `artifact_registry.json` status set to `PARTIAL_RENDER`. Upon resume, only Scene 4 is rendered. |
| 3 | NPU Lock Contention | Concurrent process tries to invoke OpenVINO TTS while NPU lock held | Process blocks at `fcntl.flock('/var/lock/openvino_npu.lock')` until current inference finishes or 300s timeout expires. |
| 4 | YouTube API Quota Exhaustion | HTTP 403 `quotaExceeded` received during Phase 13 upload | Video, SRT, thumbnail, and metadata are written to `data/upload_queue/{slug}_upload.json`. Workflow completes without crashing, and offline worker dispatches item after 00:00 PST. |
| 5 | LLM Script Validation Failure | LLM returns malformed JSON or missing required field on script generation | `ScriptGeneratorNode` traps `ValidationError`, constructs prompt with exact error message string, and re-invokes LLM up to 3 times. |
| 6 | Circuit Breaker Cooldown | 5 consecutive external API network timeouts occur during batch run | Circuit breaker trips to `OPEN`. Batch queue halts processing for 60s cooldown instead of burning through remaining 50 batch queue items. |
| 7 | Process Interruption (SIGINT) | User sends `Ctrl+C` while FFmpeg is stitching video | Orchestrator traps `SIGINT`, waits up to 30s for current FFmpeg subprocess chunk to finish, writes checkpoint to SQLite `StateLedger`, and exits cleanly with code 130. |
| 8 | Force Clean Start | `--force` flag supplied to `ops run` | Idempotency checks are bypassed; engine re-executes all nodes from Phase 01 regardless of existing completed entries in `StateLedger`. |
| 9 | Corrupted ChromaDB Index | Vector DB index file damaged | `ops health` fails readiness check; operator executes `rm -rf data/vector_store/chroma/*` and rebuilds index from `MetadataStore` SQLite via `ops index rebuild`. |
| 10 | Stale Lock File | System crashed while holding `/var/lock/openvino_npu.lock` | Readiness check reports `DeviceOrResourceBusyError`; operator clears lock via `rm -f /var/lock/openvino_npu.lock` and re-checks health. |

---

## 6. Conclusion & Implementation Guidance for Orchestrator

This specification analysis establishes complete coverage for:
1. **Master Operations CLI (`src/cli/ops.py`)**: Must expose commands `run`, `status`, `resume`, `health`, `benchmark`, `deploy`, `rollback`, `diagnose`, `report`.
2. **Pipeline Orchestrator (`src/core/orchestrator/pipeline_runner.py`)**: Must sequentially link all nodes via `WorkflowEngine`, integrating SQLite `StateLedger` for idempotency and crash recovery.
3. **Operational Runbooks (`PromptBook/Phase14/01_Production_Orchestration.md`)**: Must document system startup procedures, 6-step pre-flight checks, graceful shutdown & Saga compensation protocols, resource locking, circuit breaker policies, incident runbooks, and YouTube quota management strategies.

All mined specifications are fully backed by `ORIGINAL_REQUEST.md`, `PromptBook/Phase14/01_Production_Architecture.md`, `11_Operations_CLI.md`, `12_Operational_Documentation.md`, and the existing codebase.
