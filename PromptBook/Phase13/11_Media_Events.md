# Phase 13 / 11: Media Production Events

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Event Architecture & Integration](#2-event-architecture--integration)
3. [Source Code: `src/core/media/events.py`](#3-source-code-srccoremediaeventspy)

---

# 1. Executive Summary

As defined in the v2.0 Architecture, modules do not communicate by passing references or injecting dependencies across Phase boundaries. Instead, they interact via the **Event Bus**.

The **Media Production Events** defined here represent the physical progress of the rendering and publishing pipeline. By emitting these events, the Orchestrator allows the **Monitoring Subsystem** to track progress, the **Analytics Engine** to calculate total GPU time, and the **Plugin Platform** to trigger external webhooks (like posting a Slack message when `VideoPublished` is emitted) without tightly coupling the FFmpeg module to the Slack API.

---

# 2. Event Architecture & Integration

### Standard Payload Rules
Every event strictly implements a common `EventMetadata` block to guarantee traceability across distributed systems:
- `event_id`: UUID for deduplication.
- `timestamp`: UTC ISO-8601 for chronological ordering.
- `correlation_id`: The ID of the original `PipelineRun`. Every single event from Phase 09 to Phase 13 shares this ID, allowing logs to be traced across the entire 12-hour run.

### Publisher / Subscriber Mapping
| Event Name | Publisher | Target Subscribers |
| :--- | :--- | :--- |
| `VoiceGenerated` | `VoiceProviderProtocol` | Metrics System (Audio cost tracking), Checkpoint Manager |
| `AnimationPrepared` | `AnimationProviderProtocol`| UI Dashboard (Progress bar update) |
| `SceneRendered` | `ManimRenderer` | UI Dashboard, Checkpoint Manager (Incremental caching) |
| `SubtitlesCreated` | `SubtitleProviderProtocol` | Metadata Indexer |
| `VideoAssembled` | `FFmpegVideoAssembler` | Checkpoint Manager, Publishing Service |
| `ThumbnailGenerated` | `ThumbnailProviderProtocol`| Publishing Service |
| `VideoPublished` | `PublishProviderProtocol` | Plugin System (Slack/Twitter Webhooks), Analytics System |
| `PublishingFailed` | `PublishProviderProtocol` | Dead Letter Queue (DLQ), PagerDuty Alerting |

---

# 3. Source Code: `src/core/media/events.py`

```python
"""
Media Production Event Definitions (Phase 13)

Defines the core Event types emitted by the Media Production Platform
to integrate cleanly with the global Event Bus. 
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class EventMetadata:
    """Standardized metadata block required for all Media Events to ensure traceability."""
    event_id: str
    correlation_id: str  # Ties this event back to the original Pipeline Run ID
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0"


class MediaEvent:
    """Marker base class for all Phase 13 Media Events."""
    metadata: EventMetadata


# ---------------------------------------------------------
# Artifact Generation Events
# ---------------------------------------------------------

@dataclass
class VoiceGenerated(MediaEvent):
    """Emitted when all TTS voice tracks for a video have been physically generated to disk."""
    metadata: EventMetadata
    video_id: str
    total_segments: int
    audio_format: str
    duration_ms: int
    artifact_ids: List[str]


@dataclass
class AnimationPrepared(MediaEvent):
    """Emitted when animation boundaries are synchronized, signaling the start of Manim rendering."""
    metadata: EventMetadata
    video_id: str
    total_scenes: int
    estimated_render_time_sec: int


@dataclass
class SceneRendered(MediaEvent):
    """Emitted when an individual Manim scene completes (Critical for UI Progress Bars)."""
    metadata: EventMetadata
    video_id: str
    scene_index: int
    total_scenes: int
    artifact_id: str


@dataclass
class SubtitlesCreated(MediaEvent):
    """Emitted when SRT/VTT subtitle files are generated via force-alignment."""
    metadata: EventMetadata
    video_id: str
    languages: List[str]
    artifact_ids: List[str]


@dataclass
class ThumbnailGenerated(MediaEvent):
    """Emitted when the thumbnail is rendered and validated (Size < 2.0 MB)."""
    metadata: EventMetadata
    video_id: str
    template_id: str
    artifact_id: str


@dataclass
class VideoAssembled(MediaEvent):
    """Emitted when FFmpeg successfully multiplexes all assets into the final payload."""
    metadata: EventMetadata
    video_id: str
    resolution: str
    file_size_bytes: int
    artifact_id: str


# ---------------------------------------------------------
# Publishing & Platform Events
# ---------------------------------------------------------

@dataclass
class VideoPublished(MediaEvent):
    """Emitted when the YouTube Data API confirms successful remote ingestion."""
    metadata: EventMetadata
    video_id: str
    youtube_video_id: str
    platform: str
    url: str


@dataclass
class PublishingFailed(MediaEvent):
    """Emitted if the publishing process exhausts all retry/backoff attempts."""
    metadata: EventMetadata
    video_id: str
    platform: str
    error_code: str
    error_message: str
    attempt: int
```
