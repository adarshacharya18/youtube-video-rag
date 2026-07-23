# Project: Media Production Platform Architecture (Phase 13)

## Architecture
Phase 13 establishes the Media Production Platform Architecture for the automated YouTube content generation pipeline.
It sits downstream of Educational Content Generation (Phase 12) and provides an asynchronous, event-driven, plugin-based architecture for multi-modal media rendering and assembly.

Components:
1. Voice Production Engine (Kokoro TTS, ElevenLabs, OpenAI Audio, TTS provider plugins)
2. Animation Production Engine (Manim Python engine, Blender, remotion, SVG/Canvas rendering plugins)
3. Subtitle Generation Engine (Whisper alignment, SRT/VTT/ASS generator, styled burnt-in/soft subtitles)
4. Video Assembly Pipeline (FFmpeg compositor, transition weaver, audio mixing, multi-track timeline)
5. Thumbnail Generation Service (Pillow, Playwright/SVG rendering, dynamic text overlay, preview generator)
6. Publishing Platform Manager (YouTube Data API v3 publisher, metadata tagger, schedule dispatcher)
7. Artifact Tracking & State Store (S3/Local storage manager, SHA-256 integrity verifier, DB metadata store)
8. Provider Abstraction Layer (Swappable provider interfaces with plugin SPI)
9. Resiliency, Metrics, & Monitoring (Exponential backoff retry, DLQ, Prometheus metrics, tracing)

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Research & System Mapping | Analyze existing docs (Phase 11, Phase 12, EDA, Workflow, Plugin SDK) | None | IN_PROGRESS |
| 2 | Media Architecture Drafting | Draft full architecture doc (`01_Media_Production_Architecture.md`) | M1 | PLANNED |
| 3 | Review & Forensic Audit | Verification by Reviewer and Forensic Auditor | M2 | PLANNED |

## Interface Contracts
- **Educational Content Platform Input**: Receives `EducationalContentPlan`, `StoryboardSpec`, `NarrationPlan`, `AnimationPlan`, `ScriptSpec`.
- **Plugin Platform SDK**: Implements `MediaProviderPlugin` SPI (`VoiceProvider`, `AnimationProvider`, `SubtitleProvider`, `ThumbnailProvider`, `PublisherProvider`).
- **Workflow Engine Integration**: Workflow engine triggers media production tasks, handles step state transitions, retries, and step outputs.
- **Event Bus Integration**: Consumes `ContentApprovedEvent`, `NarrationPlannedEvent`, `AnimationPlannedEvent`; publishes `VoiceGeneratedEvent`, `AnimationRenderedEvent`, `SubtitlesGeneratedEvent`, `VideoAssembledEvent`, `ThumbnailGeneratedEvent`, `MediaPublishedEvent`.
- **Persistence Layer Integration**: Artifact store (media files, audio, video chunks, thumbnails) and Postgres/SQLite metadata store for job state & tracking.
