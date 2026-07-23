# 03_Interface_Contracts.md — Interface Contracts

This document defines the formal Python interface contracts for all modules in the Automated DSA Educational YouTube Video Pipeline. It strictly defines the boundaries, method signatures, and lifecycle expectations of each component.

---

## General Contract Principles

Before detailing individual modules, the following global principles apply to all interfaces:

- **Async behavior:** The entire pipeline is explicitly designed to be synchronous (`def` instead of `async def`), as per the architectural constraints (Section 17.2). Parallelism (e.g., NPU/CPU rendering) is handled at the Orchestrator/Threading layer, not via `asyncio`.
- **Communication between modules:** Modules **never** call each other directly. All communication is orchestrated sequentially by the Pipeline Orchestrator. Modules communicate exclusively by returning frozen dataclasses, which the Orchestrator then passes to the next module.
- **Dependency Injection:** Every module receives its dependencies (Configuration, Logger, and occasionally other utilities) exclusively via constructor injection (`__init__`).
- **Versioning & Backward compatibility:** Interfaces are implicitly v1. Backward compatibility is guaranteed by making new fields in output dataclasses optional (`| None`) and not mutating existing fields. If an interface signature must change, a v2 Protocol will be drafted.
- **Lifecycle (Initialization, Shutdown, Resource cleanup):**
  - **Initialization:** Happens exactly once in the composition root (`src/__main__.py`).
  - **Shutdown/Cleanup:** Modules do not have explicit `shutdown()` methods. Resources (HTTP clients, file handles, subprocesses) must be tightly scoped within the public method execution using context managers (`with ...:`).

---

## M1: LeetCode Scraper

```python
from typing import Protocol, runtime_checkable
import structlog
from src.core.config import ScraperConfig
from src.models.problem import ScrapedProblem
from src.core.exceptions import (
    ScraperError, 
    AuthenticationError, 
    ProblemNotFoundError, 
    RateLimitError
)

@runtime_checkable
class ScraperProtocol(Protocol):
    def scrape(self, slug: str) -> ScrapedProblem:
        ...
```

### Explanation & Contract Details
* **Public classes**: `ScraperProtocol`
* **Public methods**: `scrape`
* **Method signatures**: `def scrape(self, slug: str) -> ScrapedProblem:`
* **Return types**: `ScrapedProblem` (frozen dataclass containing parsed problem data).
* **Exceptions**: `AuthenticationError` (expired session), `ProblemNotFoundError` (invalid slug), `RateLimitError` (API limits hit), `ScraperError` (base scraping failure).
* **Async behavior**: Synchronous blocking HTTP call.
* **Lifecycle**: 
  * *Initialization*: `__init__` sets up config and logger.
  * *Cleanup*: The underlying HTTP client session (e.g., `httpx.Client`) must be opened and closed within the `scrape` method using a context manager.
* **Dependency Injection**: Requires `ScraperConfig` (containing session cookie and timeout settings) and a `logger`.
* **Communication**: Outputs `ScrapedProblem` which the Orchestrator passes to M2, M3, and M4.

---

## M2: Tag Explorer

```python
from typing import Protocol, runtime_checkable
import structlog
from src.core.config import TagsConfig
from src.models.problem import ScrapedProblem
from src.models.tags import TagKnowledge
from src.core.exceptions import TagExplorationError

@runtime_checkable
class TagExplorerProtocol(Protocol):
    def explore(self, problem: ScrapedProblem) -> TagKnowledge:
        ...
```

### Explanation & Contract Details
* **Public classes**: `TagExplorerProtocol`
* **Public methods**: `explore`
* **Method signatures**: `def explore(self, problem: ScrapedProblem) -> TagKnowledge:`
* **Return types**: `TagKnowledge` (frozen dataclass with enriched algorithm categorization).
* **Exceptions**: `TagExplorationError` (API timeout, LLM malformed response).
* **Async behavior**: Synchronous blocking LLM API call.
* **Lifecycle**: 
  * *Initialization*: `__init__` binds configuration.
  * *Cleanup*: Memory and temporary API connections are garbage collected post-execution.
* **Dependency Injection**: Requires `TagsConfig` (containing Gemini API settings) and a `logger`.
* **Communication**: Receives `ScrapedProblem` from M1. Outputs `TagKnowledge` to M3 and M4.

---

## M3: RAG Engine

```python
from typing import Protocol, runtime_checkable
import structlog
from src.core.config import RAGConfig
from src.models.problem import ScrapedProblem
from src.models.tags import TagKnowledge
from src.models.rag import RAGContext
from src.core.exceptions import RAGError, IndexNotFoundError, EmbeddingError

@runtime_checkable
class RAGEngineProtocol(Protocol):
    def retrieve(self, problem: ScrapedProblem, tags: TagKnowledge) -> RAGContext:
        ...

    def index_knowledge_base(self) -> int:
        ...
```

