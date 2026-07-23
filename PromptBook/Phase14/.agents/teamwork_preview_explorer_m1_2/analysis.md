# Phase 14 / Milestone 1 / Task 2: Subsystem Analysis & 12-Hour Integration Architecture Report (Phase 01 – Phase 07)

**Author:** Explorer 2 (Phase 14 Integration Architecture Team)  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Target Environment:** Intel Core Ultra 7 155H · Ubuntu 25.10 LTS · Python 3.12 · Intel Arc GPU / NPU  
**Document Version:** 1.0.0  
**Status:** Complete Analysis Report  
**Working Directory:** `/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/.agents/teamwork_preview_explorer_m1_2/`

---

## 1. Executive Summary

This research report provides a comprehensive architectural breakdown of **Phase 01 through Phase 07** of the Automated Data Structures and Algorithms (DSA) Educational YouTube Video Generation Pipeline. 

The analysis synthesizes both the **functional video production pipeline stages** (Knowledge Ingestion, Knowledge Organization, Vector RAG Retrieval, Problem Selection & Curation, Script Generation, Code Execution & Visualization Spec, and Animation & Voice Alignment) and their **underlying architectural support framework** (Domain Models, RAG Architecture, System Runtime, Plugin Platform, EventBus Architecture, Workflow Engine, and Persistence Layer).

Key Findings:
1. **Contract Standardisation:** Inter-phase communication is strictly decoupled via Python `typing.Protocol` interfaces, immutable frozen dataclasses, and event payloads published over an asynchronous priority-queued `EventBus`.
2. **Deterministic Payload Compilation:** Non-deterministic generative AI operations (Gemini LLM script creation, prompt chains) compile into rigid, versioned JSON artifacts (`VideoScriptPayload`, `VisualizationSpec`) before entering downstream deterministic audio/video rendering engines.
3. **Resilience & Idempotency:** Heavy compute stages (Kokoro TTS, Manim GPU animation rendering) rely on cryptographic SHA-256 checksums attached to `RenderedScene` dataclasses and local SQLite/JSON checkpointing. If an 8-hour render fails at Scene 10, execution resumes at Scene 10 without re-rendering Scenes 1–9.
4. **12-Hour Chronological Batch Pipeline:** The 12-hour batch execution window allocates ~3 hours to data processing, graph organization, RAG retrieval, curation, and script generation (Phase 01–05), ~45 minutes to code execution sandboxing and visualization spec compilation (Phase 06), ~6.25 hours to voice synthesis and GPU scene rendering (Phase 07), and ~1.5 hours to FFmpeg assembly, quality verification, and resumable YouTube API upload.

---

## 2. Phase-by-Phase Comprehensive Deep-Dive

---

### 2.1 Phase 01: Knowledge Ingestion / Data Ingestion

#### 2.1.1 Purpose & Architectural Scope
Phase 01 handles the extraction, normalization, validation, enrichment, deduplication, and persistence of raw data from heterogeneous external sources (LeetCode API, cppreference HTML, Wikipedia REST API, local PDFs/textbooks). It abstracts source-specific idiosyncrasies into a unified document pipeline.

#### 2.1.2 Inputs, Outputs, Data Formats & Artifacts
*   **Inputs:**
    *   Target URIs / Problem Slugs (e.g., `https://leetcode.com/problems/two-sum/`, `two-sum`).
    *   Raw web payloads (HTML, JSON, PDF bytes).
    *   Source connector configuration profiles.
*   **Outputs & Data Models:**
    *   `RawContent`: (`uri: str`, `raw_bytes: bytes`, `mime_type: str`, `fetched_at: datetime`).
    *   `NormalizedDocument` (Dataclass): (`doc_id: str`, `source_type: str`, `title: str`, `raw_markdown: str`, `cleaned_text: str`, `tags: List[str]`, `sha256_hash: str`, `ingested_at: datetime`).
    *   `IngestionResult` (Dataclass): (`doc_id: str`, `status: IngestionStatus` [`SUCCESS`, `DUPLICATE`, `FAILED`], `dedup_sha256: str`, `persisted_id: str`).
