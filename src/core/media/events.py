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
