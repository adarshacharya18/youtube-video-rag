# Phase03/02_Project_Structure.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Physical Directory Initialization](#2-physical-directory-initialization)
3. [Package Responsibilities](#3-package-responsibilities)
4. [File Classifications](#4-file-classifications)

---

# 1. Executive Summary

This document confirms the physical instantiation of the directory tree on the local filesystem as defined in `04_Folder_Structure.md`. Every `__init__.py`, module placeholder, configuration folder, test directory, and data sink has been successfully created. This guarantees that all imports are resolvable and the architectural boundaries are strictly enforced from Day 1.

---

# 2. Physical Directory Initialization

The following top-level directories have been provisioned:

- **`src/`**: The root Python package containing all production logic.
- **`tests/`**: The parallel test directory, maintaining a strict 1:1 mapping with the `src/` modules.
- **`config/`**: Stores YAML runtime configurations and secrets.
- **`data/`**: The runtime output sink, partitioned by module step (e.g., `data/scraped/`, `data/vector_store/`, `data/output/`).
- **`models/`**: Stores local AI models (e.g., Kokoro openvino weights).
- **`voice_samples/`**: Stores reference audio for voice cloning.
- **`scripts/`**: Shell scripts for developer workflows (`setup.sh`, `lint.sh`, etc.).
- **`logs/`**: Structured log output sink.
- **`examples/`**: Directory for sample inputs or outputs for demonstration purposes.
- **`docs/`**: Auxiliary project documentation (outside of the PromptBook).
- **`assets/`**: Static assets (thumbnails, channel art, static Manim images).
- **`data/cache/`**: Short-term disk cache for API responses (e.g., LeetCode queries).

---

# 3. Package Responsibilities

Inside the `src/` directory, the following sub-packages have been initialized with empty `__init__.py` markers and their constituent placeholder `.py` files.

### 3.1 Layer 1: Domain Models (`src/models/`)
The true leaf package. It contains purely declarative data structures (`ScrapedProblem`, `RAGContext`, `VideoScript`) and Protocol interfaces. 
- *Purpose*: Decouple modules by forcing them to depend on shared vocabulary rather than concrete implementations.

### 3.2 Layer 2: Shared Infrastructure (`src/core/`)
The near-leaf package. Contains `logger.py`, `config.py`, `exceptions.py`, and `serialization.py`.
- *Purpose*: Provide utilities that every module needs (like logging and path resolution) without causing circular dependencies.

### 3.3 Layer 3: Pipeline Modules
These are the independent workers of the Pipes and Filters architecture. They only import from `src/models/` and `src/core/`.

- **`src/scraper/`**: Extracts problem metadata and C++ code from the LeetCode GraphQL API.
- **`src/tags/`**: Explores algorithmic patterns and prerequisites using Gemini.
- **`src/rag/`**: Chunks, embeds, and retrieves educational context from the local Markdown knowledge base using ChromaDB.
- **`src/script/`**: Synthesizes the final video script, dictating the teaching flow, analogies, and pacing.
- **`src/voice/`**: Generates high-quality TTS audio clips for each script section using Kokoro.
- **`src/animation/`**: Renders dynamic, synchronized mathematical and data structure visuals using Manim. Contains a `scenes/` sub-package for specific data structure templates (e.g., `array_scene.py`).
- **`src/assembly/`**: Multiplexes audio and video streams together using FFmpeg.
- **`src/youtube/`**: Handles OAuth2 authentication and uploads the final artifact to the YouTube Data API.
- **`src/memory/`**: Persists the session state so future videos can reference past videos.

### 3.4 Layer 4: Composition Root (`src/orchestrator/` & `src/__main__.py`)
The top-level orchestrator.
- *Purpose*: `src/__main__.py` instantiates the concrete classes (e.g., `LeetCodeScraper`) and injects them into the `PipelineOrchestrator`, which manages the high-level workflow and checkpoints.

---

# 4. File Classifications

All placeholder files have been created. Examples of key files ready for implementation:

- `src/scraper/client.py`: Ready for HTTP transport logic.
- `src/animation/scenes/tree_scene.py`: Ready for Manim tree visualization logic.
- `tests/test_rag/test_engine.py`: Ready for ChromaDB mock tests.
- `src/models/protocols.py`: Ready to define the `Protocol` interfaces that bind the system together. 

The environment is now structurally complete. No files are missing, and no dynamic creation is required during runtime execution.