*   **Artifacts Produced:**
    *   Normalized Markdown document stored in SQLite `MetadataStore` (`knowledge` collection).
    *   Ingestion audit record and SHA-256 hash index entry.

#### 2.1.3 Interfaces, Contract Boundaries & Event Dependencies
*   **Protocol Interface:**
    ```python
    class ISourceConnector(Protocol):
        async def extract(self, uri: str) -> RawContent: ...
    ```
*   **Core Engine Contract:** `IngestionEngine.ingest(uri: str) -> IngestionResult`
*   **Event Dependencies:**
    *   *Emits:* `scraper.v1.problem_scraped`, `ingestion.v1.persisted`, `ingestion.v1.skipped`, `ingestion.v1.failed`.
    *   *Listens to:* `pipeline.v1.started`, `workflow.trigger_task`.

#### 2.1.4 Resource Constraints, Error Handling & Fallbacks
*   **Resource Constraints:** Network I/O bound; LeetCode/Wikipedia rate limits (10–30 req/min); RAM < 500MB per connector process; execution timeout = 120s per URI via `asyncio.wait_for`.
*   **Error Conditions:** HTTP 429/503 network timeouts; malformed HTML/JSON; invalid UTF-8 encoding.
*   **Retry & Fallback:** Exponential backoff retry (3 attempts); SHA-256 deduplication match halts pipeline gracefully (`INGESTION_SKIPPED`) returning existing `doc_id`; fatal extraction errors route to Dead Letter Queue (DLQ) and emit `pipeline.v1.fatal_error`.

---

### 2.2 Phase 02: Knowledge Organization / Knowledge Base & Taxonomy

#### 2.2.1 Purpose & Architectural Scope
Phase 02 acts as analytical middleware between raw ingestion and vector storage. It categorizes documents using a strict 3-tier hierarchical ontology (Data Structures, Algorithms, Algorithmic Patterns), builds a Directed Acyclic Graph (DAG) Knowledge Graph (`REQUIRES`, `IMPLEMENTS`, `SIMILAR_TO`), computes prerequisite chains, and executes Index Preparation for chunking.

#### 2.2.2 Inputs, Outputs, Data Formats & Artifacts
*   **Inputs:**
    *   `NormalizedDocument` from Phase 01.
    *   Ontology definition models (`Taxonomy.DataStructure.*`, `Taxonomy.Algorithm.*`, `Taxonomy.Pattern.*`).
*   **Outputs & Data Models:**
    *   `TaxonifiedDocument`: Normalized document augmented with validated ontology tags.
    *   `KnowledgeGraphNode`: (`node_id: str`, `label: str`, `category: str`, `difficulty: str`).
    *   `KnowledgeGraphEdge`: (`source_id: str`, `target_id: str`, `relation_type: RelationEnum`).
    *   `PreparedIndexChunk`: (`chunk_id: str`, `doc_id: str`, `text_content: str`, `taxonomy_metadata: Dict`, `graph_edges: List[Dict]`, `chunk_sha256: str`).
    *   `LearningPath`: Topological sequence of prerequisite nodes.
*   **Artifacts Produced:**
    *   SQLite Knowledge Graph table updates (`nodes`, `edges`).
    *   Cleansed, taxonomized chunk records in `MetadataStore`.

#### 2.2.3 Interfaces, Contract Boundaries & Event Dependencies
*   **Interfaces:**
    *   `ITaxonomyManager.classify(doc: NormalizedDocument) -> ClassifiedTaxonomy`
    *   `IKnowledgeGraph.get_prerequisites(slug: str) -> List[KnowledgeGraphNode]`
    *   `ILearningPathGenerator.topological_sort(graph) -> LearningPath`
    *   `IIndexPreparer.prepare_chunks(doc: TaxonifiedDocument) -> List[PreparedIndexChunk]`
