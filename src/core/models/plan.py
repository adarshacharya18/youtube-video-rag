"""Educational plan and curriculum breakdown models."""

import math
import re
from typing import Any, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class PlanSection(BaseModel):
    """Individual section of an educational video plan."""

    section_id: str = Field(...)
    section_type: str = Field(...)
    title: str = Field(...)
    narration: str = Field(...)
    estimated_duration: float = Field(..., gt=0.0)
    visual_cue_ids: list[str] = Field(default_factory=list)
    order: int = Field(default=0, ge=0)

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

    @field_validator("section_id", "section_type", "title", "narration")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure required string fields are non-empty and non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v

    @field_validator("visual_cue_ids")
    @classmethod
    def validate_visual_cue_ids(cls, v: list[str]) -> list[str]:
        """Ensure visual_cue_ids list items are not empty or whitespace-only."""
        for item in v:
            if not item or not item.strip():
                raise ValueError("List item cannot be empty or whitespace only")
        return v


class CodeSnippet(BaseModel):
    """Code snippet associated with an educational section."""

    snippet_id: str = Field(...)
    language: str = Field(default="python")
    code: str = Field(...)
    explanation: str | None = Field(default=None)
    line_highlights: list[int] = Field(default_factory=list)

    @field_validator("snippet_id", "language", "code")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v

    @field_validator("explanation")
    @classmethod
    def validate_optional_non_whitespace(cls, v: str | None) -> str | None:
        """Ensure explanation, if provided, is not whitespace-only."""
        if v is not None and not v.strip():
            raise ValueError("Explanation cannot be whitespace-only")
        return v

    @field_validator("line_highlights")
    @classmethod
    def validate_line_highlights(cls, v: list[int]) -> list[int]:
        """Ensure line numbers highlighted are 1-based (>= 1)."""
        for line in v:
            if line < 1:
                raise ValueError(f"Line highlight line number must be >= 1, got {line}")
        return v


class VisualCue(BaseModel):
    """Animation cue reference within the plan."""

    cue_id: str = Field(...)
    animation_type: str = Field(...)
    description: str = Field(...)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("cue_id", "animation_type", "description")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v


class ConceptPrerequisite(BaseModel):
    """Prerequisite knowledge entry."""

    concept: str = Field(...)
    description: str | None = Field(default=None)

    @field_validator("concept")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure concept name is non-whitespace."""
        if not v or not v.strip():
            raise ValueError("Concept name cannot be empty or whitespace-only")
        return v

    @field_validator("description")
    @classmethod
    def validate_optional_non_whitespace(cls, v: str | None) -> str | None:
        """Ensure optional description is not whitespace-only."""
        if v is not None and not v.strip():
            raise ValueError("Description cannot be whitespace-only")
        return v


class LearningObjective(BaseModel):
    """Target learning objective entry."""

    objective_id: str = Field(...)
    description: str = Field(...)
    taxonomic_level: str | None = Field(default=None)

    @field_validator("objective_id", "description")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """Ensure string fields are non-whitespace."""
        if not v or not v.strip():
            raise ValueError("String field cannot be empty or whitespace-only")
        return v

    @field_validator("taxonomic_level")
    @classmethod
    def validate_optional_non_whitespace(cls, v: str | None) -> str | None:
        """Ensure optional taxonomic level is not whitespace-only."""
        if v is not None and not v.strip():
            raise ValueError("Taxonomic level cannot be whitespace-only")
        return v


class EducationalPlan(BaseModel):
    """Comprehensive educational plan for generating video content."""

    topic: str = Field(...)
    slug: str = Field(..., pattern=r"^[a-z0-9-]+$")
    target_audience: str = Field(default="Beginner")
    difficulty: str = Field(default="Medium")
    learning_objectives: list[Union[LearningObjective, str]] = Field(...)
    prerequisites: list[Union[ConceptPrerequisite, str]] = Field(default_factory=list)
    sections: list[PlanSection] = Field(...)
    code_snippets: list[CodeSnippet] = Field(default_factory=list)
    visual_cues: list[VisualCue] = Field(default_factory=list)
    estimated_total_duration: float = Field(..., gt=0.0)

    @field_validator("estimated_total_duration", mode="before")
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

    @field_validator("topic", "target_audience", "difficulty")
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

    @field_validator("learning_objectives")
    @classmethod
    def validate_learning_objectives(cls, v: list[Union[LearningObjective, str]]) -> list[Union[LearningObjective, str]]:
        """Ensure learning_objectives contains at least 1 non-empty item."""
        if not v:
            raise ValueError("learning_objectives must contain at least 1 item")
        for item in v:
            if isinstance(item, str):
                if not item or not item.strip():
                    raise ValueError("List item cannot be empty or whitespace only")
        return v

    @field_validator("prerequisites")
    @classmethod
    def validate_prerequisites(cls, v: list[Union[ConceptPrerequisite, str]]) -> list[Union[ConceptPrerequisite, str]]:
        """Ensure prerequisite string items are non-empty and non-whitespace."""
        for item in v:
            if isinstance(item, str):
                if not item or not item.strip():
                    raise ValueError("List item cannot be empty or whitespace only")
        return v

    @field_validator("sections")
    @classmethod
    def validate_sections_non_empty(cls, v: list[PlanSection]) -> list[PlanSection]:
        """Ensure sections list is not empty."""
        if not v:
            raise ValueError("sections list must contain at least 1 item")
        return v

    @model_validator(mode="after")
    def validate_plan_invariants(self) -> "EducationalPlan":
        """Enforce duplicate section_id check and total duration match within 0.1s tolerance."""
        seen_ids = set()
        for sec in self.sections:
            if sec.section_id in seen_ids:
                raise ValueError(f"Duplicate section_id found in sections: '{sec.section_id}'")
            seen_ids.add(sec.section_id)

        sum_durations = sum(sec.estimated_duration for sec in self.sections)
        if abs(self.estimated_total_duration - sum_durations) > 0.1:
            raise ValueError(
                f"estimated_total_duration ({self.estimated_total_duration}) does not match "
                f"sum of section durations ({sum_durations}) within tolerance 0.1s"
            )
        return self
