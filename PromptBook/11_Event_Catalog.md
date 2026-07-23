# 11_Event_Catalog.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Designed  

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Data Ingestion & Reasoning (Scraper, RAG, Tag, Memory)](#2-data-ingestion--reasoning)
3. [Content Generation (Script, Voice, Animation)](#3-content-generation)
4. [Assembly & Distribution (FFmpeg, Upload)](#4-assembly--distribution)
5. [System & Orchestration (Pipeline, Config, Plugins, Health)](#5-system--orchestration)
6. [Observability & Future (Analytics, Discord, SEO)](#6-observability--future)

---

# 1. Executive Summary

This **Master Event Catalog** defines the strict contracts (schemas) for every asynchronous interaction within the Event-Driven Architecture. By standardizing the Event Name, Payload, and Lifecycle constraints, we guarantee that independent developers can author plugins (Subscribers) without needing to inspect the underlying source code of the Publishers.

Events follow a standard dot-notation namespace protocol: `[domain].[version].[action]`.

---

# 2. Data Ingestion & Reasoning

Events related to gathering problem data, searching vector stores, and updating the systemic memory graph.

### 2.1 `scraper.v1.problem_scraped`
- **Purpose:** Emitted when a LeetCode problem has been successfully scraped, parsed, and normalized into Markdown.
- **Publisher:** Scraper Plugin
- **Subscribers:** Tag Explorer Plugin, RAG Plugin, Analytics Plugin
- **Payload:** `{"slug": "string", "title": "string", "difficulty": "string", "raw_content": "string", "source_url": "string"}`
- **Priority:** 5 (Normal)
- **Retry Policy:** None (Fire and forget)
- **Ordering:** Unordered (Triggers parallel Tag & RAG execution)
- **Persistence:** True (Saved to Event Log)
- **Expected Frequency:** 1 per pipeline run
- **Failure Behaviour:** If subscriber fails, Event Bus pushes to DLQ.
- **Monitoring:** Track `payload_size_bytes`.
- **Version / Deprecation:** `1.0.0` / Retain indefinitely.

### 2.2 `tag.v1.tags_extracted`
- **Purpose:** Emitted when the AI identifies and validates algorithmic tags from the raw problem.
- **Publisher:** Tag Explorer Plugin
- **Subscribers:** RAG Plugin, Memory Plugin
- **Payload:** `{"slug": "string", "tags": ["array", "two-pointers"], "confidence": "float"}`
- **Priority:** 5 (Normal)
- **Retry Policy:** 3 retries (Exponential backoff on LLM timeout)
- **Ordering:** Must precede `rag.v1.context_ready`
- **Persistence:** True
- **Expected Frequency:** 1 per pipeline run
- **Failure Behaviour:** Re-route to DLQ; Pipeline degradation (RAG will proceed with default context).
- **Monitoring:** Track LLM token usage and latency.
- **Version / Deprecation:** `1.0.0` / Deprecate if tags move to an external graph DB API.

### 2.3 `rag.v1.context_ready`
- **Purpose:** Emitted when ChromaDB retrieval is complete and educational context is formatted.
- **Publisher:** RAG Context Builder
- **Subscribers:** Script Generator Plugin
- **Payload:** `{"slug": "string", "retrieved_chunks": ["string"], "educational_plan": "string"}`
- **Priority:** 5 (Normal)
- **Retry Policy:** None
- **Ordering:** Follows `scraper.v1.problem_scraped`
- **Persistence:** True
- **Expected Frequency:** 1 per pipeline run
- **Failure Behaviour:** Emit `pipeline.v1.fatal_error`.
- **Monitoring:** Track context window size (tokens).
- **Version / Deprecation:** `1.0.0` / Keep stable.

### 2.4 `memory.v1.graph_updated`
- **Purpose:** Emitted when a problem's relationships are permanently written to the Knowledge Graph.
- **Publisher:** Memory Plugin
- **Subscribers:** Analytics Plugin
- **Payload:** `{"slug": "string", "nodes_added": "int", "edges_added": "int"}`
- **Priority:** 8 (Low)
- **Retry Policy:** 5 retries (Database write locks)
- **Ordering:** Unordered (Background task)
- **Persistence:** False
- **Expected Frequency:** 1 per pipeline run
- **Failure Behaviour:** Drop quietly (Graph can be rebuilt).
- **Monitoring:** Track database write times.
- **Version / Deprecation:** `1.0.0` / Stable.

---

# 3. Content Generation

Events handling the heavy, time-consuming AI generation tasks.

### 3.1 `script.v1.generation_complete`
- **Purpose:** Emitted when the final YouTube script (Voiceover + Visual cues) is validated by Gemini.
- **Publisher:** Script Generator Plugin
- **Subscribers:** Voice Plugin, Animation Plugin, Subtitle Plugin, SEO Plugin
- **Payload:** `{"slug": "string", "voiceover_text": "string", "visual_cues": ["dict"], "duration_estimate_sec": "int"}`
- **Priority:** 4 (Elevated - unlocks heavy parallel tasks)
- **Retry Policy:** 3 retries (LLM API rate limits)
- **Ordering:** Precedes all Media creation
- **Persistence:** True (Critical persistence point)
- **Expected Frequency:** 1 per pipeline run
- **Failure Behaviour:** Emit `pipeline.v1.fatal_error`.
- **Monitoring:** LLM Token usage, moderation flags.
- **Version / Deprecation:** `1.0.0` / Major schema changes expected in `v2` for multi-actor scripts.

### 3.2 `voice.v1.audio_rendered`
- **Purpose:** Emitted when the TTS engine completes rendering the voiceover.
- **Publisher:** Voice Generator Plugin
- **Subscribers:** FFmpeg Plugin, Speech Recognition Plugin (for sync)
- **Payload:** `{"slug": "string", "audio_path": "string", "duration": "float"}`
- **Priority:** 5 (Normal)
- **Retry Policy:** 3 retries (TTS API timeouts)
- **Ordering:** Parallel to Animation
- **Persistence:** True
- **Expected Frequency:** 1 per pipeline run
- **Failure Behaviour:** Halt video build; push to DLQ.
- **Monitoring:** External API latency, audio file size.
- **Version / Deprecation:** `1.0.0` / Stable.

### 3.3 `animation.v1.render_complete`
- **Purpose:** Emitted when Manim finishes compiling Python visual cues into an MP4.
- **Publisher:** Animation Plugin
- **Subscribers:** FFmpeg Plugin
- **Payload:** `{"slug": "string", "video_path": "string", "resolution": "string"}`
- **Priority:** 5 (Normal)
- **Retry Policy:** None (Local compute, fail fast)
- **Ordering:** Parallel to Voice
- **Persistence:** True
- **Expected Frequency:** 1 per pipeline run
- **Failure Behaviour:** Halt pipeline; emit `pipeline.v1.fatal_error`.
- **Monitoring:** Render duration (Critical metric).
- **Version / Deprecation:** `1.0.0` / Stable.

---

# 4. Assembly & Distribution

Events involving heavy OS-level media manipulation and network uploads.

### 4.1 `builder.v1.video_assembled`
- **Purpose:** Emitted when FFmpeg successfully merges Voice, Animation, and Background Music.
- **Publisher:** FFmpeg Video Builder Plugin
- **Subscribers:** Upload Plugin, Thumbnail Plugin
- **Payload:** `{"slug": "string", "final_video_path": "string", "filesize_mb": "float", "duration": "float"}`
- **Priority:** 3 (High - large file artifacts exist)
- **Retry Policy:** 1 retry (Filesystem race conditions)
- **Ordering:** Follows both Voice and Animation completion
- **Persistence:** True
- **Expected Frequency:** 1 per pipeline run
- **Failure Behaviour:** Purge corrupted partial outputs; DLQ.
- **Monitoring:** FFmpeg memory usage, CPU load.
- **Version / Deprecation:** `1.0.0` / Stable.

### 4.2 `upload.v1.youtube_published`
- **Purpose:** Emitted when the video goes live on YouTube.
- **Publisher:** Upload Plugin
- **Subscribers:** Discord Announcer, Telegram Announcer, Website Sync, Analytics
- **Payload:** `{"slug": "string", "youtube_url": "string", "video_id": "string", "status": "string"}`
- **Priority:** 2 (Very High - external visibility achieved)
- **Retry Policy:** 5 retries (Exponential backoff for OAuth/Network errors)
- **Ordering:** Terminal event for primary pipeline
- **Persistence:** True
- **Expected Frequency:** 1 per pipeline run
- **Failure Behaviour:** DLQ immediately. Do not lose the assembled video.
- **Monitoring:** Network upload speed.
- **Version / Deprecation:** `1.0.0` / Stable.

---

# 5. System & Orchestration

Events controlling the state of the overall application architecture.

### 5.1 `pipeline.v1.started` / `pipeline.v1.completed` / `pipeline.v1.fatal_error`
- **Purpose:** Master state machine events.
- **Publisher:** Orchestrator / Lifecycle Manager
- **Subscribers:** Logging Plugin, Discord Announcer (for alerts), Health Plugin
- **Payload:** `{"run_id": "string", "slug": "string", "timestamp": "float", "reason": "string (if error)"}`
- **Priority:** 0 (Critical)
- **Retry Policy:** None
- **Ordering:** N/A
- **Persistence:** True
- **Expected Frequency:** 1 set per run
- **Failure Behaviour:** Hard exit.
- **Monitoring:** Pipeline success/failure ratio.
- **Version / Deprecation:** `1.0.0` / Core system event.

### 5.2 `plugin.v1.registered` / `plugin.v1.unregistered`
- **Purpose:** Emitted when a new Plugin is dynamically loaded or unloaded into the Registry.
- **Publisher:** Plugin Manager
- **Subscribers:** Health Plugin, Config Plugin
- **Payload:** `{"plugin_name": "string", "version": "string"}`
- **Priority:** 1 (System)
- **Retry Policy:** None
- **Ordering:** Startup only
- **Persistence:** False
- **Expected Frequency:** Rare (Startup/Shutdown)
- **Failure Behaviour:** N/A
- **Monitoring:** Plugin inventory drift.
- **Version / Deprecation:** `1.0.0` / Stable.

### 5.3 `config.v1.reloaded`
- **Purpose:** Emitted if environment variables or secrets are hot-swapped during runtime.
- **Publisher:** Config Plugin
- **Subscribers:** All active Plugins
- **Payload:** `{"changed_keys": ["string"]}`
- **Priority:** 0 (Critical - stops inflight work)
- **Retry Policy:** None
- **Ordering:** Immediate processing
- **Persistence:** False
- **Expected Frequency:** Very Rare
- **Failure Behaviour:** Panic if a plugin fails to parse the new config.
- **Monitoring:** Config drift.
- **Version / Deprecation:** `1.0.0` / Stable.

---

# 6. Observability & Future

Events destined for external systems and future roadmap expansions.

### 6.1 `social.v1.discord_announced`
- **Purpose:** Emitted when a Discord webhook fires notifying the community.
- **Publisher:** Discord Plugin (Future)
- **Subscribers:** Analytics Plugin
- **Payload:** `{"slug": "string", "message_id": "string", "channel": "string"}`
- **Priority:** 8 (Low)
- **Retry Policy:** 3 retries (Discord rate limits `HTTP 429`)
- **Ordering:** Follows `youtube_published`
- **Persistence:** False
- **Expected Frequency:** 1 per pipeline
- **Failure Behaviour:** Drop quietly.
- **Monitoring:** Rate limit exhaustion.
- **Version / Deprecation:** `1.0.0` / Stable.

### 6.2 `metadata.v1.seo_generated`
- **Purpose:** AI generates rich keywords, chapters, and descriptions.
- **Publisher:** SEO Plugin (Future)
- **Subscribers:** Upload Plugin, Website Sync
- **Payload:** `{"slug": "string", "description": "string", "tags": ["string"], "chapters": ["dict"]}`
- **Priority:** 5 (Normal)
- **Retry Policy:** 3 retries (LLM API)
- **Ordering:** Must precede `builder.v1.video_assembled` (if burned into video) or `upload.v1.youtube_published`
- **Persistence:** True
- **Expected Frequency:** 1 per pipeline
- **Failure Behaviour:** Degrade gracefully (Upload Plugin uses default boilerplate text).
- **Monitoring:** SEO token cost.
- **Version / Deprecation:** `1.0.0` / Stable.