### Explanation & Contract Details
* **Public classes**: `RAGEngineProtocol`
* **Public methods**: `retrieve`, `index_knowledge_base`
* **Method signatures**: 
  * `def retrieve(self, problem: ScrapedProblem, tags: TagKnowledge) -> RAGContext:`
  * `def index_knowledge_base(self) -> int:`
* **Return types**: `RAGContext` (contains retrieved markdown chunks), `int` (number of indexed chunks).
* **Exceptions**: `IndexNotFoundError` (ChromaDB index missing), `EmbeddingError` (Gemini embedding failure), `RAGError` (general retrieval failure).
* **Async behavior**: Synchronous execution.
* **Lifecycle**: 
  * *Initialization*: `__init__` binds config. Connection to local ChromaDB is established.
  * *Cleanup*: Persistent ChromaDB client handles its own shutdown. File handles during `index_knowledge_base` are scoped.
* **Dependency Injection**: Requires `RAGConfig` (ChromaDB paths, chunk sizes) and a `logger`.
* **Communication**: Receives `ScrapedProblem` and `TagKnowledge`. Outputs `RAGContext` to M4.

---

## M4: Script Generator

```python
from typing import Protocol, runtime_checkable
import structlog
from src.core.config import ScriptConfig
from src.models.problem import ScrapedProblem
from src.models.tags import TagKnowledge
from src.models.rag import RAGContext
from src.models.memory import MemoryRecord
from src.models.script import VideoScript
from src.core.exceptions import ScriptGenerationError, SchemaValidationError, ContentFilterError

@runtime_checkable
class ScriptGeneratorProtocol(Protocol):
    def generate(
        self, 
        problem: ScrapedProblem, 
        tags: TagKnowledge, 
        rag_context: RAGContext, 
        memory: MemoryRecord | None = None
    ) -> VideoScript:
        ...
```

