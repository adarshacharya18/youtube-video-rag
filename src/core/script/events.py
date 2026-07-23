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
