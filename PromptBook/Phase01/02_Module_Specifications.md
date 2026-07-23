# 02_Module_Specifications.md — Formal Module Specifications

This document defines the formal specification for all nine modules of the Automated DSA Educational YouTube Video Pipeline. It serves as the implementation blueprint for each component.

---

## M1: LeetCode Scraper (`src/scraper/`)

### Purpose
Extract complete problem metadata and the user's accepted C++ solution from LeetCode via its GraphQL API.

### Responsibilities
1. Parse problem URL/slug into a canonical slug.
2. Query LeetCode's GraphQL API with session authentication.
3. Normalize text (HTML to Markdown) and clean encodings.
4. Extract title, difficulty, description, constraints, examples, tags, and accepted code.
5. Manage API rate limiting and handle session expiration gracefully.

### Inputs
- `slug` (string)

### Outputs
- `ScrapedProblem` (frozen dataclass)
  - Saved to: `data/scraped/{slug}.json`

### Dependencies
- **External**: `httpx`, LeetCode GraphQL API
- **Internal**: `src/models/problem.py`, `src/core/exceptions.py`, `src/core/retry.py`

### Configuration
- `rate_limit_seconds`: 2.0 (delay between requests)
- `timeout_seconds`: 30
- `max_retries`: 3

### Error Cases
- `AuthenticationError`: Raised when the session cookie is expired or invalid.
- `ProblemNotFoundError`: Raised if the slug does not exist on LeetCode.
- `RateLimitError`: Raised on HTTP 429 after retries are exhausted.

### Performance Requirements
- Must obey the configured `rate_limit_seconds` to avoid IP blocking.

### Expected Runtime
- 2-5 seconds (network bound).

### Caching
- File-based cache at `data/scraped/{slug}.json`. Hit bypasses all HTTP calls.

### Public API
- `def scrape(self, slug: str) -> ScrapedProblem:`

### Internal Components
- `LeetCodeClient`: Low-level HTTP transport and GraphQL query execution.
- `ResponseParser`: Converts raw GraphQL JSON responses into the `ScrapedProblem` dataclass.

### Future Extensions
- Support for other platforms via new scrapers (e.g., `HackerRankScraper`).
- Batch slug resolution to map problem numbers to slugs.

### Testing Strategy
- **Unit**: Mock `httpx` responses to test 401, 404, 429, and malformed JSON.
- **Integration**: One `@pytest.mark.slow` test performing a live scrape of `two-sum`.

---

## M2: Tag Explorer (`src/tags/`)

### Purpose
Enrich raw LeetCode tags with deep algorithmic knowledge, pattern families, and pedagogical prerequisites.

### Responsibilities
1. Group raw tags into a primary pattern family.
2. Identify prerequisite concepts for the problem.
3. Suggest related problems sorted by difficulty progression.
4. Classify the best visual animation style for Manim.

### Inputs
- `problem` (`ScrapedProblem`)

### Outputs
- `TagKnowledge` (frozen dataclass)
  - Saved to: `data/tags/{slug}_tags.json`

### Dependencies
- **External**: `google-genai` (Gemini API)
- **Internal**: `src/models/tags.py`, `src/core/exceptions.py`

### Configuration
- `gemini_model`: "gemini-2.5-flash"
- `temperature`: 0.3 (low variance)
- `max_output_tokens`: 4096

### Error Cases
- `TagExplorationError`: Raised if the Gemini API fails, times out, or returns a malformed response.

### Performance Requirements
- Low latency response parsing; prompt sizing should be minimal to reduce token processing time.

### Expected Runtime
- 3-8 seconds (LLM API bound).

### Caching
- File-based cache at `data/tags/{slug}_tags.json`.

### Public API
- `def explore(self, problem: ScrapedProblem) -> TagKnowledge:`

### Internal Components
- `patterns.py`: Constants mapping raw tags to `PATTERN_FAMILIES` and `ANIMATION_STYLE_MAP`.

### Future Extensions
- Support for local LLMs for tag exploration.
- Tag taxonomy visualization tool.

### Testing Strategy
- **Unit**: Mock Gemini API to simulate valid responses, unknown tags, and timeouts.

---

## M3: RAG Engine (`src/rag/`)

### Purpose
Retrieve pedagogically relevant context from a local knowledge base to ground script generation in factually accurate explanations.

