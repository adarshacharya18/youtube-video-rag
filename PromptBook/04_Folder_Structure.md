# 04_Folder_Structure.md — Complete Directory Specification

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Target Environment:** Intel Core Ultra 7 155H · Ubuntu 25.10 LTS · Python 3.12 · Intel Arc GPU  
**Document Version:** 1.0.0  
**Last Updated:** July 2026  
**Status:** Canonical — All directories MUST conform to this specification.

---

## Table of Contents

1. [Complete Folder Tree](#1-complete-folder-tree)
2. [Project Root](#2-project-root)
3. [Source Code — `src/`](#3-source-code--src)
4. [Domain Models — `src/models/`](#4-domain-models--srcmodels)
5. [Shared Infrastructure — `src/core/`](#5-shared-infrastructure--srccore)
6. [Module 1: Problem Scraper — `src/scraper/`](#6-module-1-problem-scraper--srcscraper)
7. [Module 2: Tag Explorer — `src/tags/`](#7-module-2-tag-explorer--srctags)
8. [Module 3: RAG Knowledge Engine — `src/rag/`](#8-module-3-rag-knowledge-engine--srcrag)
9. [Module 4: Script Generator — `src/script/`](#9-module-4-script-generator--srcscript)
10. [Module 5: Voice Generation — `src/voice/`](#10-module-5-voice-generation--srcvoice)
11. [Module 6: Manim Animation Engine — `src/animation/`](#11-module-6-manim-animation-engine--srcanimation)
12. [Module 7: Video Assembly — `src/assembly/`](#12-module-7-video-assembly--srcassembly)
13. [Module 8: YouTube Upload — `src/youtube/`](#13-module-8-youtube-upload--srcyoutube)
14. [Module 9: Memory System — `src/memory/`](#14-module-9-memory-system--srcmemory)
15. [Module 0: Pipeline Orchestrator — `src/orchestrator/`](#15-module-0-pipeline-orchestrator--srcorchestrator)
16. [Tests — `tests/`](#16-tests--tests)
17. [Configuration — `config/`](#17-configuration--config)
18. [Runtime Data — `data/`](#18-runtime-data--data)
19. [Knowledge Base — `data/knowledge_base/`](#19-knowledge-base--dataknowledge_base)
20. [Voice Samples — `voice_samples/`](#20-voice-samples--voice_samples)
21. [Models — `models/`](#21-models--models)
22. [PromptBook — `PromptBook/`](#22-promptbook--promptbook)
23. [Scripts — `scripts/`](#23-scripts--scripts)
24. [Logs — `logs/`](#24-logs--logs)
25. [Git Version Control Rules](#25-git-version-control-rules)
26. [Directory Rules Summary](#26-directory-rules-summary)

---

## 1. Complete Folder Tree

```
Youtube-Channel/
│
│   ── Project Root ──────────────────────────────────────────────────
│
├── .env                                 # Secrets (API keys, cookies)
├── .env.example                         # Template .env for onboarding
├── .gitignore                           # Git exclusion rules
├── pyproject.toml                       # Project metadata, deps, tool config
├── README.md                            # Project overview and quick start
├── reference.wav                        # Legacy voice reference (→ voice_samples/)
│
│   ── Source Code ───────────────────────────────────────────────────
│
├── src/
│   ├── __init__.py                      # Package marker
│   ├── __main__.py                      # CLI entry point + composition root
│   │
│   ├── models/                          # Layer 1: Domain models (true leaf)
│   │   ├── __init__.py                  # Re-exports all public dataclasses
│   │   ├── enums.py                     # Difficulty, SectionType, PipelineStatus, AnimationStyle
│   │   ├── problem.py                   # ScrapedProblem, Example
│   │   ├── tags.py                      # TagKnowledge, RelatedProblem
│   │   ├── rag.py                       # RAGContext, RetrievedChunk
│   │   ├── script.py                    # VideoScript, ScriptSection, SEOMetadata
│   │   ├── visual_params.py             # VisualParams union (Array, Tree, Code, etc.)
│   │   ├── voice.py                     # VoiceResult, SectionAudio
│   │   ├── animation.py                 # AnimationResult, SectionClip
│   │   ├── assembly.py                  # AssembledVideo
│   │   ├── youtube.py                   # UploadResult
│   │   ├── memory.py                    # MemoryRecord
│   │   ├── pipeline.py                  # PipelineResult
│   │   └── protocols.py                 # All Protocol interfaces
│   │
│   ├── core/                            # Layer 2: Shared infrastructure (near-leaf, depends on models/)
│   │   ├── __init__.py                  # Re-exports key utilities
│   │   ├── config.py                    # PipelineConfig, load_config(), sub-configs
│   │   ├── logger.py                    # get_logger(), structlog setup
│   │   ├── serialization.py             # serialize(), deserialize(), JSON codecs
│   │   ├── cache.py                     # FileCache — check/put/invalidate
│   │   ├── exceptions.py               # PipelineError hierarchy
│   │   ├── retry.py                     # @retry decorator with exponential backoff
│   │   └── paths.py                     # PROJECT_ROOT, resolve_path(), ensure_dir()
│   │
│   ├── scraper/                         # Module 1: LeetCode Problem Scraper
│   │   ├── __init__.py                  # Exports LeetCodeScraper
│   │   ├── scraper.py                   # LeetCodeScraper (ScraperProtocol)
│   │   ├── client.py                    # LeetCodeClient — HTTP/GraphQL transport
│   │   └── parser.py                    # ResponseParser — GraphQL → dataclass
│   │
│   ├── tags/                            # Module 2: Tag Explorer
│   │   ├── __init__.py                  # Exports GeminiTagExplorer
│   │   ├── explorer.py                  # GeminiTagExplorer (TagExplorerProtocol)
│   │   └── patterns.py                  # Pattern family mappings, constants
│   │
│   ├── rag/                             # Module 3: RAG Knowledge Engine
│   │   ├── __init__.py                  # Exports ChromaRAGEngine
│   │   ├── engine.py                    # ChromaRAGEngine (RAGEngineProtocol)
│   │   ├── chunker.py                   # TopicAwareChunker — document splitting
│   │   ├── embedder.py                  # GeminiEmbedder — embedding wrapper
│   │   └── indexer.py                   # KnowledgeBaseIndexer — build/update index
│   │
│   ├── script/                          # Module 4: Script Generator
│   │   ├── __init__.py                  # Exports GeminiScriptGenerator
│   │   ├── generator.py                 # GeminiScriptGenerator (ScriptGeneratorProtocol)
│   │   ├── prompts.py                   # Prompt templates for script generation
│   │   └── validator.py                 # ScriptValidator — JSON schema validation
│   │
│   ├── voice/                           # Module 5: Voice Generation
│   │   ├── __init__.py                  # Exports KokoroVoiceSynthesizer
│   │   ├── synthesizer.py               # KokoroVoiceSynthesizer (VoiceSynthesizerProtocol)
│   │   └── audio_utils.py               # Audio processing helpers (normalization, format)
│   │
│   ├── animation/                       # Module 6: Manim Animation Engine
│   │   ├── __init__.py                  # Exports ManimAnimationRenderer
│   │   ├── renderer.py                  # ManimAnimationRenderer (AnimationRendererProtocol)
│   │   ├── theme.py                     # Visual theme constants (colors, fonts, sizes)
│   │   └── scenes/                      # Reusable Manim scene templates
│   │       ├── __init__.py              # Exports all scene classes
│   │       ├── base_scene.py            # DSABaseScene — dark theme, layout
│   │       ├── array_scene.py           # ArrayScene — traversal, swaps, highlights
│   │       ├── linkedlist_scene.py      # LinkedListScene — node ops, pointer movement
│   │       ├── tree_scene.py            # TreeScene — BFS/DFS, level coloring
│   │       ├── graph_scene.py           # GraphScene — edge traversal, visited sets
│   │       ├── hashmap_scene.py         # HashMapScene — bucket visualization
│   │       ├── stack_queue_scene.py     # StackQueueScene — push/pop/enqueue/dequeue
│   │       ├── code_scene.py            # CodeScene — syntax-highlighted walkthrough
│   │       └── complexity_scene.py      # ComplexityScene — Big-O charts
│   │
│   ├── assembly/                        # Module 7: Video Assembly
│   │   ├── __init__.py                  # Exports FFmpegVideoAssembler
│   │   ├── assembler.py                 # FFmpegVideoAssembler (VideoAssemblerProtocol)
│   │   └── ffmpeg_commands.py           # FFmpeg command builders (mux, concat, normalize)
│   │
│   ├── youtube/                         # Module 8: YouTube Upload
│   │   ├── __init__.py                  # Exports YouTubeAPIUploader
│   │   ├── uploader.py                  # YouTubeAPIUploader (YouTubeUploaderProtocol)
│   │   └── auth.py                      # OAuthManager — token persistence, refresh
│   │
│   ├── memory/                          # Module 9: Memory System
│   │   ├── __init__.py                  # Exports JSONMemoryStore
│   │   └── store.py                     # JSONMemoryStore (MemoryStoreProtocol)
│   │
│   └── orchestrator/                    # Module 0: Pipeline Orchestrator
│       ├── __init__.py                  # Exports PipelineOrchestrator
│       ├── pipeline.py                  # PipelineOrchestrator — main coordinator
│       └── checkpoint.py                # CheckpointManager — save/load/resume
│
│   ── Tests ─────────────────────────────────────────────────────────
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Global fixtures, factories
│   ├── test_models/                     # Tests for src/models/
│   │   ├── __init__.py
│   │   ├── test_problem.py
│   │   ├── test_script.py
│   │   └── test_enums.py
│   ├── test_core/                       # Tests for src/core/
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_serialization.py
│   │   ├── test_cache.py
│   │   ├── test_retry.py
│   │   └── test_paths.py
│   ├── test_scraper/                    # Tests for src/scraper/
│   │   ├── __init__.py
│   │   ├── conftest.py                  # Module-specific fixtures
│   │   ├── test_scraper.py
│   │   ├── test_client.py
│   │   └── test_parser.py
│   ├── test_tags/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   └── test_explorer.py
│   ├── test_rag/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_engine.py
│   │   ├── test_chunker.py
│   │   └── test_indexer.py
│   ├── test_script/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_generator.py
│   │   └── test_validator.py
│   ├── test_voice/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   └── test_synthesizer.py
│   ├── test_animation/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_renderer.py
│   │   └── test_scenes/
│   │       ├── __init__.py
│   │       ├── test_array_scene.py
│   │       └── test_code_scene.py
│   ├── test_assembly/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_assembler.py
│   │   └── test_ffmpeg_commands.py
│   ├── test_youtube/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_uploader.py
│   │   └── test_auth.py
│   ├── test_memory/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   └── test_store.py
│   └── test_orchestrator/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_pipeline.py
│       ├── test_pipeline_e2e.py         # End-to-end with all fakes
│       └── test_checkpoint.py
│
│   ── Configuration ─────────────────────────────────────────────────
│
├── config/
│   ├── pipeline.yaml                    # Pipeline runtime configuration
│   ├── logging.yaml                     # Logging handler configuration
│   └── client_secrets.json              # YouTube OAuth credentials (gitignored)
│
│   ── Runtime Data ──────────────────────────────────────────────────
│
├── data/
│   ├── knowledge_base/                  # RAG source documents (version controlled)
│   │   ├── arrays.md
│   │   ├── linked_lists.md
│   │   ├── trees.md
│   │   ├── graphs.md
│   │   ├── dynamic_programming.md
│   │   ├── sorting.md
│   │   ├── hashing.md
│   │   ├── stacks_queues.md
│   │   ├── two_pointers.md
│   │   ├── sliding_window.md
│   │   ├── binary_search.md
│   │   ├── recursion_backtracking.md
│   │   ├── greedy.md
│   │   ├── bit_manipulation.md
│   │   └── complexity_analysis.md
│   │
│   ├── vector_store/                    # ChromaDB persistent storage (gitignored)
│   │   └── chroma/
│   │
│   ├── scraped/                         # Module 1 outputs (gitignored)
│   │   └── {slug}.json
│   │
│   ├── tags/                            # Module 2 outputs (gitignored)
│   │   └── {slug}_tags.json
│   │
│   ├── rag/                             # Module 3 outputs (gitignored)
│   │   └── {slug}_context.json
│   │
│   ├── scripts/                         # Module 4 outputs (gitignored)
│   │   └── {slug}_script.json
│   │
│   ├── voice/                           # Module 5 outputs (gitignored)
│   │   └── {slug}/
│   │       ├── section_hook.wav
│   │       ├── section_problem_statement.wav
│   │       ├── ...
│   │       └── manifest.json
│   │
│   ├── animation/                       # Module 6 outputs (gitignored)
│   │   └── {slug}/
│   │       ├── section_hook.mp4
│   │       ├── section_problem_statement.mp4
│   │       └── ...
│   │
│   ├── output/                          # Module 7 outputs (gitignored)
│   │   └── {slug}/
│   │       ├── final.mp4
│   │       └── thumbnail.png
│   │
│   ├── uploads/                         # Module 8 outputs (gitignored)
│   │   └── {slug}_upload.json
│   │
│   ├── checkpoints/                     # Orchestrator checkpoints (gitignored)
│   │   └── {slug}/
│   │       ├── scraper.json
│   │       ├── tags.json
│   │       ├── rag.json
│   │       ├── script.json
│   │       ├── voice.json
│   │       ├── animation.json
│   │       ├── assembly.json
│   │       └── youtube.json
│   │
│   └── memory/                          # Module 9 persistent store (gitignored)
│       └── memory.json
│
│   ── Voice & Models ────────────────────────────────────────────────
│
├── voice_samples/                       # Reference audio for voice cloning
│   └── reference.wav
│
├── models/                              # AI model files (gitignored)
│   └── kokoro-82m-openvino/
│       ├── model.xml
│       ├── model.bin
│       └── config.json
│
│   ── Documentation ─────────────────────────────────────────────────
│
├── PromptBook/                          # AI development guides & prompts
│   ├── 00_Project_Context.md
│   ├── 01_Global_Rules.md
│   ├── 02_Project_Architecture.md
│   ├── 03_Project_Standards.md
│   ├── 04_Folder_Structure.md           # THIS DOCUMENT
│   ├── 05_Project_Roadmap.md
│   ├── 06_AI_Development_Guide.md
│   ├── 07_Prompt_Template_Library.md
│   ├── Phase01/
│   │   └── {phase-specific specs}
│   └── Phase02/
│       └── {phase-specific specs}
│
│   ── Developer Utilities ───────────────────────────────────────────
│
├── scripts/                             # Shell scripts for developer workflow
│   ├── setup.sh                         # Environment setup & dependency install
│   ├── lint.sh                          # Run flake8 + mypy + isort check
│   ├── test.sh                          # Run pytest with coverage
│   └── clean.sh                         # Delete all generated data/ artifacts
│
│   ── Runtime Logs ──────────────────────────────────────────────────
│
└── logs/                                # Application logs (gitignored)
    └── pipeline.log                     # Rotating log file (50MB × 5 backups)
```

---

## 2. Project Root

### Purpose

The project root (`Youtube-Channel/`) is the top-level directory that anchors every path in the system. It contains only project-wide configuration files, the `README`, and entry to all subdirectories. It is the working directory from which the pipeline is invoked.

### Allowed Files

| File | Purpose |
|---|---|
| `.env` | Environment variables containing secrets (API keys, session cookies). Never committed. |
| `.env.example` | Template showing required environment variables with placeholder values. Committed. |
| `.gitignore` | Git exclusion rules for secrets, data artifacts, logs, model files. |
| `pyproject.toml` | Project metadata, Python dependencies, tool configuration (mypy, flake8, isort, pytest, coverage). |
| `README.md` | Project overview, prerequisites, quick start guide, architecture link. |
| `reference.wav` | Legacy voice reference file. Retained for backward compatibility; canonical location is `voice_samples/`. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| `requirements.txt` | Dependencies live in `pyproject.toml`. |
| `setup.py`, `setup.cfg` | Superseded by `pyproject.toml`. |
| `Makefile` | Developer scripts live in `scripts/`. |
| `Dockerfile`, `docker-compose.yml` | No containerization (see `02_Project_Architecture.md`, Section 17.1). |
| Any `.py` file | All Python source lives under `src/`. |
| `*.log` | Logs live under `logs/`. |
| `*.json`, `*.yaml` (data) | Configuration lives in `config/`, data in `data/`. |

### Dependencies

None. The project root is the dependency anchor — everything depends downward from it.

### Public Interface

```bash
# Primary entry point
python -m src two-sum

# With options
python -m src two-sum --force-regenerate --skip-upload
```

### Future Expansion

| Addition | Location |
|---|---|
| `CHANGELOG.md` | Project root |
| `CONTRIBUTING.md` | Project root |
| `LICENSE` | Project root |
| `.pre-commit-config.yaml` | Project root (if pre-commit hooks are adopted) |

---

## 3. Source Code — `src/`

### Purpose

The root Python package containing **all application source code**. This is the only directory containing `.py` files intended for production execution. It serves as the namespace root for all imports.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Package marker. May contain version string (`__version__`). |
| `__main__.py` | CLI entry point and **composition root** — the single location where all concrete dependencies are instantiated and wired together. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Any module file (`.py`) beyond `__init__.py` and `__main__.py` | All logic lives in sub-packages. |
| Test files | Tests live in `tests/`. |
| Configuration files | Configuration lives in `config/`. |
| Data files | Data lives in `data/`. |

### Dependencies

`src/` depends on:
- All sub-packages within it (for the composition root in `__main__.py`).

### Public Interface

`src/__main__.py` is the **only file** that knows about concrete implementations. It:
1. Parses CLI arguments.
2. Loads `PipelineConfig` via `load_config()`.
3. Instantiates all concrete module classes.
4. Wires them into the `PipelineOrchestrator`.
5. Calls `orchestrator.run(slug)`.

```python
# Invocation
python -m src <slug> [options]
```

### Sub-Package Layout

```
src/
├── models/         Layer 1 — Domain vocabulary (true leaf, no deps)
├── core/           Layer 2 — Shared services (near-leaf, depends on models/ only)
├── scraper/        Layer 3 — Pipeline module
├── tags/           Layer 3 — Pipeline module
├── rag/            Layer 3 — Pipeline module
├── script/         Layer 3 — Pipeline module
├── voice/          Layer 3 — Pipeline module
├── animation/      Layer 3 — Pipeline module
├── assembly/       Layer 3 — Pipeline module
├── youtube/        Layer 3 — Pipeline module
├── memory/         Layer 3 — Pipeline module
└── orchestrator/   Layer 4 — Entry point (depends on Layer 3 protocols)
```

### Future Expansion

New pipeline modules are added as new sub-packages at Layer 3:
- `src/thumbnail/` — Thumbnail generation.
- `src/subtitles/` — Subtitle/caption generation.
- `src/analytics/` — YouTube Analytics integration.

---

## 4. Domain Models — `src/models/`

### Purpose

The **shared vocabulary** of the entire system. Contains all dataclasses, enums, type aliases, and Protocol interfaces that define the contracts between modules. This is the leaf package — it depends on nothing else in the project.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Re-exports all public dataclasses and enums for convenience imports. |
| `enums.py` | All enumeration types: `Difficulty`, `SectionType`, `PipelineStatus`, `AnimationStyle`. |
| `problem.py` | `ScrapedProblem`, `Example` — Scraper output contract. |
| `tags.py` | `TagKnowledge`, `RelatedProblem` — Tag Explorer output contract. |
| `rag.py` | `RAGContext`, `RetrievedChunk` — RAG Engine output contract. |
| `script.py` | `VideoScript`, `ScriptSection`, `SEOMetadata` — Script Generator output contract. |
| `visual_params.py` | `VisualParams` union type and all per-scene typed parameter dataclasses (`ArrayVisualParams`, `CodeVisualParams`, `TreeVisualParams`, etc.). |
| `voice.py` | `VoiceResult`, `SectionAudio` — Voice module output contract. |
| `animation.py` | `AnimationResult`, `SectionClip` — Animation module output contract. |
| `assembly.py` | `AssembledVideo` — Assembly module output contract. |
| `youtube.py` | `UploadResult` — YouTube module output contract. |
| `memory.py` | `MemoryRecord` — Memory module storage contract. |
| `pipeline.py` | `PipelineResult` — Orchestrator output contract. |
| `protocols.py` | All `Protocol` interfaces: `ScraperProtocol`, `TagExplorerProtocol`, `RAGEngineProtocol`, `ScriptGeneratorProtocol`, `VoiceSynthesizerProtocol`, `AnimationRendererProtocol`, `VideoAssemblerProtocol`, `YouTubeUploaderProtocol`, `MemoryStoreProtocol`. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Any implementation logic | Models are pure data definitions — no algorithms, no I/O, no API calls. |
| Any import from `src/core/` or pipeline modules | Leaf package — zero internal dependencies. |
| Configuration dataclasses | Config types live in `src/core/config.py`. |
| Test files | Tests live in `tests/test_models/`. |

### Dependencies

**None.** `src/models/` is a leaf package. It imports only from the Python standard library (`dataclasses`, `datetime`, `pathlib`, `enum`, `typing`).

### Public Interface

Every other package in `src/` may import from `src/models/`:

```python
from src.models.problem import ScrapedProblem
from src.models.enums import Difficulty
from src.models.protocols import ScraperProtocol
```

### File Organization Rule

One model file per pipeline module output. The file name matches the domain concept, not the module name:

| Module | Output Contract | Model File |
|---|---|---|
| Scraper | `ScrapedProblem` | `problem.py` |
| Tag Explorer | `TagKnowledge` | `tags.py` |
| RAG Engine | `RAGContext` | `rag.py` |
| Script Generator | `VideoScript` | `script.py` |
| Script Generator (visuals) | `VisualParams` union | `visual_params.py` |
| Voice | `VoiceResult` | `voice.py` |
| Animation | `AnimationResult` | `animation.py` |
| Assembly | `AssembledVideo` | `assembly.py` |
| YouTube | `UploadResult` | `youtube.py` |
| Memory | `MemoryRecord` | `memory.py` |
| Orchestrator | `PipelineResult` | `pipeline.py` |

### Future Expansion

When a new module is added, its output contract is added as a new file in `src/models/`:
- `src/models/thumbnail.py` — `GeneratedThumbnail` dataclass.
- `src/models/subtitles.py` — `SubtitleTrack` dataclass.

A new Protocol is added to `protocols.py` for the new module.

---

## 5. Shared Infrastructure — `src/core/`

### Purpose

Cross-cutting infrastructure utilities used by every pipeline module. Provides configuration loading, logging setup, serialization, caching, error handling, retry logic, and path resolution. This is a **near-leaf** package — it depends on `src/models/` for serialization type resolution, but does not depend on any pipeline module.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Re-exports commonly used utilities. |
| `config.py` | `PipelineConfig` and all sub-config dataclasses (`ScraperConfig`, `RAGConfig`, etc.). `load_config()` function that merges CLI args → `.env` → YAML → defaults. |
| `logger.py` | `get_logger()` factory. `structlog` configuration with console and file handlers. Pipeline run ID binding. |
| `serialization.py` | `serialize()` and `deserialize()` functions. Custom JSON encoders/decoders for `datetime`, `Path`, `Enum`, frozen dataclasses. |
| `cache.py` | `FileCache` class with `get()`, `put()`, `invalidate()`, `invalidate_all()`. Slug-keyed file-based caching. |
| `exceptions.py` | Complete `PipelineError` exception hierarchy (see `02_Project_Architecture.md`, Section 10.1). |
| `retry.py` | `@retry` decorator with configurable max attempts, initial delay, backoff factor, and retryable exception types. |
| `paths.py` | `PROJECT_ROOT` constant, `resolve_path()` for config-relative paths, `ensure_dir()` for safe directory creation. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Any domain-specific logic | Scraper logic goes in `src/scraper/`, not here. |
| Any import from pipeline modules | Leaf package — cannot depend on Layer 3. |
| Any import from `src/models/` except types used in config | `core/` is parallel to `models/`, not dependent on it. Config dataclasses reference primitive types only. |
| API client implementations | HTTP clients belong in their respective modules. |

### Dependencies

**Minimal.** `src/core/` imports from:
- Python standard library.
- `structlog` (logging).
- `pyyaml` (YAML parsing for config).
- `python-dotenv` (`.env` loading for config).

It does **not** import from `src/models/` for core utilities. The `config.py` file may define its own config dataclasses that use only primitive types.

### Public Interface

Every pipeline module receives core services via constructor injection:

```python
from src.core.config import ScraperConfig
from src.core.exceptions import ScraperError, AuthenticationError
from src.core.retry import retry
from src.core.paths import resolve_path, ensure_dir
```

### Future Expansion

| Addition | File |
|---|---|
| Rate limiter utility | `src/core/rate_limiter.py` |
| Metrics/timing collector | `src/core/metrics.py` |
| Event bus (if needed) | `src/core/events.py` |
| Validation utilities | `src/core/validation.py` |

---

## 6. Module 1: Problem Scraper — `src/scraper/`

### Purpose

Extract complete problem metadata and the user's accepted C++ solution from LeetCode via its GraphQL API.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Exports `LeetCodeScraper`. |
| `scraper.py` | `LeetCodeScraper` class implementing `ScraperProtocol`. Orchestrates the scraping workflow: validate slug → check cache → fetch → parse → persist. |
| `client.py` | `LeetCodeClient` class. Low-level HTTP transport. Sends GraphQL queries to `leetcode.com/graphql` with session cookie authentication. Handles rate limiting, timeouts, and retries. |
| `parser.py` | `ResponseParser` class. Transforms raw GraphQL JSON responses into `ScrapedProblem` dataclass. Cleans HTML, normalizes text, extracts code submissions. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Any import from other pipeline modules | Module independence. |
| Tag expansion logic | Belongs in `src/tags/`. |
| Script generation logic | Belongs in `src/script/`. |
| General-purpose HTTP utilities | If reusable, belongs in `src/core/`. |

### Dependencies

| Dependency | Type | Source |
|---|---|---|
| `ScrapedProblem`, `Example`, `Difficulty` | Dataclasses/Enums | `src/models/` |
| `ScraperConfig` | Configuration | `src/core/config` |
| `ScraperError`, `AuthenticationError`, `ProblemNotFoundError`, `RateLimitError` | Exceptions | `src/core/exceptions` |
| `@retry` | Decorator | `src/core/retry` |
| `httpx` | HTTP client | Third-party |
| `structlog` | Logging | Third-party |

### Public Interface

```python
class LeetCodeScraper:
    def __init__(self, config: ScraperConfig, logger: BoundLogger) -> None: ...
    def scrape(self, slug: str) -> ScrapedProblem: ...
```

### Data Output

```
data/scraped/{slug}.json     # Serialized ScrapedProblem
```

### Future Expansion

| Addition | File |
|---|---|
| HackerRank scraper | New module `src/hackerrank/` implementing `ScraperProtocol` |
| CodeForces scraper | New module `src/codeforces/` implementing `ScraperProtocol` |
| Batch slug resolver | `src/scraper/resolver.py` — resolve problem numbers to slugs |

---

## 7. Module 2: Tag Explorer — `src/tags/`

### Purpose

Enrich raw LeetCode tags with deep algorithmic knowledge: pattern families, prerequisite concepts, related problems, and animation style classification.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Exports `GeminiTagExplorer`. |
| `explorer.py` | `GeminiTagExplorer` class implementing `TagExplorerProtocol`. Sends enriched tag queries to Gemini API, parses structured responses. |
| `patterns.py` | `PATTERN_FAMILIES` constant mapping, `ANIMATION_STYLE_MAP`, and other static classification data. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| LeetCode API calls | Scraping belongs in `src/scraper/`. |
| Embedding or vector logic | RAG belongs in `src/rag/`. |
| Script text generation | Belongs in `src/script/`. |

### Dependencies

| Dependency | Type | Source |
|---|---|---|
| `TagKnowledge`, `RelatedProblem`, `AnimationStyle` | Dataclasses/Enums | `src/models/` |
| `ScrapedProblem` | Input dataclass | `src/models/` |
| `TagsConfig` | Configuration | `src/core/config` |
| `TagExplorationError` | Exception | `src/core/exceptions` |
| `google-genai` | Gemini SDK | Third-party |

### Public Interface

```python
class GeminiTagExplorer:
    def __init__(self, config: TagsConfig, logger: BoundLogger) -> None: ...
    def explore(self, problem: ScrapedProblem) -> TagKnowledge: ...
```

### Data Output

```
data/tags/{slug}_tags.json     # Serialized TagKnowledge
```

### Future Expansion

| Addition | File |
|---|---|
| Local LLM tag explorer | New class in `explorer.py` or separate `local_explorer.py` |
| Tag taxonomy visualizer | `src/tags/taxonomy.py` |

---

## 8. Module 3: RAG Knowledge Engine — `src/rag/`

### Purpose

Retrieve pedagogically relevant context from a local knowledge base to ground script generation in factually accurate explanations. Manages the document index, embedding pipeline, and retrieval queries.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Exports `ChromaRAGEngine`. |
| `engine.py` | `ChromaRAGEngine` class implementing `RAGEngineProtocol`. Entry point for retrieval queries (`retrieve()`) and index management (`index_knowledge_base()`). |
| `chunker.py` | `TopicAwareChunker` class. Splits Markdown documents into semantically coherent chunks by heading structure, respecting topic boundaries. |
| `embedder.py` | `GeminiEmbedder` class. Wrapper around Gemini's embedding model. Handles batching, rate limiting, and error recovery. |
| `indexer.py` | `KnowledgeBaseIndexer` class. Orchestrates the full indexing workflow: discover files → chunk → embed → upsert into ChromaDB. Supports incremental indexing. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| LeetCode API calls | Scraping belongs in `src/scraper/`. |
| Script generation | Belongs in `src/script/`. |
| General-purpose embedding utilities | If reusable beyond RAG, move to `src/core/`. |

### Dependencies

| Dependency | Type | Source |
|---|---|---|
| `RAGContext`, `RetrievedChunk` | Dataclasses | `src/models/` |
| `ScrapedProblem`, `TagKnowledge` | Input dataclasses | `src/models/` |
| `RAGConfig` | Configuration | `src/core/config` |
| `RAGError`, `IndexNotFoundError`, `EmbeddingError` | Exceptions | `src/core/exceptions` |
| `chromadb` | Vector store | Third-party |
| `google-genai` | Embeddings | Third-party |

### Public Interface

```python
class ChromaRAGEngine:
    def __init__(self, config: RAGConfig, logger: BoundLogger) -> None: ...
    def retrieve(self, problem: ScrapedProblem, tags: TagKnowledge) -> RAGContext: ...
    def index_knowledge_base(self) -> int: ...
```

### Data Output

```
data/rag/{slug}_context.json       # Serialized RAGContext
data/vector_store/chroma/          # ChromaDB persistent index
```

### Future Expansion

| Addition | File |
|---|---|
| Re-ranker (cross-encoder) | `src/rag/reranker.py` |
| Hybrid search (BM25 + vector) | `src/rag/hybrid.py` |
| Index health checker | `src/rag/diagnostics.py` |

---

## 9. Module 4: Script Generator — `src/script/`

### Purpose

Synthesize a structured, narration-ready JSON video script from problem data, tag knowledge, and RAG context. The script drives both the voice and animation modules downstream.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Exports `GeminiScriptGenerator`. |
| `generator.py` | `GeminiScriptGenerator` class implementing `ScriptGeneratorProtocol`. Constructs the composite prompt, calls Gemini, parses the structured response. |
| `prompts.py` | Prompt template constants and builders. System prompts, section schema definitions, few-shot examples. |
| `validator.py` | `ScriptValidator` class. Validates generated scripts against the 10-section JSON schema. Checks section ordering, required fields, narration quality heuristics. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| LeetCode API calls | Belongs in `src/scraper/`. |
| Embedding or retrieval logic | Belongs in `src/rag/`. |
| Voice synthesis | Belongs in `src/voice/`. |
| Animation rendering | Belongs in `src/animation/`. |

### Dependencies

| Dependency | Type | Source |
|---|---|---|
| `VideoScript`, `ScriptSection`, `SEOMetadata`, `SectionType` | Dataclasses/Enums | `src/models/` |
| `ScrapedProblem`, `TagKnowledge`, `RAGContext`, `MemoryRecord` | Input dataclasses | `src/models/` |
| `ScriptConfig` | Configuration | `src/core/config` |
| `ScriptGenerationError`, `SchemaValidationError`, `ContentFilterError` | Exceptions | `src/core/exceptions` |
| `google-genai` | Gemini SDK | Third-party |

### Public Interface

```python
class GeminiScriptGenerator:
    def __init__(self, config: ScriptConfig, logger: BoundLogger) -> None: ...
    def generate(
        self,
        problem: ScrapedProblem,
        tags: TagKnowledge,
        rag_context: RAGContext,
        memory: MemoryRecord | None = None,
    ) -> VideoScript: ...
```

### Data Output

```
data/scripts/{slug}_script.json     # Serialized VideoScript
```

### Future Expansion

| Addition | File |
|---|---|
| Multi-variant generation (A/B) | `src/script/variants.py` |
| Script quality scorer | `src/script/scorer.py` |
| Local LLM generator | New class implementing `ScriptGeneratorProtocol` |

---

## 10. Module 5: Voice Generation — `src/voice/`

### Purpose

Convert narration text into high-quality speech audio using the Kokoro-82M TTS model running locally via OpenVINO on the Intel Core Ultra 7 155H.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Exports `KokoroVoiceSynthesizer`. |
| `synthesizer.py` | `KokoroVoiceSynthesizer` class implementing `VoiceSynthesizerProtocol`. Loads the OpenVINO model, processes sections sequentially, exports WAV files, generates timing manifest. |
| `audio_utils.py` | Audio processing utilities: sample rate validation, silence trimming, WAV export, duration calculation. No TTS logic — pure audio manipulation. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Script generation | Belongs in `src/script/`. |
| Animation rendering | Belongs in `src/animation/`. |
| FFmpeg commands | Belongs in `src/assembly/`. |
| Model training or fine-tuning code | Out of scope. |

### Dependencies

| Dependency | Type | Source |
|---|---|---|
| `VoiceResult`, `SectionAudio` | Dataclasses | `src/models/` |
| `VideoScript` | Input dataclass | `src/models/` |
| `VoiceConfig` | Configuration | `src/core/config` |
| `VoiceSynthesisError`, `ModelLoadError`, `AudioExportError` | Exceptions | `src/core/exceptions` |
| `openvino` | Inference runtime | Third-party |
| `numpy`, `scipy` | Audio processing | Third-party |

### Public Interface

```python
class KokoroVoiceSynthesizer:
    def __init__(self, config: VoiceConfig, logger: BoundLogger) -> None: ...
    def synthesize(self, script: VideoScript) -> VoiceResult: ...
```

### Data Output

```
data/voice/{slug}/
├── section_hook.wav
├── section_problem_statement.wav
├── section_constraints.wav
├── section_brute_force.wav
├── section_optimized_approach.wav
├── section_visual_walkthrough.wav
├── section_dry_run.wav
├── section_code_walkthrough.wav
├── section_complexity_analysis.wav
├── section_closing.wav
└── manifest.json                 # Timing manifest
```

### Future Expansion

| Addition | File |
|---|---|
| ElevenLabs TTS | New module `src/voice_elevenlabs/` implementing `VoiceSynthesizerProtocol` |
| Voice quality analyzer | `src/voice/quality.py` |
| SSML preprocessing | `src/voice/ssml.py` |

---

## 11. Module 6: Manim Animation Engine — `src/animation/`

### Purpose

Render programmatic mathematical and algorithmic animations for each script section using the Manim Community library. Contains a library of reusable scene templates for common DSA patterns.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Exports `ManimAnimationRenderer`. |
| `renderer.py` | `ManimAnimationRenderer` class implementing `AnimationRendererProtocol`. Selects scene templates, configures with section data, triggers Manim renders, collects outputs. |
| `theme.py` | Visual theme constants: background color, syntax colors, font families, font sizes, animation easing functions, padding values. Single source of truth for visual consistency. |
| `scenes/` | Sub-package containing reusable Manim scene templates (see below). |

### Sub-Package: `src/animation/scenes/`

| File | Purpose |
|---|---|
| `__init__.py` | Exports all scene classes. Contains `SCENE_REGISTRY` mapping `AnimationStyle` enum to scene class. |
| `base_scene.py` | `DSABaseScene` — Base scene class with dark background, standard layout grid, consistent text styling, fade-in/fade-out transitions. All other scenes inherit from this. |
| `array_scene.py` | `ArrayScene` — Array visualization with index pointers, element highlighting, swap animations, traversal indicators. |
| `linkedlist_scene.py` | `LinkedListScene` — Linked list node rendering, pointer movement, insertion/deletion, reversal animations. |
| `tree_scene.py` | `TreeScene` — Binary tree layout, BFS/DFS traversal with level coloring, node highlighting, subtree operations. |
| `graph_scene.py` | `GraphScene` — Graph with adjacency visualization, edge traversal animations, visited/unvisited coloring, path highlighting. |
| `hashmap_scene.py` | `HashMapScene` — Hash table bucket visualization, collision chains, lookup animations. |
| `stack_queue_scene.py` | `StackQueueScene` — Stack push/pop and queue enqueue/dequeue with element movement. |
| `code_scene.py` | `CodeScene` — Syntax-highlighted code display with line-by-line execution pointer, variable state panel. |
| `complexity_scene.py` | `ComplexityScene` — Big-O comparison bar/line charts, growth rate animations. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Voice synthesis | Belongs in `src/voice/`. |
| FFmpeg video processing | Belongs in `src/assembly/`. |
| Script generation | Belongs in `src/script/`. |
| Non-Manim rendering (PIL, matplotlib for scene content) | Scenes use Manim's Mobject API exclusively. |

### Dependencies

| Dependency | Type | Source |
|---|---|---|
| `AnimationResult`, `SectionClip`, `AnimationStyle` | Dataclasses/Enums | `src/models/` |
| `VideoScript`, `VoiceResult` | Input dataclasses | `src/models/` |
| `AnimationConfig` | Configuration | `src/core/config` |
| `AnimationRenderError`, `SceneConfigError` | Exceptions | `src/core/exceptions` |
| `manim` | Animation framework | Third-party |

### Public Interface

```python
class ManimAnimationRenderer:
    def __init__(self, config: AnimationConfig, logger: BoundLogger) -> None: ...
    def render(self, script: VideoScript, voice: VoiceResult) -> AnimationResult: ...
```

### Data Output

```
data/animation/{slug}/
├── section_hook.mp4
├── section_problem_statement.mp4
├── ...
└── section_closing.mp4
```

### Future Expansion

| Addition | File |
|---|---|
| Dynamic programming table scene | `src/animation/scenes/dp_table_scene.py` |
| Trie/prefix tree scene | `src/animation/scenes/trie_scene.py` |
| Sorting algorithm scene | `src/animation/scenes/sorting_scene.py` |
| Intro/outro title card scene | `src/animation/scenes/title_scene.py` |
| Scene preview server | `src/animation/preview.py` |

---

## 12. Module 7: Video Assembly — `src/assembly/`

### Purpose

Stitch together voice audio and animation video clips into a final, polished YouTube-ready video using FFmpeg.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Exports `FFmpegVideoAssembler`. |
| `assembler.py` | `FFmpegVideoAssembler` class implementing `VideoAssemblerProtocol`. Validates inputs, orchestrates the assembly workflow (mux → concat → normalize → export), generates thumbnail. |
| `ffmpeg_commands.py` | `FFmpegCommandBuilder` — Constructs FFmpeg command-line argument lists for: single-section mux (audio onto video), multi-section concatenation, audio normalization (LUFS), thumbnail extraction, and hardware-accelerated encoding. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Manim rendering | Belongs in `src/animation/`. |
| Voice synthesis | Belongs in `src/voice/`. |
| YouTube upload | Belongs in `src/youtube/`. |
| Direct FFmpeg binary management (download, install) | System prerequisite. |

### Dependencies

| Dependency | Type | Source |
|---|---|---|
| `AssembledVideo` | Output dataclass | `src/models/` |
| `VoiceResult`, `AnimationResult`, `VideoScript` | Input dataclasses | `src/models/` |
| `AssemblyConfig` | Configuration | `src/core/config` |
| `AssemblyError`, `FFmpegNotFoundError`, `MuxingError` | Exceptions | `src/core/exceptions` |
| `subprocess` | FFmpeg execution | Standard library |

### Public Interface

```python
class FFmpegVideoAssembler:
    def __init__(self, config: AssemblyConfig, logger: BoundLogger) -> None: ...
    def assemble(
        self,
        voice: VoiceResult,
        animation: AnimationResult,
        script: VideoScript,
    ) -> AssembledVideo: ...
```

### Data Output

```
data/output/{slug}/
├── final.mp4          # Complete YouTube-ready video
└── thumbnail.png      # Extracted/composed thumbnail
```

### Future Expansion

| Addition | File |
|---|---|
| Background music mixer | `src/assembly/music.py` |
| Subtitle overlay | `src/assembly/subtitles.py` |
| Intro/outro appender | `src/assembly/bookends.py` |
| Intel QSV acceleration | Enhancement within `ffmpeg_commands.py` |

---

## 13. Module 8: YouTube Upload — `src/youtube/`

### Purpose

Upload the assembled video to YouTube with full metadata using the YouTube Data API v3 via OAuth 2.0 authentication.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Exports `YouTubeAPIUploader`. |
| `uploader.py` | `YouTubeAPIUploader` class implementing `YouTubeUploaderProtocol`. Handles video upload (resumable), metadata setting, thumbnail upload, and quota management. |
| `auth.py` | `OAuthManager` class. Manages OAuth 2.0 flow: initial authorization, token persistence, automatic refresh. Stores tokens at `config/youtube_token.json`. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Video rendering or assembly | Belongs in `src/assembly/`. |
| Script generation | Belongs in `src/script/`. |
| YouTube Analytics | Future module — `src/analytics/`. |
| Channel management beyond upload | Out of scope. |

### Dependencies

| Dependency | Type | Source |
|---|---|---|
| `UploadResult` | Output dataclass | `src/models/` |
| `AssembledVideo`, `SEOMetadata` | Input dataclasses | `src/models/` |
| `YouTubeConfig` | Configuration | `src/core/config` |
| `YouTubeUploadError`, `QuotaExceededError`, `AuthTokenExpiredError` | Exceptions | `src/core/exceptions` |
| `google-api-python-client` | YouTube API | Third-party |
| `google-auth`, `google-auth-oauthlib` | OAuth | Third-party |

### Public Interface

```python
class YouTubeAPIUploader:
    def __init__(self, config: YouTubeConfig, logger: BoundLogger) -> None: ...
    def upload(self, video: AssembledVideo, metadata: SEOMetadata) -> UploadResult: ...
```

### Data Output

```
data/uploads/{slug}_upload.json     # Serialized UploadResult
config/youtube_token.json           # OAuth token (gitignored)
```

### Future Expansion

| Addition | File |
|---|---|
| Upload queue for offline batching | `src/youtube/queue.py` |
| Playlist management | `src/youtube/playlists.py` |
| Video update (re-upload metadata) | Enhancement within `uploader.py` |

---

## 14. Module 9: Memory System — `src/memory/`

### Purpose

Maintain a persistent record of all generated videos for deduplication, quality tracking, and cross-video consistency. Feeds historical data back into the script generator.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Exports `JSONMemoryStore`. |
| `store.py` | `JSONMemoryStore` class implementing `MemoryStoreProtocol`. CRUD operations on `MemoryRecord` objects. Reads/writes `data/memory/memory.json`. Provides query methods for deduplication and analytics. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Script generation logic | Belongs in `src/script/`. |
| YouTube API calls | Belongs in `src/youtube/`. |
| Database schema migrations | No database in use (JSON file store). |
| Analytics dashboards | Future module. |

### Dependencies

| Dependency | Type | Source |
|---|---|---|
| `MemoryRecord`, `PipelineStatus` | Dataclasses/Enums | `src/models/` |
| Core config, logging, serialization | Infrastructure | `src/core/` |
| `MemoryError`, `CorruptedStoreError` | Exceptions | `src/core/exceptions` |

### Public Interface

```python
class JSONMemoryStore:
    def __init__(self, config: PipelineGlobalConfig, logger: BoundLogger) -> None: ...
    def save(self, record: MemoryRecord) -> None: ...
    def has_been_generated(self, slug: str) -> bool: ...
    def get_record(self, slug: str) -> MemoryRecord | None: ...
    def get_all_tags(self) -> set[str]: ...
    def get_problems_by_tag(self, tag: str) -> list[str]: ...
    def get_failed_runs(self) -> list[MemoryRecord]: ...
```

### Data Output

```
data/memory/memory.json     # Persistent memory store
```

### Future Expansion

| Addition | File |
|---|---|
| SQLite backend | `src/memory/sqlite_store.py` implementing `MemoryStoreProtocol` |
| Analytics queries | `src/memory/analytics.py` |
| Memory export/import | `src/memory/export.py` |

---

## 15. Module 0: Pipeline Orchestrator — `src/orchestrator/`

### Purpose

Coordinate the sequential execution of all pipeline modules, manage checkpoints for crash recovery, and aggregate results.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Exports `PipelineOrchestrator`. |
| `pipeline.py` | `PipelineOrchestrator` class. Accepts all module instances via constructor injection. Executes the 9-module sequence. Handles non-critical module failures. Reports final status with timing. |
| `checkpoint.py` | `CheckpointManager` class. Saves module outputs as checkpoint files after each stage. On restart, detects existing checkpoints and returns the resume point. Cleans up checkpoints after successful completion. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Any domain logic (scraping, rendering, uploading) | The orchestrator calls modules, it does not contain module logic. |
| Concrete module imports (e.g., `from src.scraper.scraper import ...`) | The orchestrator depends only on protocols from `src/models/protocols.py`. Concrete classes are wired in `src/__main__.py`. |
| CLI argument parsing | Lives in `src/__main__.py`. |

### Dependencies

| Dependency | Type | Source |
|---|---|---|
| All `Protocol` interfaces | Abstractions | `src/models/protocols` |
| All output dataclasses | Return types | `src/models/` |
| `PipelineConfig` | Configuration | `src/core/config` |
| `PipelineError` (base) | Exception handling | `src/core/exceptions` |

### Public Interface

```python
class PipelineOrchestrator:
    def __init__(
        self,
        config: PipelineConfig,
        scraper: ScraperProtocol,
        tag_explorer: TagExplorerProtocol,
        rag_engine: RAGEngineProtocol,
        script_generator: ScriptGeneratorProtocol,
        voice_synthesizer: VoiceSynthesizerProtocol,
        animation_renderer: AnimationRendererProtocol,
        video_assembler: VideoAssemblerProtocol,
        youtube_uploader: YouTubeUploaderProtocol,
        memory_store: MemoryStoreProtocol,
        logger: BoundLogger,
    ) -> None: ...

    def run(self, slug: str) -> PipelineResult: ...
```

### Data Output

```
data/checkpoints/{slug}/
├── scraper.json
├── tags.json
├── rag.json
├── script.json
├── voice.json
├── animation.json
├── assembly.json
└── youtube.json
```

### Future Expansion

| Addition | File |
|---|---|
| Parallel Voice+Manim execution | Enhancement within `pipeline.py` |
| Batch processing (slug list) | `src/orchestrator/batch.py` |
| Progress dashboard (Rich/Textual) | `src/orchestrator/dashboard.py` |

---

## 16. Tests — `tests/`

### Purpose

All test code for the project. Mirrors the `src/` directory structure exactly. Every source module has a corresponding test sub-package.

### Allowed Files

| File | Purpose |
|---|---|
| `__init__.py` | Package markers (in every test directory). |
| `conftest.py` | Fixtures. Global fixtures in `tests/conftest.py`. Module-specific fixtures in `tests/test_{module}/conftest.py`. |
| `test_*.py` | Test modules. One test file per source file. Named `test_{source_file}.py`. |
| `test_*_e2e.py` | End-to-end test modules. Integration tests that exercise multiple components. |
| `factories.py` | Factory functions for creating test data. Alternative to fixture-heavy conftest. |
| `fakes.py` | Fake implementations of protocols for testing (e.g., `FakeScraper`, `FakeVoiceSynthesizer`). |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Production source code | Source lives in `src/`. |
| Configuration files | Config lives in `config/`. |
| Data files (persisted to `data/`) | Tests use `tmp_path` fixture. |
| `unittest.TestCase` subclasses | Project uses `pytest` exclusively. |

### Dependencies

| Dependency | Type | Source |
|---|---|---|
| `pytest` | Test framework | Third-party |
| `pytest-cov` | Coverage | Third-party |
| `unittest.mock` | Mocking | Standard library |
| `structlog.testing` | Log assertions | Third-party |
| All `src/` modules | Subjects under test | Internal |

### Structure Mirror Rule

```
src/scraper/scraper.py          →  tests/test_scraper/test_scraper.py
src/scraper/client.py           →  tests/test_scraper/test_client.py
src/scraper/parser.py           →  tests/test_scraper/test_parser.py
src/rag/engine.py               →  tests/test_rag/test_engine.py
src/rag/chunker.py              →  tests/test_rag/test_chunker.py
src/animation/renderer.py       →  tests/test_animation/test_renderer.py
src/animation/scenes/array_scene.py → tests/test_animation/test_scenes/test_array_scene.py
```

### Future Expansion

| Addition | Location |
|---|---|
| Performance benchmarks | `tests/benchmarks/` |
| Snapshot tests (golden files) | `tests/snapshots/` |
| Load tests | `tests/load/` |

---

## 17. Configuration — `config/`

### Purpose

External configuration files that control runtime behavior. Contains non-secret settings (YAML), logging setup, and credential files for external services.

### Allowed Files

| File | Purpose | Committed? |
|---|---|---|
| `pipeline.yaml` | Pipeline runtime configuration (see `02_Project_Architecture.md`, Section 8.2). | Yes |
| `logging.yaml` | Logging handler configuration (console format, file rotation, level overrides). | Yes |
| `client_secrets.json` | YouTube OAuth 2.0 client credentials from Google Cloud Console. | **No** (gitignored) |
| `youtube_token.json` | Persisted OAuth access/refresh tokens (auto-generated by auth flow). | **No** (gitignored) |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| `.env` | Lives in project root. |
| Python files | Config is declarative (YAML/JSON), not code. |
| Data files | Data lives in `data/`. |
| Model files | Models live in `models/`. |
| Generated files | Only `youtube_token.json` is auto-generated (by OAuth flow). |

### Dependencies

`config/` is read by `src/core/config.py` at startup. No other code reads directly from `config/`.

### Future Expansion

| Addition | File |
|---|---|
| Theme configuration (Manim colors) | `config/theme.yaml` |
| Prompt override configuration | `config/prompts.yaml` |
| Multi-environment profiles | `config/pipeline.dev.yaml`, `config/pipeline.prod.yaml` |

---

## 18. Runtime Data — `data/`

### Purpose

All runtime-generated artifacts produced by the pipeline. Contains module outputs, cached intermediate results, the vector store, checkpoints, and the memory store. Every subdirectory is owned by exactly one module.

### Allowed Files

Only files generated by the pipeline. No manually created files except in `data/knowledge_base/`.

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Source code | Source lives in `src/`. |
| Configuration | Config lives in `config/`. |
| Log files | Logs live in `logs/`. |
| Manually created data (except knowledge base) | The pipeline owns this directory. |

### Subdirectory Ownership

| Directory | Owner Module | File Pattern | Committed? |
|---|---|---|---|
| `data/knowledge_base/` | Manual (human-curated) | `{topic}.md` | **Yes** |
| `data/vector_store/` | Module 3 (RAG) | ChromaDB internal | No |
| `data/scraped/` | Module 1 (Scraper) | `{slug}.json` | No |
| `data/tags/` | Module 2 (Tags) | `{slug}_tags.json` | No |
| `data/rag/` | Module 3 (RAG) | `{slug}_context.json` | No |
| `data/scripts/` | Module 4 (Script) | `{slug}_script.json` | No |
| `data/voice/` | Module 5 (Voice) | `{slug}/*.wav`, `manifest.json` | No |
| `data/animation/` | Module 6 (Animation) | `{slug}/*.mp4` | No |
| `data/output/` | Module 7 (Assembly) | `{slug}/final.mp4`, `thumbnail.png` | No |
| `data/uploads/` | Module 8 (YouTube) | `{slug}_upload.json` | No |
| `data/checkpoints/` | Module 0 (Orchestrator) | `{slug}/{module}.json` | No |
| `data/memory/` | Module 9 (Memory) | `memory.json` | No |

### Naming Convention

All runtime data files use the **problem slug** as the primary key:

```
data/{module_output_dir}/{slug}[_suffix].{ext}
```

Examples:
- `data/scraped/two-sum.json`
- `data/tags/two-sum_tags.json`
- `data/voice/two-sum/section_hook.wav`
- `data/output/two-sum/final.mp4`

### Disk Space Considerations

| Data Type | Approximate Size per Problem | Retention Policy |
|---|---|---|
| JSON artifacts (scraped, tags, rag, scripts, uploads) | < 1 MB total | Indefinite (cache) |
| Voice WAV files (10 sections) | 20-50 MB | Indefinite (re-render avoidance) |
| Animation MP4 clips (10 sections) | 50-150 MB | Deletable after assembly |
| Final assembled video | 50-200 MB | Deletable after YouTube upload |
| ChromaDB vector store | 100-500 MB total | Indefinite |
| **Total per problem** | **~150-400 MB** | |

### Future Expansion

| Addition | Directory |
|---|---|
| Generated thumbnails | `data/thumbnails/{slug}/` |
| Subtitle tracks | `data/subtitles/{slug}/` |
| Upload queue | `data/upload_queue/` |

---

## 19. Knowledge Base — `data/knowledge_base/`

### Purpose

Curated educational Markdown documents covering DSA topics. This is the **only manually maintained content** in the `data/` directory. These documents are ingested by the RAG Engine (Module 3) and embedded into the vector store.

### Allowed Files

| File Pattern | Purpose |
|---|---|
| `{topic}.md` | One Markdown file per DSA topic. Uses heading structure for chunk boundaries. |

### Planned Files

| File | Topic Coverage |
|---|---|
| `arrays.md` | Array fundamentals, traversal patterns, in-place operations |
| `linked_lists.md` | Singly/doubly linked lists, fast/slow pointers, reversal |
| `trees.md` | Binary trees, BST, traversals (BFS/DFS), balanced trees |
| `graphs.md` | Graph representations, BFS, DFS, topological sort, shortest path |
| `dynamic_programming.md` | Memoization, tabulation, common DP patterns |
| `sorting.md` | Comparison sorts, counting/radix sort, merge sort analysis |
| `hashing.md` | Hash tables, collision resolution, hash map patterns |
| `stacks_queues.md` | Stack/queue operations, monotonic stacks, BFS with queues |
| `two_pointers.md` | Two-pointer technique, converging/diverging patterns |
| `sliding_window.md` | Fixed and variable-size windows, shrinking conditions |
| `binary_search.md` | Binary search variants, search space reduction |
| `recursion_backtracking.md` | Recursion patterns, backtracking templates, pruning |
| `greedy.md` | Greedy choice property, interval scheduling, activity selection |
| `bit_manipulation.md` | Bitwise operations, XOR tricks, bitmask DP |
| `complexity_analysis.md` | Big-O, Big-Θ, Big-Ω, amortized analysis, space complexity |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Non-Markdown files | RAG chunker expects Markdown heading structure. |
| Code-only files | Documents should be pedagogical explanations, not raw code. |
| Generated/scraped content | This is human-curated, editorially controlled content. |

### Markdown Structure Requirements

Each knowledge base document must follow this structure for optimal chunking:

```markdown
# Topic Name

Brief introduction to the topic.

## Concept 1: Subtopic

Explanation of the first concept...

### Key Insight

Important insight about this concept...

## Concept 2: Another Subtopic

...
```

- **H1 (`#`):** One per file, the topic name.
- **H2 (`##`):** Major concepts — each becomes a primary chunk boundary.
- **H3 (`###`):** Sub-concepts — may be grouped with their parent H2 chunk.
- **Code blocks:** Included within concept explanations (C++ preferred for consistency with LeetCode submissions).
- **No front matter:** No YAML/TOML front matter. The chunker uses headings only.

### Version Control

This directory **is committed to git** and version controlled. Changes to knowledge base content trigger re-indexing of the vector store on the next pipeline run.

### Future Expansion

| Addition | Impact |
|---|---|
| New topic files | Add `.md` file, re-run `index_knowledge_base()` |
| Multi-language explanations | Add `{topic}_{lang}.md` variants |
| External source imports | `data/knowledge_base/external/` sub-directory |

---

## 20. Voice Samples — `voice_samples/`

### Purpose

Reference audio files used for voice cloning and speaker embedding extraction. The Kokoro-82M TTS model uses these samples to match the speaker's voice characteristics.

### Allowed Files

| File | Purpose |
|---|---|
| `reference.wav` | Primary reference audio for voice cloning. Must be clean speech, 10-30 seconds, at target sample rate. |
| Additional `.wav` files | Alternative voice samples for different speaking styles. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Non-audio files | Directory is exclusively for voice reference audio. |
| Compressed audio (`.mp3`, `.ogg`) | Lossy formats degrade voice cloning quality. WAV only. |
| Training data | This is not a model training directory. |

### Audio Requirements

| Parameter | Value |
|---|---|
| Format | WAV (uncompressed) |
| Sample rate | 24 kHz (matching Kokoro-82M output) |
| Channels | Mono |
| Duration | 10-30 seconds of clear speech |
| Content | No background noise, no music, no echo |

### Dependencies

Referenced by `src/voice/synthesizer.py` via the `VoiceConfig.reference_audio` path.

---

## 21. Models — `models/`

### Purpose

Local AI model files for offline inference. Contains the OpenVINO-compiled Kokoro-82M TTS model (and potentially other models in the future). These files are large binaries and are **never committed to git**.

### Allowed Files

| File Pattern | Purpose |
|---|---|
| `kokoro-82m-openvino/model.xml` | OpenVINO IR model definition |
| `kokoro-82m-openvino/model.bin` | OpenVINO IR model weights |
| `kokoro-82m-openvino/config.json` | Model configuration |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Source code | Source lives in `src/`. |
| Training scripts | Out of scope. |
| PyTorch/TensorFlow checkpoints | Only OpenVINO IR format is used in production. |

### Dependencies

Referenced by `src/voice/synthesizer.py` via the `VoiceConfig.model_path` path.

### Version Control

**Gitignored.** Model files are downloaded/converted during setup (via `scripts/setup.sh`) and are not committed. The `README.md` documents how to obtain them.

### Future Expansion

| Addition | Directory |
|---|---|
| Whisper model (for subtitle generation) | `models/whisper-openvino/` |
| Local LLM (for offline script generation) | `models/llama-openvino/` |

---

## 22. PromptBook — `PromptBook/`

### Purpose

AI development guides, project specifications, and prompt templates. These documents define how AI models are used to build, review, and extend the project. They serve as the persistent context for multi-model workflows.

### Allowed Files

| File | Purpose |
|---|---|
| `00_Project_Context.md` | Global system context — project identity, hardware, pipeline overview. |
| `01_Global_Rules.md` | Universal coding rules for all AI-generated code. |
| `02_Project_Architecture.md` | Master architecture specification (module design, data flow, interfaces). |
| `03_Project_Standards.md` | Engineering standards (naming, style, testing, security). |
| `04_Folder_Structure.md` | This document — complete directory specification. |
| `05_Project_Roadmap.md` | Implementation phases, milestones, delivery schedule. |
| `06_AI_Development_Guide.md` | AI model assignments, prompt patterns, review workflows. |
| `07_Prompt_Template_Library.md` | Reusable prompt templates for common tasks. |
| `Phase01/` | Phase 1 implementation specs (per-module design docs). |
| `Phase02/` | Phase 2 implementation specs. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Source code (`.py`) | Source lives in `src/`. |
| Configuration files | Config lives in `config/`. |
| Data files | Data lives in `data/`. |
| Meeting notes or personal docs | Project documentation only. |

### Naming Convention

Files are numbered with two-digit prefixes (`00_` through `99_`) for deterministic ordering. Names use `PascalCase` joined with underscores to match the established convention.

### Dependencies

Referenced by all AI model interactions as context input. No code dependency.

### Future Expansion

| Addition | Location |
|---|---|
| Phase 3+ specs | `PromptBook/Phase03/` |
| Post-mortem documents | `PromptBook/PostMortems/` |
| Decision records (ADRs) | `PromptBook/Decisions/` |

---

## 23. Scripts — `scripts/`

### Purpose

Developer utility shell scripts for common workflow tasks: environment setup, linting, testing, and cleanup. These are convenience wrappers, not production code.

### Allowed Files

| File | Purpose |
|---|---|
| `setup.sh` | Install Python dependencies, download model files, create `data/` directory structure, validate system prerequisites (FFmpeg, Manim). |
| `lint.sh` | Run `flake8`, `mypy --strict`, and `isort --check-only` in sequence. Exit non-zero on any failure. |
| `test.sh` | Run `pytest --cov=src --cov-report=term-missing`. Exit non-zero if coverage is below threshold. |
| `clean.sh` | Delete all generated artifacts in `data/` (excluding `data/knowledge_base/`), `logs/`, and `__pycache__` directories. |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Python scripts | Python utilities belong in `src/core/` or are invoked via `python -m`. |
| Build scripts | No build step needed (`pyproject.toml` handles packaging). |
| Deployment scripts | No deployment infrastructure. |

### Execution

```bash
# Make executable
chmod +x scripts/*.sh

# Run
./scripts/setup.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/clean.sh
```

### Future Expansion

| Addition | File |
|---|---|
| Benchmark runner | `scripts/benchmark.sh` |
| Knowledge base re-indexer | `scripts/reindex.sh` |
| Database migration (if SQLite) | `scripts/migrate.sh` |

---

## 24. Logs — `logs/`

### Purpose

Application log files generated during pipeline execution. Contains rotating log files in structured JSON format for debugging, auditing, and performance analysis.

### Allowed Files

| File | Purpose |
|---|---|
| `pipeline.log` | Active log file. Structured JSON, one entry per line. |
| `pipeline.log.1` through `pipeline.log.5` | Rotated backup log files (automatic rotation at 50MB). |

### Forbidden Files

| Forbidden | Reason |
|---|---|
| Source code | Source lives in `src/`. |
| Data files | Data lives in `data/`. |
| Manually created files | This directory is managed by the logging system. |

### Version Control

**Gitignored.** Log files are never committed.

### Log Inspection

```bash
# View recent logs
tail -f logs/pipeline.log

# Filter by module
cat logs/pipeline.log | jq 'select(.module == "src.scraper.client")'

# Filter by log level
cat logs/pipeline.log | jq 'select(.level == "ERROR")'

# Filter by pipeline run
cat logs/pipeline.log | jq 'select(.pipeline_run_id == "run_20260722_183000_two-sum")'
```

---

## 25. Git Version Control Rules

### `.gitignore` Specification

```gitignore
# ── Secrets ──────────────────────────────────────────
.env
config/client_secrets.json
config/youtube_token.json

# ── Runtime Data (generated artifacts) ──────────────
data/vector_store/
data/scraped/
data/tags/
data/rag/
data/scripts/
data/voice/
data/animation/
data/output/
data/uploads/
data/checkpoints/
data/memory/

# ── Model Files ─────────────────────────────────────
models/

# ── Logs ────────────────────────────────────────────
logs/

# ── Python ──────────────────────────────────────────
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.eggs/
*.egg

# ── Virtual Environment ────────────────────────────
.venv/
venv/
env/

# ── IDE ─────────────────────────────────────────────
.vscode/
.idea/
*.swp
*.swo
*~

# ── OS ──────────────────────────────────────────────
.DS_Store
Thumbs.db
```

### What IS Committed

| Path | Reason |
|---|---|
| `src/` | All source code |
| `tests/` | All test code |
| `config/pipeline.yaml` | Non-secret configuration |
| `config/logging.yaml` | Logging configuration |
| `data/knowledge_base/` | Human-curated educational content |
| `voice_samples/` | Voice reference audio |
| `PromptBook/` | Project documentation |
| `scripts/` | Developer utility scripts |
| `.env.example` | Onboarding template |
| `pyproject.toml` | Dependencies and tool config |
| `README.md` | Project overview |
| `.gitignore` | Exclusion rules |

### What is NOT Committed

| Path | Reason |
|---|---|
| `.env` | Contains API keys and session cookies |
| `config/client_secrets.json` | Contains OAuth client secret |
| `config/youtube_token.json` | Contains OAuth access/refresh tokens |
| `data/*` (except `knowledge_base/`) | Generated runtime artifacts |
| `models/` | Large binary model files |
| `logs/` | Runtime log output |

---

## 26. Directory Rules Summary

### The Five Laws of Directory Structure

**Law 1: Single Ownership.**  
Every directory is owned by exactly one concern. No directory serves two masters.

**Law 2: No Lateral Dependencies.**  
Pipeline module directories (`src/scraper/`, `src/tags/`, etc.) never import from each other. They communicate only through `src/models/` dataclasses.

**Law 3: Leaf Packages Have No Internal Dependencies.**  
`src/models/` and `src/core/` depend only on the Python standard library and third-party packages. They never import from pipeline modules.

**Law 4: Downward-Only Dependencies.**  
Layer 4 (entry points) → Layer 3 (pipeline modules) → Layer 2 (shared services) → Layer 1 (domain models). No upward arrows.

**Law 5: Tests Mirror Source.**  
Every source directory under `src/` has a corresponding `test_` directory under `tests/` with matching file structure.

### Quick Reference: Where Does This File Go?

| I need to... | It goes in... |
|---|---|
| Define a new dataclass for inter-module data | `src/models/{domain}.py` |
| Define a new Protocol interface | `src/models/protocols.py` |
| Define a new enum | `src/models/enums.py` |
| Create a new custom exception | `src/core/exceptions.py` |
| Add a shared utility function | `src/core/{utility}.py` |
| Implement a pipeline module | `src/{module_name}/{implementation}.py` |
| Write a test | `tests/test_{module_name}/test_{file}.py` |
| Add test fixtures | `tests/test_{module_name}/conftest.py` |
| Add a configuration parameter | `src/core/config.py` + `config/pipeline.yaml` |
| Add educational content for RAG | `data/knowledge_base/{topic}.md` |
| Store a module's output | `data/{module_output_dir}/{slug}...` |
| Add a developer script | `scripts/{name}.sh` |
| Add a project specification | `PromptBook/{number}_{Name}.md` |
| Add a new AI model file | `models/{model_name}/` |

---

**End of Directory Specification (`04_Folder_Structure.md`).**
