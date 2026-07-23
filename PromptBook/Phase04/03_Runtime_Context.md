# Phase04/03_Runtime_Context.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Target Environment:** Intel Core Ultra 7 155H · Ubuntu 25.10 LTS · Python 3.12 · Intel Arc GPU  
**Document Version:** 2.0.0  
**Status:** Canonical — Supersedes v1.0.0 after architectural audit.

---

# 1. Architectural Decision: Removal of `RuntimeContext`

In the v1.0.0 architecture, the pipeline utilized a `RuntimeContext` (or `PipelineContext`) object to bundle execution parameters, run metadata, configuration, loggers, and filesystem paths, passing it through all pipeline stages.

This abstraction has been **completely removed** in the v2.0.0 canonical architecture.

## 1.1 Why `RuntimeContext` is Anti-Canonical

1. **God Object Anti-Pattern:** A context object inevitably grows to encompass unrelated concerns (configuration, filesystem paths, logger state, run IDs), coupling modules to a massive global state object.
2. **Obfuscated Dependencies:** When a module receives a generic `context`, its actual dependencies are hidden. A `VoiceSynthesizer` needs `VoiceConfig`, not the entire `PipelineContext`.
3. **Violation of Canonical Injection:** The architecture mandates passing explicit `config` and `logger` to constructors, and specific runtime arguments (like `slug`) strictly to the execution methods (e.g., `run()`).

---

# 2. The Canonical Equivalent

Instead of passing a generic runtime context object across the application, the pipeline strictly relies on **direct dependency injection** and **explicit parameter passing**.

### 2.1 Constructor Injection (Static Dependencies)
Static dependencies such as configuration subset models and bound loggers are provided to each module purely at instantiation within the single composition root (`src/__main__.py`). Modules do not receive the global `PipelineConfig`, only their specific configuration node.

```python
# Canonical Module Instantiation in src/__main__.py
scraper = LeetCodeScraper(config.scraper, get_logger("scraper"))
voice = KokoroVoiceSynthesizer(config.voice, get_logger("voice"))
```

### 2.2 Method Injection (Runtime Parameters)
Runtime variables (such as the problem `slug`) are passed directly as primitive arguments to the orchestrator's `run()` method, which orchestrates module calls using those arguments.

```python
# Canonical Orchestrator Execution
orchestrator = PipelineOrchestrator(
    config=config,
    scraper=scraper,
    voice=voice,
    # ... other modules ...
)

# Execution parameter 'slug' is passed directly, not wrapped in a context object
orchestrator.run(slug=args.slug)
```

### 2.3 Filesystem Paths
Path management is no longer pre-computed and stored in a context object. Instead, modules dynamically construct their paths utilizing functions from `src.core.paths` combined with base directories defined in their immutable configuration.

---

# 3. Change Log
- **Removed `PipelineContext`:** Completely eliminated `src/domain/context.py`.
- **Enforced Explicit Dependencies:** Modules now explicitly require their specific configuration subset (e.g., `VoiceConfig`) and a standard structured logger.
- **Simplified State Tracking:** Modules act as purely stateless functional components, removing the need for a shared context object to manage state across the pipeline.