*   **Event Dependencies:**
    *   *Listens to:* `scraper.v1.problem_scraped`, `ingestion.v1.persisted`.
    *   *Emits:* `tag.v1.tags_extracted`, `memory.v1.graph_updated`, `organization.v1.index_ready`.

#### 2.2.4 Resource Constraints, Error Handling & Fallbacks
*   **Resource Constraints:** CPU and memory bound (NetworkX / SQLite operations); RAM < 1GB; execution latency < 5s per problem document batch.
*   **Error Conditions:** Unrecognized tags; circular prerequisite dependencies in graph; database write lock contention.
*   **Retry & Fallback:** Unclassified tags are relegated to an `Unclassified` secondary tag array rather than crashing the classifier; cycle detection algorithms break circular dependencies and log warnings; SQLite write locks trigger 5 retries with jittered backoff.

---

### 2.3 Phase 03: RAG / Vector Database & Retrieval

#### 2.3.1 Purpose & Architectural Scope
Phase 03 is the physical execution runtime for semantic search and vector retrieval. It listens for `organization.v1.index_ready`, generates floating-point vector embeddings via plugin providers (OpenAI / HuggingFace), upserts vectors into multi-tenant namespaces (`ALGORITHMS`, `DATA_STRUCTURES`, `PATTERNS`, `PROBLEMS`), and processes queries with similarity search, cross-encoder reranking, and prompt context building.

#### 2.3.2 Inputs, Outputs, Data Formats & Artifacts
*   **Inputs:**
    *   `PreparedIndexChunk` list from Phase 02.
    *   Query strings from downstream script planners.
*   **Outputs & Data Models:**
    *   `VectorEmbedding`: (`chunk_id: str`, `vector: List[float]`, `dimension: int`, `namespace: str`).
    *   `RetrievedChunk`: (`chunk_id: str`, `text: str`, `similarity_score: float`, `rerank_score: float`, `metadata: Dict`).
    *   `RAGContextResponse`: (`query: str`, `retrieved_chunks: List[RetrievedChunk]`, `formatted_context: str`, `token_count: int`).
*   **Artifacts Produced:**
    *   Vector database indices in ChromaDB / Pinecone / Milvus.
    *   Redis / In-memory query response cache entries.

#### 2.3.3 Interfaces, Contract Boundaries & Event Dependencies
*   **Interfaces:**
    *   `AsyncIndexer.upsert(chunks: List[PreparedIndexChunk]) -> None`
    *   `IKnowledgeRouter.route(query: str) -> NamespaceEnum`
    *   `ISemanticRetriever.retrieve(query: str, namespace: NamespaceEnum, top_k: int) -> List[RetrievedChunk]`
    *   `IReranker.rerank(query: str, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]`
*   **Event Dependencies:**
    *   *Listens to:* `organization.v1.index_ready`.
    *   *Emits:* `rag.v1.context_ready`, `rag.v1.indexed`.

#### 2.3.4 Resource Constraints, Error Handling & Fallbacks
*   **Resource Constraints:** Network I/O and API rate-limited; embedding batch size = 100 chunks; maximum concurrent API calls controlled via `asyncio.Semaphore(10)`; P99 retrieval latency target < 800ms; Vector DB RAM allocation ~2–4GB.
*   **Error Conditions:** LLM embedding API HTTP 429 rate limit / timeout; Vector DB network connection failure; query context length window overflow.
*   **Retry & Fallback:** 3 retries with exponential backoff on API rate limits; Vector DB connection failure degrades runtime status to `DEGRADED` and falls back to FTS5 keyword search in SQLite `MetadataStore`; context builder dynamically truncates chunks to fit target LLM token window.

---

### 2.4 Phase 04: Problem Selection & Topic Curation

#### 2.4.1 Purpose & Architectural Scope
Phase 04 governs problem selection, target audience profiling (Beginner, Intermediate, Advanced), curriculum alignment, learning objective definition, and educational strategy formulation.

