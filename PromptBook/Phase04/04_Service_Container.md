# Phase04/04_Service_Container.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Target Environment:** Intel Core Ultra 7 155H · Ubuntu 25.10 LTS · Python 3.12 · Intel Arc GPU  
**Document Version:** 2.0.0  
**Status:** Canonical — Supersedes v1.0.0 after architectural audit.

---

# 1. Architectural Decision: Removal of `ServiceContainer`

In the v1.0.0 architecture, the system utilized a `ServiceContainer` (or DI Container) to register, resolve, and manage the lifecycles of dependencies dynamically using classes, scopes, and `resolve()` methods.

This abstraction has been **completely removed** in the v2.0.0 canonical architecture.

## 1.1 Why `ServiceContainer` is Anti-Canonical

1. **No DI Frameworks (Rule 11.3):** The canonical architecture explicitly prohibits DI frameworks, container classes, `register()`, `resolve()`, and `Scope` concepts.
2. **Obfuscation of Wiring:** Service containers hide the explicit wiring of the application behind dynamic resolution, making it harder to track how modules are instantiated and connected.
3. **Overengineering:** For a fixed, single-batch 9-module pipeline, dynamic service resolution is unnecessary overhead. We know exactly which 9 modules exist at compile time.

---

# 2. The Canonical Equivalent: Manual Dependency Injection

The canonical architecture mandates **Manual Dependency Injection** inside a single **Composition Root** located entirely within `src/__main__.py`.

### 2.1 The Composition Root
All modules are manually instantiated with explicit dependencies (configuration sub-objects and loggers) and directly wired into the `PipelineOrchestrator`.

```python
# src/__main__.py — Composition Root

def main() -> None:
    config = load_config()
    logger = get_logger("pipeline")
    
    # 1. Manual instantiation of all modules (Constructor Injection)
    scraper = LeetCodeScraper(config.scraper, get_logger("scraper"))
    tags = GeminiTagExplorer(config.tags, get_logger("tags"))
    rag = ChromaRAGEngine(config.rag, get_logger("rag"))
    script = GeminiScriptGenerator(config.script, get_logger("script"))
    voice = KokoroVoiceSynthesizer(config.voice, get_logger("voice"))
    animation = ManimAnimationRenderer(config.animation, get_logger("animation"))
    assembly = FFmpegVideoAssembler(config.assembly, get_logger("assembly"))
    youtube = YouTubeAPIUploader(config.youtube, get_logger("youtube"))
    memory = JSONMemoryStore(config.memory, get_logger("memory"))

    # 2. Direct wiring into the orchestrator
    orchestrator = PipelineOrchestrator(
        config=config, 
        scraper=scraper, 
        tags=tags,
        rag=rag,
        script=script,
        voice=voice,
        animation=animation,
        assembly=assembly,
        youtube=youtube,
        memory=memory
    )
    
    # 3. Execution
    orchestrator.run(slug=parse_cli_args().slug)
```

### 2.2 Core Principles
- **No `@inject` decorators:** Dependencies are passed plainly via standard `__init__` arguments.
- **No `register(Interface, Concrete)`:** Concrete classes are imported and constructed directly in `__main__.py`.
- **No `resolve()`:** The orchestrator expects concrete instances directly.

---

# 3. Change Log
- **Removed DI Container:** Eliminated all service container logic, registration methods, and injection decorators.
- **Implemented Manual DI:** Consolidated all instantiation and wiring explicitly in `src/__main__.py`.
- **Eliminated Dynamic Resolution:** The system relies strictly on static, manually written constructor injections.
