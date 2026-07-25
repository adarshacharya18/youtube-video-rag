"""Asset references and video rendering manifest models."""

from datetime import datetime
import math
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class AssetReference(BaseModel):
    """Reference to an external or internal media asset."""

    asset_id: str = Field(...)
    asset_type: str = Field(...)
    file_path: str = Field(...)
    duration: float | None = Field(default=None, gt=0.0)

    @field_validator("duration", mode="before")
    @classmethod
    def validate_finite_float(cls, v: Any) -> Any:
        """Ensure float field is a finite number."""
        if v is not None:
            try:
                fv = float(v)
            except (ValueError, TypeError):
                return v
            if not math.isfinite(fv):
                raise ValueError("Float field must be a finite number")
        return v

    @field_validator("asset_id", "asset_type", "file_path")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-empty and non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v


class AudioAsset(BaseModel):
    """Audio track asset representation."""

    audio_id: str = Field(...)
    file_path: str = Field(...)
    duration_seconds: float = Field(..., gt=0.0)
    sample_rate: int = Field(default=24000, gt=0)
    voice_model: str = Field(default="kokoro")

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def validate_finite_float(cls, v: Any) -> Any:
        """Ensure float field is a finite number."""
        if v is not None:
            try:
                fv = float(v)
            except (ValueError, TypeError):
                return v
            if not math.isfinite(fv):
                raise ValueError("Float field must be a finite number")
        return v

    @field_validator("audio_id", "file_path", "voice_model")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v


class VideoAsset(BaseModel):
    """Video segment/clip asset representation."""

    asset_id: str = Field(...)
    file_path: str = Field(...)
    duration_seconds: float = Field(..., gt=0.0)
    resolution: str = Field(default="1920x1080")
    fps: int = Field(default=30, gt=0, le=120)
    file_size_bytes: int = Field(default=0, ge=0)

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def validate_finite_float(cls, v: Any) -> Any:
        """Ensure float field is a finite number."""
        if v is not None:
            try:
                fv = float(v)
            except (ValueError, TypeError):
                return v
            if not math.isfinite(fv):
                raise ValueError("Float field must be a finite number")
        return v

    @field_validator("asset_id", "file_path", "resolution")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v


class RenderSegment(BaseModel):
    """Individual segment in a video rendering manifest."""

    segment_id: str = Field(...)
    segment_type: str = Field(...)
    start_time: float = Field(default=0.0, ge=0.0)
    end_time: float = Field(..., gt=0.0)
    duration: float = Field(..., gt=0.0)
    asset_references: list[AssetReference] = Field(default_factory=list)
    audio_path: str | None = Field(default=None)
    visual_path: str | None = Field(default=None)
    narration_text: str | None = Field(default=None)
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    transition_in: str | None = Field(default=None)
    transition_out: str | None = Field(default=None)
    audio_asset: AudioAsset | None = Field(default=None)
    scene_type: str | None = Field(default=None)
    visual_parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("start_time", "end_time", "duration", "volume", mode="before")
    @classmethod
    def validate_finite_float(cls, v: Any) -> Any:
        """Ensure float fields are finite numbers."""
        if v is not None:
            try:
                fv = float(v)
            except (ValueError, TypeError):
                return v
            if not math.isfinite(fv):
                raise ValueError("Float field must be a finite number")
        return v

    @field_validator("segment_id")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure segment_id is non-whitespace."""
        if not v or not v.strip():
            raise ValueError("segment_id cannot be empty or whitespace-only")
        return v

    @field_validator("segment_type")
    @classmethod
    def validate_segment_type(cls, v: str) -> str:
        """Ensure segment_type is one of the allowed set."""
        allowed = {"intro", "code_walkthrough", "visual_anim", "outro", "narration"}
        if v not in allowed:
            raise ValueError(f"segment_type '{v}' must be one of {allowed}")
        return v

    @model_validator(mode="after")
    def validate_segment_invariants(self) -> "RenderSegment":
        """Validate start/end timing, duration calculation, and presence of at least one asset reference."""
        if self.end_time <= self.start_time:
            raise ValueError(f"end_time ({self.end_time}) must be greater than start_time ({self.start_time})")

        expected_duration = self.end_time - self.start_time
        if abs(self.duration - expected_duration) > 1e-3:
            raise ValueError(
                f"duration ({self.duration}) must match end_time - start_time ({expected_duration}) within tolerance 1e-3"
            )

        has_asset_refs = bool(self.asset_references)
        has_audio_path = self.audio_path is not None and bool(self.audio_path.strip())
        has_visual_path = self.visual_path is not None and bool(self.visual_path.strip())
        has_audio_asset = self.audio_asset is not None

        if not (has_asset_refs or has_audio_path or has_visual_path or has_audio_asset):
            raise ValueError(
                "RenderSegment must contain at least one asset reference "
                "(audio_path, visual_path, asset_references, or audio_asset)"
            )
        return self


class RenderManifest(BaseModel):
    """Manifest describing complete render timeline for a video."""

    pipeline_run_id: str = Field(...)
    slug: str = Field(..., pattern=r"^[a-z0-9-]+$")
    segments: list[RenderSegment] = Field(...)
    total_duration: float = Field(..., gt=0.0)

    @field_validator("total_duration", mode="before")
    @classmethod
    def validate_finite_float(cls, v: Any) -> Any:
        """Ensure float field is a finite number."""
        if v is not None:
            try:
                fv = float(v)
            except (ValueError, TypeError):
                return v
            if not math.isfinite(fv):
                raise ValueError("Float field must be a finite number")
        return v

    @field_validator("pipeline_run_id")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure pipeline_run_id is non-whitespace."""
        if not v or not v.strip():
            raise ValueError("pipeline_run_id cannot be empty or whitespace-only")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Ensure slug strictly matches pattern ^[a-z0-9-]+$."""
        if not v or not v.strip():
            raise ValueError("Slug cannot be empty")
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(f"Slug '{v}' must match pattern ^[a-z0-9-]+$")
        return v

    @field_validator("segments")
    @classmethod
    def validate_segments_non_empty(cls, v: list[RenderSegment]) -> list[RenderSegment]:
        """Ensure segments list is non-empty."""
        if not v:
            raise ValueError("segments list cannot be empty")
        return v


class AssembledVideo(BaseModel):
    """Final assembled video metadata artifact."""

    slug: str = Field(..., pattern=r"^[a-z0-9-]+$")
    final_video_path: str = Field(...)
    thumbnail_path: str | None = Field(default=None)
    total_duration_seconds: float = Field(..., gt=0.0)
    file_size_bytes: int = Field(default=0, ge=0)
    segments: list[RenderSegment] = Field(default_factory=list)
    assembled_at: str | datetime | None = Field(default=None)

    @field_validator("total_duration_seconds", mode="before")
    @classmethod
    def validate_finite_float(cls, v: Any) -> Any:
        """Ensure float field is a finite number."""
        if v is not None:
            try:
                fv = float(v)
            except (ValueError, TypeError):
                return v
            if not math.isfinite(fv):
                raise ValueError("Float field must be a finite number")
        return v

    @field_validator("final_video_path")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure final_video_path is non-whitespace."""
        if not v or not v.strip():
            raise ValueError("final_video_path cannot be empty or whitespace-only")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Ensure slug strictly matches pattern ^[a-z0-9-]+$."""
        if not v or not v.strip():
            raise ValueError("Slug cannot be empty")
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(f"Slug '{v}' must match pattern ^[a-z0-9-]+$")
        return v