#### 2.4.2 Inputs, Outputs, Data Formats & Artifacts
*   **Inputs:**
    *   Workflow trigger payload (problem slug or automated daily cron event).
    *   Knowledge Graph state & audience profile configuration.
*   **Outputs & Data Models:**
    *   `CurationPlan`: (`problem_slug: str`, `target_difficulty: str`, `prerequisites_to_recap: List[str]`, `learning_objectives: List[str]`).
    *   `EducationalStrategySpec`: (`teaching_paradigm: str`, `analogy_type: str`, `complexity_focus: str`).
*   **Artifacts Produced:**
    *   `curation_plan_<slug>.json` stored in `ArtifactStore`.

#### 2.4.3 Interfaces, Contract Boundaries & Event Dependencies
*   **Interfaces:**
    *   `IEducationalPlanner.plan_topic(slug: str, target_audience: str) -> CurationPlan`
    *   `ILearningObjectives.generate(plan: CurationPlan) -> List[str]`
*   **Event Dependencies:**
    *   *Listens to:* `pipeline.v1.started`, `scheduler.v1.cron_trigger`.
    *   *Emits:* `curation.v1.topic_selected`.

#### 2.4.4 Resource Constraints, Error Handling & Fallbacks
*   **Resource Constraints:** Lightweight CPU/Memory (< 100MB RAM, runtime < 2s).
*   **Error Conditions:** Target problem missing from Knowledge Graph; invalid audience difficulty parameter.
*   **Retry & Fallback:** Missing problem triggers Phase 01 Ingestion on-the-fly; invalid difficulty parameter falls back to `Intermediate` template profile with standard 3-goal objective structure.

---

### 2.5 Phase 05: Educational Content / Script Generation

#### 2.5.1 Purpose & Architectural Scope
Phase 05 is the generative core of the pipeline. It consumes `RAGContextResponse` (Phase 03) and `CurationPlan` (Phase 04), executes a 4-step prompt chain (Objectives -> Storyboard -> Narration Plan -> Animation Directives), and verifies script validity via an LLM-as-a-Judge self-correction loop, compiling the output into a deterministic `VideoScriptPayload` JSON.

#### 2.5.2 Inputs, Outputs, Data Formats & Artifacts
*   **Inputs:**
    *   `CurationPlan` (Phase 04) & `RAGContextResponse` (Phase 03).
    *   Prompt templates from Prompt Template Library.
*   **Outputs & Data Models:**
    *   `VideoScriptPayload` (JSON Schema):
        ```json
        {
          "version": "1.0",
          "slug": "two-sum",
          "metadata": {
            "target_audience": "Beginner",
            "total_scenes": 5,
            "estimated_duration_sec": 320
          },
          "scenes": [
            {
              "scene_id": 1,
              "type": "theory_intro",
              "narration": "Welcome back! Today we are solving Two Sum.",
              "animation_directives": {
                "action": "DisplayTitleCard",
                "parameters": {"title": "Two Sum", "difficulty": "Easy"}
              }
            }
          ]
        }
        ```
*   **Artifacts Produced:**
    *   `script_v1_<slug>.json` stored in `ArtifactStore`.
    *   Prompt execution trace and LLM-as-a-Judge evaluation score log.

#### 2.5.3 Interfaces, Contract Boundaries & Event Dependencies
*   **Interfaces:**
    *   `IScriptGenerator.generate(curation: CurationPlan, rag_context: RAGContextResponse) -> VideoScriptPayload`
    *   `IScriptReviewer.evaluate(script: VideoScriptPayload, rag_context: RAGContextResponse) -> ReviewResult`
*   **Event Dependencies:**
    *   *Listens to:* `rag.v1.context_ready`, `curation.v1.topic_selected`.
    *   *Emits:* `script.v1.generation_complete`, `script.v1.review_failed`.

