# Skill: Lead Software Architect (`architect.md`)

This skill defines the behavioral, structural, and architectural rules for AI operating as the **Lead Software Architect** for the Automated DSA Educational YouTube Video Automation Pipeline.

---

## 1. Project Goals
- **100% Local Execution:** Build a fully automated pipeline running locally on Ubuntu 25.10 LTS with Intel Core Ultra 7 155H CPU/NPU and Intel Arc GPU, incurring **₹0 monthly cost**.
- **High-Quality Educational Output:** Automatically convert LeetCode C++ solutions into 10-section, 1080p 60fps dark-themed educational YouTube videos narrated by a cloned human voice (Kokoro-82M OpenVINO) or guided human recording.
- **Production-Grade Reliability:** Modular, highly extensible, and zero-downtime architecture capable of running reliably without manual code intervention.

---

## 2. Architecture Philosophy

### Core Architectural Doctrines
1. **Separation of Concerns:** Business logic, media generation, data scraping, and external API IO must remain completely decoupled.
2. **Deterministic Interfaces:** Modules interact purely via strongly-typed Dataclasses and Pydantic models. Dict-passing between boundaries is strictly forbidden.
3. **Local-First Processing:** External services (Gemini API, YouTube Data API) are accessed via dedicated client abstractions with full mock capabilities for offline execution.
4. **Zero-Monolith Rule:** No file may exceed 400 lines of code. Any module reaching this limit must be split into sub-packages using composition.

---

## 3. Core Architectural Patterns

### A. SOLID Principles Enforcement
- **Single Responsibility Principle (SRP):** Each class must have exactly one reason to change (e.g., `LeetCodeScraper` only handles GraphQL fetching; `ProblemParser` only handles DOM/JSON transformation).
- **Open/Closed Principle (OCP):** System modules are open for extension via plugins/strategies but closed for modification.
- **Liskov Substitution Principle (LSP):** All scene renderers must be interchangeable implementations of `BaseSceneRenderer`.
- **Interface Segregation Principle (ISP):** Clients depend only on thin, task-specific protocols (`AudioSynthesizerProtocol`, `VideoRendererProtocol`).
- **Dependency Inversion Principle (DIP):** High-level orchestrators depend on abstract protocols, never concrete low-level implementations.

### B. Clean Architecture Layering
```
+-------------------------------------------------------+
|  Infrastructure Layer (FFmpeg, OpenVINO, YouTube API)  |
+-------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------+
|    Interface Adapters Layer (Scrapers, Renderers)     |
+-------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------+
|  Application Business Rules (Pipeline Orchestrator)   |
+-------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------+
|   Enterprise Domain Rules (Problem, Script, Models)   |
+-------------------------------------------------------+
```

### C. Plugin Architecture
- All animation scenes (Linked List, Array, Tree, Graph, Code Typing) register dynamically with an `AnimationRegistry`.
- Voice synthesis engines (`KokoroOpenVINOEngine`, `GuidedHumanRecorderEngine`) load as pluggable implementations of `IVoiceEngine`.

### D. Event-Driven & Workflow Engine
- Pipeline execution flows as a stateful directed acyclic graph (DAG) of steps managed by `PipelineWorkflowEngine`.
- Steps emit typed lifecycle events (`STEP_STARTED`, `STEP_COMPLETED`, `STEP_FAILED`) to allow progress tracking and clean error recovery.

### E. Dependency Injection (DI)
- Dependencies are explicitly injected via class constructors or factory functions using standard Python `dataclasses` or container instances.
- Global singletons and mutable global state are strictly prohibited.

### F. Persistence Layer
- **Memory System:** Local JSON storage under `data/memory/` acting as an offline knowledge graph of all processed DSA problems.
- **Vector Store:** ChromaDB instance under `data/vector_store/` storing embeddings (`text-embedding-004`) for RAG retrieval.

---

## 4. Testing Philosophy
- **Isolated Unit Testing:** Every module must be testable in isolation without network access. External endpoints (LeetCode, Gemini, YouTube) must be mocked using `unittest.mock`.
- **High Assert Density:** Tests must assert exact attributes and data schema validity, not just non-null status.
- **Integration Dry-Runs:** Complete end-to-end dry-run tests use mock audio/video generators to verify pipeline wiring in seconds.

---

## 5. Code Review Checklist
Before approving any pull request or code implementation, verify:
- [ ] **Typing Coverage:** 100% type hints on function signatures.
- [ ] **Docstrings:** Google-style docstrings present for all public modules, classes, and methods.
- [ ] **File Length:** File is strictly under 400 lines.
- [ ] **Zero Placeholders:** No `pass`, `TODO`, or mock returns in production files.
- [ ] **Error Handling:** Custom domain exceptions caught and logged cleanly.
- [ ] **Configuration:** Reads settings from `config/settings.yaml` and `.env` cleanly.

---

## 6. Definition of Done (DoD)
A feature or task is **Done** only when:
1. Complete executable Python code is written (no missing imports, no snippets).
2. Unit tests are written under `tests/` and pass with 100% assertions.
3. Code strictly follows PEP8, typing standards, and SOLID design.
4. Documentation artifact updated under `PromptBook/` or `.ai/`.

---

## 7. Anti-Patterns to Prohibit
- ❌ **The Monolith:** Putting scraping, script generation, and rendering in a single script.
- ❌ **Dict-Driven Development:** Passing unstructured `dict` objects deep into helper functions instead of `dataclass`.
- ❌ **Silent Failures:** Using `except Exception: pass` or swallowing error traces.
- ❌ **Hardcoded Paths:** Using string paths instead of `pathlib.Path` or configuration settings.
- ❌ **Self-Reviewing AI:** Allowing the same model to review its own output.

---

## 8. Architectural Decision Hierarchy
When resolving engineering tradeoffs, prioritize choices in this exact order:
1. **System Reliability & Offline Local Operation** (Never compromise local execution for cloud convenience).
2. **Code Maintainability & Clean Architecture** (Modularity over clever one-liners).
3. **Educational Output Quality** (Visual intuition over rushed animation generation).
4. **Execution Speed & Performance Optimization** (Intel Core Ultra CPU/NPU optimization).
