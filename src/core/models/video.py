"""Video metadata and platform models for the automated video pipeline."""

from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class VideoResolution(StrEnum):
    """Supported video resolutions."""

    R_720P = "720p"
    R_1080P = "1080p"
    R_1440P = "1440p"
    R_4K = "4K"


class TargetPlatform(StrEnum):
    """Target platforms for video publishing."""

    YOUTUBE = "youtube"
    YOUTUBE_SHORTS = "youtube_shorts"
    TIKTOK = "tiktok"


class PrivacyStatus(StrEnum):
    """Privacy statuses for uploaded videos."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class Difficulty(StrEnum):
    """Problem difficulty levels."""

    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class SEOMetadata(BaseModel):
    """SEO metadata model for YouTube search optimization."""

    youtube_title: str = Field(..., min_length=1, max_length=100)
    youtube_description: str = Field(..., min_length=1, max_length=5000)
    tags: list[str] = Field(default_factory=list)
    category_id: int = Field(default=27)
    privacy_status: PrivacyStatus = Field(default=PrivacyStatus.PUBLIC)
    chapter_timestamps: list[dict[str, str]] = Field(default_factory=list)

    @field_validator("youtube_title", "youtube_description")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure title and description are not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        """Ensure tag list items are not empty or whitespace-only and total character count <= 500."""
        for tag in tags:
            if not tag or not tag.strip():
                raise ValueError("List item cannot be empty or whitespace only")
        total_chars = sum(len(tag) for tag in tags)
        if total_chars > 500:
            raise ValueError(f"Total tag characters ({total_chars}) exceeds limit of 500")
        return tags


class VideoMetadata(BaseModel):
    """Core video metadata model aligned with pipeline state ledger."""

    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=5000)
    slug: str = Field(..., pattern=r"^[a-z0-9-]+$")
    resolution: VideoResolution = Field(default=VideoResolution.R_1080P)
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    fps: int = Field(default=30, gt=0, le=120)
    tags: list[str] = Field(default_factory=list)
    format: str = Field(default="mp4")
    target_platform: TargetPlatform = Field(default=TargetPlatform.YOUTUBE)
    category_id: int = Field(default=27, gt=0)
    privacy_status: PrivacyStatus = Field(default=PrivacyStatus.PUBLIC)
    language: str = Field(default="en")
    problem_number: int | None = Field(default=None)
    difficulty: Difficulty | None = Field(default=None)
    seo_metadata: SEOMetadata | None = Field(default=None)

    @field_validator("title", "description", "format", "language")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v

    @field_validator("fps")
    @classmethod
    def validate_fps(cls, fps: int) -> int:
        """Ensure FPS is one of the allowed standard values."""
        allowed = {24, 25, 30, 50, 60, 120}
        if fps not in allowed:
            raise ValueError(f"FPS {fps} is not in allowed set {allowed}")
        return fps

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        """Ensure tag list items are not empty or whitespace-only and total character count <= 500."""
        for tag in tags:
            if not tag or not tag.strip():
                raise ValueError("List item cannot be empty or whitespace only")
        total_chars = sum(len(tag) for tag in tags)
        if total_chars > 500:
            raise ValueError(f"Total tag characters ({total_chars}) exceeds limit of 500")
        return tags

    @model_validator(mode="after")
    def align_resolution_and_dimensions(self) -> "VideoMetadata":
        """Validate and align resolution with width and height."""
        res_map = {
            "720p": (1280, 720),
            "1080p": (1920, 1080),
            "1440p": (2560, 1440),
            "4K": (3840, 2160),
        }
        dim_map = {v: k for k, v in res_map.items()}

        res_str = str(self.resolution.value) if isinstance(self.resolution, Enum) else str(self.resolution)
        curr_dims = (self.width, self.height)

        if res_str in res_map:
            expected_w, expected_h = res_map[res_str]
            if curr_dims != (expected_w, expected_h):
                if curr_dims in dim_map and res_str == "1080p":
                    self.resolution = VideoResolution(dim_map[curr_dims])
                else:
                    self.width = expected_w
                    self.height = expected_h
        return self