#### 2.5.4 Resource Constraints, Error Handling & Fallbacks
*   **Resource Constraints:** Generative LLM API token & rate limits (~4,500 LLM tokens per script run); generation latency 30–90 seconds.
*   **Error Conditions:** Malformed JSON output; hallucinated mathematical time complexities; character count limit violation for narration.
*   **Retry & Fallback:** LLM structured output enforcement (`instructor` / Pydantic validation); LLM-as-a-Judge rejection triggers draft re-generation (max 3 retries); rate limit HTTP 429 triggers exponential backoff retry; max retry exhaustion falls back to conservative fallback script template.

---

### 2.6 Phase 06: Code Execution & Visualization Spec Generation

#### 2.6.1 Purpose & Architectural Scope
Phase 06 extracts code snippets and visual scene descriptions from the script payload, executes Python/C++ code inside a sandboxed isolated runtime to verify correctness and capture step-by-step state traces (variable values, pointer positions, array indices), and constructs precise visual scene placement specifications (`VisualizationSpec`).

#### 2.6.2 Inputs, Outputs, Data Formats & Artifacts
*   **Inputs:**
    *   `VideoScriptPayload` JSON from Phase 05.
    *   Code snippets (Python 3.12 / C++20).
*   **Outputs & Data Models:**
    *   `CodeExecutionTrace`: (`stdout: str`, `return_code: int`, `state_snapshots: List[Dict[str, Any]]`, `execution_time_ms: float`).
    *   `VisualizationSpec`: (`scene_id: int`, `canvas_dimensions: Tuple[int, int]`, `elements: List[VisualElementSpec]`, `code_highlight_lines: List[int]`, `layout_grid: Dict`).
*   **Artifacts Produced:**
    *   `visualization_spec_<slug>.json` stored in `ArtifactStore`.
    *   Validated Python/C++ source file artifacts.

#### 2.6.3 Interfaces, Contract Boundaries & Event Dependencies
*   **Interfaces:**
    *   `ICodeExecutor.execute_sandboxed(code: str, test_cases: List[TestCase]) -> CodeExecutionTrace`
    *   `IVisualizationSpecBuilder.build(scene: SceneSpec, trace: CodeExecutionTrace) -> VisualizationSpec`
*   **Event Dependencies:**
    *   *Listens to:* `script.v1.generation_complete`.
    *   *Emits:* `visualization.v1.spec_ready`.

#### 2.6.4 Resource Constraints, Error Handling & Fallbacks
*   **Resource Constraints:** Execution runtime sandbox enforced via Docker / Seccomp isolation; resource limits per code block: 1 vCPU, 256MB RAM, 5.0s execution wall-clock timeout.
*   **Error Conditions:** Code compilation error / zero-division exception; sandbox memory overflow; visual element coordinate overlap.
*   **Retry & Fallback:** Automated LLM code patcher attempt (1 attempt); fallback to canonical verified solution code from RAG database; heuristic layout solver automatically resolves coordinate overlaps.

---

### 2.7 Phase 07: Animation & Voiceover Alignment Spec

#### 2.7.1 Purpose & Architectural Scope
Phase 07 is the physical media synthesis and alignment engine. It synthesizes speech audio from narration text via TTS (Kokoro/ElevenLabs), generates subtitle files (`.srt`/`.vtt`), compiles Python Manim visual scene specifications into `.mp4` video files, aligns audio timing with video scene duration, and multiplexes audio, video, subtitles, and thumbnails into the final `.mp4` package via FFmpeg.

#### 2.7.2 Inputs, Outputs, Data Formats & Artifacts
*   **Inputs:**
    *   `VideoScriptPayload` (Phase 05) & `VisualizationSpec` (Phase 06).
    *   Audio TTS parameters & Manim render settings (1080p60 / 4K).
*   **Outputs & Data Models:**
    *   `AudioArtifact`: (`audio_id: str`, `file_path: str`, `duration_sec: float`, `sample_rate: int`).
    *   `RenderedScene`: (`scene_id: int`, `video_path: str`, `duration_sec: float`, `resolution: str`, `checksum: str`).
    *   `SubtitleArtifact`: (`srt_path: str`, `line_count: int`).
    *   `FinalVideoArtifact`: (`video_path: str`, `filesize_mb: float`, `duration_sec: float`, `checksum: str`).