### Responsibilities
1. Manage indexing of Markdown documents in `data/knowledge_base/`.
2. Chunk documents based on topics and headings.
3. Generate embeddings using Gemini and upsert them into ChromaDB.
4. Retrieve and rank relevant chunks for a specific problem and its tags.

### Inputs
- `problem` (`ScrapedProblem`)
- `tags` (`TagKnowledge`)

### Outputs
- `RAGContext` (frozen dataclass containing retrieved chunks)
  - Saved to: `data/rag/{slug}_context.json`

### Dependencies
- **External**: `chromadb`, `google-genai` (embeddings)
- **Internal**: `src/models/rag.py`, `src/core/exceptions.py`

### Configuration
- `embedding_model`: "text-embedding-004"
- `collection_name`: "dsa_knowledge"
- `chunk_size`: 512
- `chunk_overlap`: 64
- `top_k`: 8
- `chroma_persist_dir`: "data/vector_store/chroma"

### Error Cases
- `IndexNotFoundError`: Raised if retrieval is attempted before the index is built.
- `EmbeddingError`: Raised if the Gemini API fails during embedding generation.

### Performance Requirements
- Retrieval query must execute in <3 seconds.
- Incremental indexing must skip unchanged files.

### Expected Runtime
- Retrieval: 1-3 seconds.
- Initial Indexing: ~1-2 minutes depending on corpus size.

### Caching
- File-based cache at `data/rag/{slug}_context.json` for the retrieval step.

### Public API
- `def retrieve(self, problem: ScrapedProblem, tags: TagKnowledge) -> RAGContext:`
- `def index_knowledge_base(self) -> int:`

### Internal Components
- `TopicAwareChunker`: Splits Markdown files by heading boundaries.
- `GeminiEmbedder`: Handles embedding batches with rate limiting.
- `KnowledgeBaseIndexer`: Orchestrates indexing workflow.

### Future Extensions
- Cross-encoder based re-ranking.
- Hybrid search combining BM25 and vector search.

### Testing Strategy
- **Unit**: Test chunker with complex markdown, mock ChromaDB for retrieval, test missing index handling.

---

## M4: Script Generator (`src/script/`)

### Purpose
Synthesize a structured, narration-ready 10-section JSON video script from the aggregated problem data.

### Responsibilities
1. Construct complex composite prompts from problem metadata, tags, and RAG context.
2. Query Gemini to generate a script adhering strictly to a JSON schema.
3. Validate the JSON schema and ensure all 10 sections are present.
4. Generate YouTube SEO metadata.

### Inputs
- `problem` (`ScrapedProblem`)
- `tags` (`TagKnowledge`)
- `rag_context` (`RAGContext`)
- `memory` (`MemoryRecord` | `None`)

### Outputs
- `VideoScript` (frozen dataclass)
  - Saved to: `data/scripts/{slug}_script.json`

### Dependencies
- **External**: `google-genai` (Gemini API)
- **Internal**: `src/models/script.py`, `src/core/exceptions.py`

### Configuration
- `gemini_model`: "gemini-2.5-flash"
- `temperature`: 0.7 (higher for conversational narration)
- `max_output_tokens`: 16384
- `sections_count`: 10

### Error Cases
- `SchemaValidationError`: Raised if the output does not strictly match the 10-section format.
- `ContentFilterError`: Raised if the LLM output triggers safety filters.

### Performance Requirements
- Handle large context windows up to 32k tokens efficiently.

### Expected Runtime
- 10-30 seconds (LLM API bound).

### Caching
- File-based cache at `data/scripts/{slug}_script.json`.

### Public API
- `def generate(self, problem: ScrapedProblem, tags: TagKnowledge, rag_context: RAGContext, memory: MemoryRecord | None = None) -> VideoScript:`

### Internal Components
- `prompts.py`: Template engine and schema definitions.
- `ScriptValidator`: Enforces JSON structure and section ordering.

### Future Extensions
- Local LLM fallback.
- Generation of multiple A/B test scripts.

### Testing Strategy
- **Unit**: Test validator with valid/invalid structures; mock Gemini to simulate JSON parse failures.

---

## M5: Voice Engine (`src/voice/`)

### Purpose
Convert script narration text into high-quality speech audio using the local Kokoro-82M TTS model via OpenVINO.

### Responsibilities
1. Load OpenVINO model (CPU/NPU) and speaker embeddings.
2. Synthesize audio section-by-section.
3. Export WAV files at 24kHz.
4. Generate a timing manifest mapping section IDs to exact audio durations.

