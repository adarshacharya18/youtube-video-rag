# Phase 12 / 11: Content Generation Telemetry Events

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/script/events.py`](#2-source-code-srccorescripteventspy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

As explicitly mandated by the Phase 04 architectural review, the pipeline operates as a **synchronous batch process**, not an asynchronous event-driven workflow. Therefore, these events are strictly **fire-and-forget telemetry payloads** used for external observability (Grafana Dashboards) and performance monitoring. They do *not* trigger downstream business logic or require Dead Letter Queues.

By emitting these events, DevOps engineers can track the exact LLM latency, token counts, and review rejection rates of the Content Generation platform in real-time.

---

# 2. Source Code: `src/core/script/events.py`

```python
"""
Telemetry Events for the Content Generation Pipeline.

These events are strictly for non-blocking observability (e.g., Grafana dashboards).
They DO NOT control business logic or sequence execution, adhering to the 
synchronous batch-pipeline architecture defined in Phase 04.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ContentEvent:
    """Base telemetry event for Content Generation."""
    slug: str
    version: str = "1.0"


@dataclass(frozen=True)
class TeachingPlanCreated(ContentEvent):
    """Emitted when the Educational Planner successfully structures the RAG context."""
    objectives_count: int
    difficulty_level: str


@dataclass(frozen=True)
class StoryboardGenerated(ContentEvent):
    """Emitted when the Storyboard determines visual pacing."""
    scene_count: int
    estimated_duration_sec: int


@dataclass(frozen=True)
class NarrationPlanned(ContentEvent):
    """Emitted when the SSML and spoken English prose are finalized."""
    total_word_count: int
    estimated_audio_duration_sec: int


@dataclass(frozen=True)
class AnimationPlanned(ContentEvent):
    """Emitted when the JSON semantic visual actions are finalized."""
    total_visual_actions: int


@dataclass(frozen=True)
class ScriptGenerated(ContentEvent):
    """Emitted when the Compiler merges all ASTs into a single JSON."""
    payload_size_bytes: int


@dataclass(frozen=True)
class ContentReviewed(ContentEvent):
    """Emitted after the LLM-as-a-Judge inspects the final script for hallucinations."""
    is_approved: bool
    overall_score: int
    critical_findings_count: int


@dataclass(frozen=True)
class ContentExported(ContentEvent):
    """Emitted when the ZIP package and checksum manifest are written to disk."""
    archive_path: str
    checksum: str
```

---

# 3. Design Decisions

1. **Strictly Observability Bound:** These events are exclusively `Subscribed` to by the `RAGMonitor` daemon (Phase 11). They are published via `fire_and_forget` semantics. If the Event Bus crashes or a subscriber is slow, the synchronous batch pipeline continues unhindered.
2. **Actionable Metrics:** The payloads are extremely small, containing only integers and booleans (`total_word_count`, `is_approved`). We never emit the actual massive string payload into the telemetry bus, saving immense memory and I/O overhead.
3. **Review Rejection Tracking (`ContentReviewed`):** By tracking `is_approved` and `critical_findings_count`, DevOps can set up Grafana alerts. If `is_approved == False` spikes across 5 consecutive videos, it indicates that Google Gemini's underlying model has likely drifted and is hallucinating math at a higher rate, requiring prompt tuning.