*   **Artifacts Produced:**
    *   `voice_<slug>_scene<N>.wav` audio binaries.
    *   `scene_<slug>_<N>.mp4` scene animation binaries.
    *   `subtitles_<slug>.srt` subtitle file.
    *   `final_<slug>.mp4` final assembled YouTube deliverable.
    *   `thumbnail_<slug>.png` 1920x1080 thumbnail image.

#### 2.7.3 Interfaces, Contract Boundaries & Event Dependencies
*   **Interfaces:**
    *   `IVoiceProvider.generate_audio(narration: Dict) -> AudioArtifact`
    *   `IManimRenderer.render_scene(spec: VisualizationSpec) -> RenderedScene`
    *   `ISubtitleGenerator.generate(audio: AudioArtifact, narration: str) -> SubtitleArtifact`
    *   `IVideoBuilder.assemble(scenes: List[RenderedScene], audio: List[AudioArtifact], srt: SubtitleArtifact) -> FinalVideoArtifact`
*   **Event Dependencies:**
    *   *Listens to:* `visualization.v1.spec_ready`, `script.v1.generation_complete`.
    *   *Emits:* `voice.v1.audio_rendered`, `animation.v1.render_complete`, `builder.v1.video_assembled`.

#### 2.7.4 Resource Constraints, Error Handling & Fallbacks
*   **Resource Constraints:** Compute and GPU bound (Intel Arc GPU / NPU / Multi-core CPU); rendering budget consumes ~6.25 hours of 12-hour window; GPU VRAM 4–8GB; temporary scratch disk space 10–30GB per run.
*   **Error Conditions:** Kokoro TTS synthesis timeout; Manim GPU render OOM / crash; FFmpeg filtergraph multiplexing failure.
*   **Retry & Fallback:** TTS API failure triggers exponential backoff (3 retries); scene-level idempotency via `RenderedScene.checksum` allows resuming rendering at the exact failed scene without re-rendering preceding scenes; local payload validation before FFmpeg execution prevents mid-pipeline assembly crashes.

---

## 3. Interfaces, Contract Boundaries & Event Flow Topology

The following matrix documents the contract boundaries, data payload schemas, and event routing logic connecting Phase 01 through Phase 07.

| Phase Boundary | Trigger Event Name | Payload Key Fields | Publisher -> Subscriber | Primary Contract / Interface |
|---|---|---|---|---|
| **Phase 01 -> Phase 02** | `scraper.v1.problem_scraped` | `slug`, `title`, `difficulty`, `raw_content`, `source_url` | Ingestion Engine -> Taxonomy & Organization | `ISourceConnector` -> `NormalizedDocument` |
| **Phase 01 -> Phase 02** | `ingestion.v1.persisted` | `doc_id`, `source_type`, `sha256_hash` | Ingestion Engine -> Knowledge Graph Builder | `MetadataStore.save_metadata()` |
| **Phase 02 -> Phase 03** | `tag.v1.tags_extracted` | `slug`, `tags`, `confidence` | Taxonomy Classifier -> RAG & Memory Service | `ITaxonomyManager` |
| **Phase 02 -> Phase 03** | `organization.v1.index_ready` | `doc_id`, `chunk_count`, `taxonomy_domain` | Index Preparer -> Async Vector Indexer | `IIndexPreparer` -> `PreparedIndexChunk` |
| **Phase 03 -> Phase 04/05** | `rag.v1.context_ready` | `slug`, `retrieved_chunks`, `educational_plan` | RAG Context Builder -> Educational Planner & Script Generator | `ISemanticRetriever` -> `RAGContextResponse` |
| **Phase 04 -> Phase 05** | `curation.v1.topic_selected` | `problem_slug`, `target_difficulty`, `learning_objectives` | Curation Engine -> Script Generator | `IEducationalPlanner` -> `CurationPlan` |
| **Phase 05 -> Phase 06** | `script.v1.generation_complete` | `slug`, `voiceover_text`, `visual_cues`, `duration_estimate_sec` | Script Generator -> Code Executor & Visualization Planner | `IScriptGenerator` -> `VideoScriptPayload` |
| **Phase 06 -> Phase 07** | `visualization.v1.spec_ready` | `slug`, `scene_specs`, `code_trace` | Visualization Builder -> Manim Renderer & Voice Engine | `IVisualizationSpecBuilder` -> `VisualizationSpec` |
| **Phase 07 (Sub-module)** | `voice.v1.audio_rendered` | `slug`, `audio_path`, `duration` | Voice Provider -> Video Builder (FFmpeg) | `IVoiceProvider` -> `AudioArtifact` |
| **Phase 07 (Sub-module)** | `animation.v1.render_complete` | `slug`, `video_path`, `resolution` | Manim Renderer -> Video Builder (FFmpeg) | `IManimRenderer` -> `RenderedScene` |
| **Phase 07 -> Terminal** | `builder.v1.video_assembled` | `slug`, `final_video_path`, `filesize_mb`, `duration` | Video Builder -> YouTube Publisher | `IVideoBuilder` -> `FinalVideoArtifact` |