### Explanation & Contract Details
* **Public classes**: `ScriptGeneratorProtocol`
* **Public methods**: `generate`
* **Method signatures**: See above.
* **Return types**: `VideoScript` (contains 10 specific narrative sections and visual params).
* **Exceptions**: `SchemaValidationError` (LLM output doesn't match JSON structure), `ContentFilterError` (safety trip), `ScriptGenerationError`.
* **Async behavior**: Synchronous blocking LLM text generation.
* **Lifecycle**: 
  * *Initialization*: Standard config and logger binding.
  * *Cleanup*: N/A. Pure compute/API bound.
* **Dependency Injection**: Requires `ScriptConfig` (model parameters, context windows).
* **Communication**: Aggregates outputs from M1, M2, M3, and M9. Outputs `VideoScript` to M5, M6, M7, M8.

---

## M5: Voice Engine

```python
from typing import Protocol, runtime_checkable
import structlog
from src.core.config import VoiceConfig
from src.models.script import VideoScript
from src.models.voice import VoiceResult
from src.core.exceptions import VoiceSynthesisError, ModelLoadError, AudioExportError

@runtime_checkable
class VoiceSynthesizerProtocol(Protocol):
    def synthesize(self, script: VideoScript) -> VoiceResult:
        ...
```

### Explanation & Contract Details
* **Public classes**: `VoiceSynthesizerProtocol`
* **Public methods**: `synthesize`
* **Method signatures**: `def synthesize(self, script: VideoScript) -> VoiceResult:`
* **Return types**: `VoiceResult` (contains paths to 10 `.wav` files).
* **Exceptions**: `ModelLoadError` (OpenVINO model not found), `AudioExportError` (disk write failure).
* **Async behavior**: Synchronous blocking inference.
* **Lifecycle**: 
  * *Initialization*: `__init__` should eagerly load the OpenVINO model into memory to ensure fail-fast behavior if the NPU is unavailable.
  * *Cleanup*: Model memory is released when the process terminates. File handles for `.wav` exports are scoped.
* **Dependency Injection**: Requires `VoiceConfig` (model path, reference audio).
* **Communication**: Receives `VideoScript` from M4. Outputs `VoiceResult` to M6 and M7.

---

## M6: Manim Animation

```python
from typing import Protocol, runtime_checkable
import structlog
from src.core.config import AnimationConfig
from src.models.script import VideoScript
from src.models.voice import VoiceResult
from src.models.animation import AnimationResult
from src.core.exceptions import AnimationRenderError, SceneConfigError

@runtime_checkable
class AnimationRendererProtocol(Protocol):
    def render(self, script: VideoScript, voice: VoiceResult) -> AnimationResult:
        ...
```

### Explanation & Contract Details
* **Public classes**: `AnimationRendererProtocol`
* **Public methods**: `render`
* **Method signatures**: `def render(self, script: VideoScript, voice: VoiceResult) -> AnimationResult:`
* **Return types**: `AnimationResult` (contains paths to 10 `.mp4` files).
* **Exceptions**: `SceneConfigError` (invalid visual parameters from script), `AnimationRenderError` (Manim crash).
* **Async behavior**: Synchronous blocking render.
* **Lifecycle**: 
  * *Initialization*: Binds configuration.
  * *Cleanup*: **Critical**: Manim scenes must be rendered in isolated subprocesses or strictly cleaned up to prevent memory leaks and GL context exhaustion between sections.
* **Dependency Injection**: Requires `AnimationConfig` (resolution, FPS, theme).
* **Communication**: Receives `VideoScript` (M4) and `VoiceResult` (M5) to match durations. Outputs `AnimationResult` to M7.

---

## M7: Video Assembler

```python
from typing import Protocol, runtime_checkable
import structlog
from src.core.config import AssemblyConfig
from src.models.voice import VoiceResult
from src.models.animation import AnimationResult
from src.models.script import VideoScript
from src.models.assembly import AssembledVideo
from src.core.exceptions import AssemblyError, FFmpegNotFoundError, MuxingError

@runtime_checkable
class VideoAssemblerProtocol(Protocol):
    def assemble(
        self, 
        voice: VoiceResult, 
        animation: AnimationResult, 
        script: VideoScript
    ) -> AssembledVideo:
        ...
```

### Explanation & Contract Details
* **Public classes**: `VideoAssemblerProtocol`
* **Public methods**: `assemble`
* **Method signatures**: See above.
* **Return types**: `AssembledVideo` (path to final `.mp4` and thumbnail).
* **Exceptions**: `FFmpegNotFoundError` (binary missing), `MuxingError` (ffmpeg subprocess failed).
* **Async behavior**: Synchronous execution of subprocesses.
* **Lifecycle**: 
  * *Initialization*: Verifies FFmpeg exists on the system PATH.
  * *Cleanup*: Subprocesses must be managed safely using `subprocess.run(..., check=True)`. Temporary files (like concat lists) must be deleted using `tempfile` context managers.
* **Dependency Injection**: Requires `AssemblyConfig` (codec, bitrate, target loudness).
* **Communication**: Receives output from M4, M5, and M6. Outputs `AssembledVideo` to M8.

---

## M8: YouTube Upload

```python
from typing import Protocol, runtime_checkable
import structlog
from src.core.config import YouTubeConfig
from src.models.assembly import AssembledVideo
from src.models.script import SEOMetadata
from src.models.youtube import UploadResult
from src.core.exceptions import YouTubeUploadError, QuotaExceededError, AuthTokenExpiredError

@runtime_checkable
class YouTubeUploaderProtocol(Protocol):
    def upload(self, video: AssembledVideo, metadata: SEOMetadata) -> UploadResult:
        ...
```

### Explanation & Contract Details
* **Public classes**: `YouTubeUploaderProtocol`
* **Public methods**: `upload`
* **Method signatures**: `def upload(self, video: AssembledVideo, metadata: SEOMetadata) -> UploadResult:`
* **Return types**: `UploadResult` (contains YouTube URL and Video ID).
* **Exceptions**: `QuotaExceededError` (daily limit hit), `AuthTokenExpiredError` (OAuth failure), `YouTubeUploadError` (network/upload failure).
* **Async behavior**: Synchronous blocking resumable upload.
* **Lifecycle**: 
  * *Initialization*: Checks for valid OAuth tokens in local storage.
  * *Cleanup*: Network sockets are closed upon completion.
* **Dependency Injection**: Requires `YouTubeConfig` (OAuth secret paths, category settings).
* **Communication**: Receives `AssembledVideo` (M7) and `SEOMetadata` (extracted from M4). Outputs `UploadResult` to M9.

---

## M9: Memory System

```python
from typing import Protocol, runtime_checkable
import structlog
from src.core.config import MemoryConfig
from src.models.memory import MemoryRecord
from src.core.exceptions import MemoryError, CorruptedStoreError

@runtime_checkable
class MemoryStoreProtocol(Protocol):
    def save(self, record: MemoryRecord) -> None:
        ...

    def has_been_generated(self, slug: str) -> bool:
        ...

    def get_record(self, slug: str) -> MemoryRecord | None:
        ...

    def get_all_tags(self) -> set[str]:
        ...

    def get_failed_runs(self) -> list[MemoryRecord]:
        ...
```

### Explanation & Contract Details
* **Public classes**: `MemoryStoreProtocol`
* **Public methods**: `save`, `has_been_generated`, `get_record`, `get_all_tags`, `get_failed_runs`
* **Method signatures**: See above.
* **Return types**: Various scalar/collection types and `MemoryRecord` instances.
* **Exceptions**: `CorruptedStoreError` (JSON is malformed).
* **Async behavior**: Synchronous file I/O.
* **Lifecycle**: 
  * *Initialization*: Ensures the memory file exists, creates if missing.
  * *Cleanup*: Implements POSIX file locking during the `save()` operation to prevent race conditions. File is opened, read/modified, and safely closed in a single transaction.
* **Dependency Injection**: Requires global configuration and logger.
* **Communication**: Analyzed by Orchestrator at startup. Receives aggregated pipeline results at the end of the run.