### Inputs
- `script` (`VideoScript`)

### Outputs
- `VoiceResult` (frozen dataclass)
  - Saves 10 `.wav` files and `manifest.json` to `data/voice/{slug}/`

### Dependencies
- **External**: `openvino`, Kokoro-82M model files.
- **Internal**: `src/models/voice.py`, `src/core/exceptions.py`

### Configuration
- `model_path`: "models/kokoro-82m-openvino"
- `reference_audio`: "voice_samples/reference.wav"
- `sample_rate`: 24000
- `speed`: 1.0

### Error Cases
- `ModelLoadError`: Raised if OpenVINO models are missing or NPU initialization fails.
- `AudioExportError`: Raised on filesystem write failure.

### Performance Requirements
- Target <3 minutes total synthesis time on NPU/CPU.
- Manage memory to prevent OOM across 10 sections.

### Expected Runtime
- 60-180 seconds (compute bound).

### Caching
- Checked via existence of `data/voice/{slug}/manifest.json`.

### Public API
- `def synthesize(self, script: VideoScript) -> VoiceResult:`

### Internal Components
- `audio_utils.py`: Helpers for silence trimming and duration calculations.

### Future Extensions
- Support for multiple languages.
- Integration of alternative TTS models (e.g., Coqui, ElevenLabs).

### Testing Strategy
- **Unit**: Mock model inference to test loop and file creation; validate manifest math.

---

## M6: Manim Animation (`src/animation/`)

### Purpose
Render programmatic algorithmic animations using Manim, synced perfectly to the generated voice durations.

### Responsibilities
1. Select appropriate Manim scenes based on `AnimationStyle`.
2. Construct scenes dynamically based on `visual_params`.
3. Render frames into MP4 files using Manim's FFmpeg backend.
4. Force scene duration to match the corresponding audio duration.

### Inputs
- `script` (`VideoScript`)
- `voice` (`VoiceResult`)

### Outputs
- `AnimationResult` (frozen dataclass)
  - Saves 10 `.mp4` files to `data/animation/{slug}/`

### Dependencies
- **External**: `manim`
- **Internal**: `src/models/animation.py`, `src/core/exceptions.py`

### Configuration
- `resolution`: "1920x1080"
- `fps`: 30
- `background_color`: "#0f0f23"
- `quality`: "production_quality"

### Error Cases
- `SceneConfigError`: Raised when `visual_params` contain invalid structures preventing render.
- `AnimationRenderError`: Base error for Manim subprocess failures.

### Performance Requirements
- Scene renders must isolate memory (e.g., via subprocesses) to prevent leaks.
- Leverage GPU acceleration if supported by Manim.

### Expected Runtime
- 120-300 seconds (heavily compute bound).

### Caching
- Caches per section. Checks existence of 10 MP4s in `data/animation/{slug}/`.

### Public API
- `def render(self, script: VideoScript, voice: VoiceResult) -> AnimationResult:`

### Internal Components
- `theme.py`: Shared styles, colors, and fonts.
- `scenes/*.py`: Concrete implementations (`ArrayScene`, `CodeScene`, `ComplexityScene`).

### Future Extensions
- Real-time web preview streaming.
- Additional data structures (Heaps, Tries).

### Testing Strategy
- **Unit**: Instantiate scenes directly to verify no exceptions are raised during setup; mock Manim render call.

---

## M7: Video Assembler (`src/assembly/`)

### Purpose
Stitch voice audio and Manim video clips into a single, polished YouTube-ready video file using FFmpeg.

### Responsibilities
1. Ensure frame-accurate muxing of corresponding `.wav` and `.mp4` files.
2. Concatenate all 10 sections in script order.
3. Normalize audio loudness to -14 LUFS (YouTube standard).
4. Apply fade-in and fade-out effects.
5. Extract a thumbnail keyframe.

### Inputs
- `voice` (`VoiceResult`)
- `animation` (`AnimationResult`)
- `script` (`VideoScript` for SEO/metadata)

### Outputs
- `AssembledVideo` (frozen dataclass)
  - Saves: `data/output/{slug}/final.mp4` and `thumbnail.png`

### Dependencies
- **External**: `ffmpeg` (system binary)
- **Internal**: `src/models/assembly.py`, `src/core/exceptions.py`

### Configuration
- `video_codec`: "libx264"
- `audio_codec`: "aac"
- `crf`: 18
- `audio_bitrate`: "192k"
- `loudness_target`: -14

