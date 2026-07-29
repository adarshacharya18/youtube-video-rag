"""YouTube Script Pydantic Schemas for DSA Educational Content.

Defines structured models representing YouTube engagement metrics and sections:
Hook, Context, Solution, Complexity, along with visual cues and spoken narration.
"""

import json
import math
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class VisualCue(BaseModel):
    """Animation or visual reference cue within a script section."""

    cue_id: str = Field(..., description="Unique visual cue identifier")
    animation_type: str = Field(..., description="Type of visual animation (e.g., array_highlight, tree_traversal)")
    description: str = Field(..., description="Detailed description of visual action")
    timestamp_seconds: float = Field(default=0.0, ge=0.0, description="Timestamp offset in seconds")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary parameters for renderer")

    @field_validator("cue_id", "animation_type", "description")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-empty and non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v

    @field_validator("timestamp_seconds", mode="before")
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


class HookSection(BaseModel):
    """YouTube engagement Hook section (0-30s intro)."""

    title: str = Field(default="Hook", description="Section title")
    narration: str = Field(..., description="Fast-paced opening narration to intrigue viewers")
    visual_cues: List[VisualCue] = Field(default_factory=list, description="Visual cues for hook")
    estimated_duration: float = Field(..., gt=0.0, description="Duration in seconds")

    @field_validator("title", "narration")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v

    @field_validator("estimated_duration", mode="before")
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


class ContextSection(BaseModel):
    """Problem context, background, and intuition section."""

    title: str = Field(default="Context", description="Section title")
    narration: str = Field(..., description="Problem statement breakdown and real-world intuition")
    visual_cues: List[VisualCue] = Field(default_factory=list, description="Visual cues for context")
    estimated_duration: float = Field(..., gt=0.0, description="Duration in seconds")

    @field_validator("title", "narration")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v

    @field_validator("estimated_duration", mode="before")
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


class SolutionSection(BaseModel):
    """Step-by-step algorithmic solution walkthrough and code execution."""

    title: str = Field(default="Solution", description="Section title")
    narration: str = Field(..., description="Step-by-step algorithmic breakdown and code narration")
    code_snippet: Optional[str] = Field(default=None, description="Reference code implementation")
    visual_cues: List[VisualCue] = Field(default_factory=list, description="Visual cues for solution step")
    estimated_duration: float = Field(..., gt=0.0, description="Duration in seconds")

    @field_validator("title", "narration")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v

    @field_validator("code_snippet")
    @classmethod
    def validate_optional_non_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Ensure code_snippet, if provided, is not whitespace-only."""
        if v is not None and not v.strip():
            raise ValueError("code_snippet cannot be whitespace-only")
        return v

    @field_validator("estimated_duration", mode="before")
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


class ComplexitySection(BaseModel):
    """Asymptotic Time and Space complexity analysis section."""

    title: str = Field(default="Complexity", description="Section title")
    narration: str = Field(..., description="Narration explaining Big-O bounds and edge cases")
    time_complexity: str = Field(default="O(N)", description="Big-O Time Complexity")
    space_complexity: str = Field(default="O(1)", description="Big-O Space Complexity")
    visual_cues: List[VisualCue] = Field(default_factory=list, description="Visual cues for complexity analysis")
    estimated_duration: float = Field(..., gt=0.0, description="Duration in seconds")

    @field_validator("title", "narration", "time_complexity", "space_complexity")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v

    @field_validator("estimated_duration", mode="before")
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


class YouTubeScript(BaseModel):
    """Complete YouTube Educational DSA Script Model."""

    topic: str = Field(..., description="DSA Topic or Problem title")
    slug: str = Field(..., pattern=r"^[a-z0-9-]+$", description="URL-friendly slug (lowercase, numbers, hyphens)")
    difficulty: str = Field(default="Medium", description="Problem difficulty level")
    hook: HookSection = Field(..., description="Hook engagement section")
    context: ContextSection = Field(..., description="Problem context section")
    solution: SolutionSection = Field(..., description="Algorithmic solution section")
    complexity: ComplexitySection = Field(..., description="Complexity analysis section")
    total_duration: float = Field(..., gt=0.0, description="Total script duration in seconds")
    spoken_narration: List[str] = Field(default_factory=list, description="Aggregated spoken narration strings")
    visual_cues: List[VisualCue] = Field(default_factory=list, description="Aggregated visual animation cues")

    @field_validator("topic", "difficulty")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
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

    @field_validator("total_duration", mode="before")
    @classmethod
    def validate_finite_float(cls, v: Any) -> Any:
        """Ensure total_duration is a finite float."""
        if v is not None:
            try:
                fv = float(v)
            except (ValueError, TypeError):
                return v
            if not math.isfinite(fv):
                raise ValueError("total_duration must be a finite number")
        return v

    @model_validator(mode="after")
    def validate_script_invariants(self) -> "YouTubeScript":
        """Enforce total duration match across sections and auto-populate aggregate lists."""
        section_sum = (
            self.hook.estimated_duration
            + self.context.estimated_duration
            + self.solution.estimated_duration
            + self.complexity.estimated_duration
        )
        if round(abs(self.total_duration - section_sum), 4) > 0.1:
            raise ValueError(
                f"total_duration ({self.total_duration}) does not match sum of section durations ({section_sum}) "
                f"within tolerance of 0.1s"
            )

        # Auto-populate spoken_narration if empty
        if not self.spoken_narration:
            object.__setattr__(
                self,
                "spoken_narration",
                [
                    self.hook.narration,
                    self.context.narration,
                    self.solution.narration,
                    self.complexity.narration,
                ],
            )

        # Auto-populate visual_cues if empty
        if not self.visual_cues:
            all_cues = (
                list(self.hook.visual_cues)
                + list(self.context.visual_cues)
                + list(self.solution.visual_cues)
                + list(self.complexity.visual_cues)
            )
            object.__setattr__(self, "visual_cues", all_cues)

        return self

    @classmethod
    def export_schema_json(cls) -> str:
        """Export the Pydantic model JSON schema as a formatted string."""
        return json.dumps(cls.model_json_schema(), indent=2)

    @classmethod
    def export_schema_dict(cls) -> Dict[str, Any]:
        """Export the Pydantic model JSON schema as a dictionary."""
        return cls.model_json_schema()


# Alias for backward compatibility / flexibility
ScriptSchema = YouTubeScript