---

## 4. Chronological 12-Hour Batch Pipeline Timeline

The v2.0 production integration model transitions the system from real-time interactive execution to a deterministic 12-hour batch pipeline run.

### 4.1 Chronological Execution Gantt Chart

```
Time (HH:MM)  Phase & Stage Description                     Resource / Bottleneck Profile
00:00 - 00:45 Phase 01: Knowledge Ingestion & Scraping        [Network I/O & Scraper Throttling]
00:45 - 01:30 Phase 02: Knowledge Org, Taxonomy & Graph      [CPU Graph Sorting & SQLite Write]
01:30 - 02:15 Phase 03: RAG Indexing & VectorDB Upsert        [LLM Embedding API & Network]
02:15 - 02:30 Phase 04: Problem Selection & Curation          [Lightweight CPU Planning]
02:30 - 03:30 Phase 05: Script Gen & LLM-as-a-Judge Loop     [Generative LLM Token Rate Limits]
03:30 - 04:15 Phase 06: Sandboxed Execution & Vis Spec        [Docker Sandboxing & Math Grid Solver]
04:15 - 05:30 Phase 07 (Part A): TTS Voice & Speech Align     [NPU / GPU Audio Synthesis]
05:30 - 10:30 Phase 07 (Part B): Heavy Manim GPU Rendering   [Intel Arc GPU / VRAM / CPU Core Max]
10:30 - 11:30 Assembly, Subtitles & Thumbnail Multiplexing   [FFmpeg H.264 HW Enc & Disk I/O]
11:30 - 12:00 Pre-flight Checks & Resumable YouTube Upload   [Network Upload & YouTube API v3]
```

### 4.2 Resource Allocation & Parallelism Matrix

| Pipeline Phase Window | CPU Utilization | GPU / NPU Allocation | Memory (RAM / VRAM) | Disk I/O & Storage Workspace | Network Bandwidth |
|---|---|---|---|---|---|
| **Phase 01 (00:00 - 00:45)** | Low (20%) | Idle | 500MB RAM | Low (SQLite metadata writes) | High (Raw scraping & API calls) |
| **Phase 02 (00:45 - 01:30)** | Moderate (40%) | Idle | 1GB RAM | Moderate (Graph node index) | Minimal |
| **Phase 03 (01:30 - 02:15)** | Low (25%) | Idle | 2GB RAM | Moderate (Vector DB write) | High (Embedding API calls) |
| **Phase 04 (02:15 - 02:30)** | Low (10%) | Idle | 250MB RAM | Negligible | Minimal |
| **Phase 05 (02:30 - 03:30)** | Low (15%) | Idle | 500MB RAM | Low (Script JSON output) | High (Gemini API LLM prompt chain) |
| **Phase 06 (03:30 - 04:15)** | Moderate (50%) | Idle | 1GB RAM | Low (Trace output) | Minimal |
| **Phase 07 Voice (04:15 - 05:30)** | Moderate (45%) | Active (NPU / GPU TTS) | 2GB RAM / 2GB VRAM | Moderate (`.wav` audio creation) | Minimal / Low |
| **Phase 07 Render (05:30 - 10:30)** | High (90%) | Max (Intel Arc GPU Manim) | 8GB RAM / 6GB VRAM | High (10–30GB MP4 scene scratch space) | Minimal |
| **Assembly (10:30 - 11:30)** | High (80%) | Hardware H.264 Video Encoder | 4GB RAM | Max (FFmpeg multiplexing & write) | Minimal |
| **Publishing (11:30 - 12:00)** | Low (10%) | Idle | 500MB RAM | Low | Max (Chunked video upload) |

