# Context: Project Roadmap (`roadmap.md`)

This document outlines the implementation phases, deliverables, and verification checkpoints for the Automated DSA Educational YouTube Video Automation Pipeline.

---

## Roadmap Phases

### Phase 1: Infrastructure & Scraper Foundation
- Setup project configuration (`config/settings.yaml`, `config/theme.py`, `.env`).
- Implement `LeetCodeClient` GraphQL API scraper to extract user accepted C++ solutions & problem metadata.
- Setup unit test suite with mock GraphQL responses.

### Phase 2: Knowledge Base & Script Engine
- Initialize local ChromaDB vector store and LlamaIndex node parsers under `data/vector_store/`.
- Implement `TagExplorer` for technique extraction (Two Pointers, Graphs, DP).
- Implement `ScriptGenerator` to synthesize 10-section educational JSON scripts via Gemini API.

### Phase 3: Hybrid Voice Engine
- Implement `VoiceSynthesizer` with Kokoro-82M OpenVINO CPU/NPU engine (`--voice cloned`).
- Implement section teleprompter and custom WAV ingestion pipeline (`--voice record`).

### Phase 4: Animation Engine (Manim CE)
- Implement dark theme palette tokens (`#0f0f23`, `#00d4ff`, `#e0e0e0`).
- Build reusable scene templates: `StepFlow`, `LinkedListScene`, `CodeTyping`.

### Phase 5: Assembly, SEO & Memory System
- Implement `VideoAssembler` using `ffmpeg-python` for audio/video sync and background track mixing.
- Implement `YouTubeUploader` with automated SEO metadata and private upload defaults.
- Implement `MemorySystem` to persist problem JSON representations under `data/memory/`.

### Phase 6: Prototype End-to-End Execution — LeetCode #143 Reorder List
- **Prototype Problem:** LeetCode #143 "Reorder List"
- **Solution Strategy:** C++ Fast & Slow Pointer → Reverse Second Half → Interleave Merge
- **Solution URL:** `https://leetcode.com/problems/reorder-list/solutions/4163684/fast-and-slow-pointer-approach-by-ad18-8xoq/`
- **Verification Criteria:**
  1. Scraper extracts AD18's C++ solution.
  2. RAG engine retrieves Fast & Slow pointer intuition.
  3. Voice engine generates narration in under 5 minutes on Intel CPU.
  4. Manim renders 10-section visual video including node pointer animations and code typing.
  5. Video uploads privately to YouTube with chapters, tags, description, and thumbnail.