### Error Cases
- `FFmpegNotFoundError`: Raised if the system binary is missing.
- `MuxingError`: Raised if concat or filters fail due to corrupted inputs.

### Performance Requirements
- Leverage hardware acceleration (e.g., Intel QSV `-c:v h264_qsv`) where possible.

### Expected Runtime
- 30-60 seconds (I/O and light compute bound).

### Caching
- File-based cache at `data/output/{slug}/final.mp4`.

### Public API
- `def assemble(self, voice: VoiceResult, animation: AnimationResult, script: VideoScript) -> AssembledVideo:`

### Internal Components
- `ffmpeg_commands.py`: Pure functions to build complex FFmpeg filter graphs and subprocess commands.

### Future Extensions
- Addition of background music mixing.
- Soft subtitle track embedding.

### Testing Strategy
- **Unit**: Validate exact string matches for generated FFmpeg commands.
- **Integration**: Assemble tiny 1-second mocked audio/video files.

---

## M8: YouTube Upload (`src/youtube/`)

### Purpose
Upload the final assembled video to YouTube with metadata and thumbnails via the YouTube Data API v3.

### Responsibilities
1. Authenticate via OAuth 2.0 and manage token refreshes.
2. Upload the MP4 payload using a resumable upload protocol.
3. Apply title, description (with chapters), tags, category, and privacy status.
4. Upload and set the custom thumbnail.

### Inputs
- `video` (`AssembledVideo`)
- `metadata` (`SEOMetadata` from script)

### Outputs
- `UploadResult` (frozen dataclass)
  - Saved to: `data/uploads/{slug}_upload.json`

### Dependencies
- **External**: `google-api-python-client`, `google-auth-oauthlib`
- **Internal**: `src/models/youtube.py`, `src/core/exceptions.py`

### Configuration
- `category_id`: 27 (Education)
- `default_language`: "en"
- `client_secrets_path`: "config/client_secrets.json"

### Error Cases
- `AuthTokenExpiredError`: Raised if token refresh completely fails.
- `QuotaExceededError`: Raised if the YouTube daily limit (10,000 units) is hit.

### Performance Requirements
- Must resume cleanly on transient network drops.

### Expected Runtime
- 30-120 seconds (Network bandwidth bound).

### Caching
- Checked via `data/uploads/{slug}_upload.json`.

### Public API
- `def upload(self, video: AssembledVideo, metadata: SEOMetadata) -> UploadResult:`

### Internal Components
- `OAuthManager`: Manages token persistence and authorization flows.

### Future Extensions
- Multi-platform uploads (e.g., TikTok, Instagram Reels) by abstracting an `UploaderProtocol`.

### Testing Strategy
- **Unit**: Mock YouTube API client to simulate successful uploads, quota drops, and token refreshes.

---

## M9: Memory System (`src/memory/`)

### Purpose
Maintain a persistent JSON record of all generated videos for deduplication, analytics, and cross-video consistency.

### Responsibilities
1. Save `MemoryRecord` post-pipeline run.
2. Provide quick deduplication checks (`has_been_generated`).
3. Query historical records and failed runs.
4. Expose a unified tagging taxonomy based on past generations.

### Inputs
- All previously generated dataclass results.

### Outputs
- `MemoryRecord`
  - Saved to/Read from: `data/memory/memory.json`

### Dependencies
- **External**: None.
- **Internal**: `src/models/memory.py`, `src/core/exceptions.py`

### Configuration
- N/A

### Error Cases
- `CorruptedStoreError`: Raised if `memory.json` is malformed JSON.

### Performance Requirements
- Must implement file locking to prevent race conditions during concurrent batch runs.

### Expected Runtime
- <1 second (I/O bound).

### Caching
- N/A.

### Public API
- `def save(self, record: MemoryRecord) -> None:`
- `def has_been_generated(self, slug: str) -> bool:`
- `def get_record(self, slug: str) -> MemoryRecord | None:`
- `def get_all_tags(self) -> set[str]:`
- `def get_failed_runs(self) -> list[MemoryRecord]:`

### Internal Components
- N/A (single cohesive store module).

### Future Extensions
- Migration to SQLite (`SQLiteMemoryStore`) when records exceed a few thousand.
- Integration of YouTube view metrics to track video performance over time.

### Testing Strategy
- **Unit**: File system mocking to test CRUD operations, locking, and graceful JSON corruption handling.