### 4.3 Checkpointing, Idempotency & Fault-Recovery Architecture

1. **State Persistence (`StateStore`):**
   * The `WorkflowEngine` records DAG task state transitions (`PENDING` -> `RUNNING` -> `SUCCESS`) to SQLite/JSON after every step.
   * If the pipeline halts mid-way, state re-hydration allows resuming execution at the exact pending task node.
2. **Artifact Checksumming (`RenderedScene` Idempotency):**
   * Every rendered scene artifact carries a SHA-256 hash computed over its input script parameters and visualization directives.
   * If a 12-hour batch crashes during Scene 12 at Hour 9, restarting the pipeline checks `RenderedScene` checksums in `ArtifactStore` and instantly skips Scenes 1–11.
3. **Resumable Network Operations (YouTube Upload):**
   * Network publishing uses resumable HTTP chunked upload protocols. If connection drops at 98%, upload reconnects and resumes from the exact offset, preventing pipeline invalidation.
4. **Pre-flight Payload Validation:**
   * Downstream publishers execute strict local payload validation (`_validate_payload()`) before initiating external network requests (e.g. verifying thumbnail size < 2.0MB and video path existence), eliminating last-second pipeline crashes.

---

## 5. Evidence Chain & Reference Index

| Finding / Analysis Point | Primary Source Document in `/PromptBook/` | Verification Path / Line References |
|---|---|---|
| **Event Driven Topologies & Decoupling** | `10_Event_Driven_Architecture.md` | Lines 22–77 (Pub-Sub topology, Golden Rule) |
| **Master Event Catalog & Schemas** | `11_Event_Catalog.md` | Lines 32–168 (Event schemas for Phase 01–07) |
| **Declarative Workflow Engine & SAGAs** | `11_Workflow_Engine.md` | Lines 35–75, 148–150 (DAG format & rollback) |
| **Knowledge Ingestion Architecture** | `Phase09/01_Ingestion_Architecture.md` | Lines 30–52 (Connector protocol & 6-step FSM) |
| **Knowledge Organization & Taxonomy** | `Phase10/01_Knowledge_Organization_Architecture.md` | Lines 60–100 (Core domains, Graph DAG) |
| **RAG Runtime & Multi-Knowledge-Base** | `Phase11/01_RAG_Runtime.md` | Lines 35–130 (Router, Async indexer, Vector DB) |
| **Script Generation & JSON Payload** | `Phase12/01_Content_Generation_Architecture.md` | Lines 19–27, 108–141 (Script compiler schema) |
| **Media Production Platform & Manim** | `Phase13/01_Media_Production_Architecture.md` | Lines 18–28, 70–108 (Voice, Animation, FFmpeg) |
| **Idempotent Render Checkpointing** | `Phase13/04_Animation_Production.md` | Lines 132–135 (`RenderedScene` checksum) |
| **Resumable Upload & Last-mile Validation** | `Phase13/09_Publishing_Service.md` | Lines 21–25, 170–173 (Resumable upload & pre-validation) |

---
*Report compiled and verified by Explorer 2.*
