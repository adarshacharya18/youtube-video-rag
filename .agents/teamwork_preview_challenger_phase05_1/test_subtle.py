from pydantic import ValidationError
from src.core.models import (
    EducationalPlan,
    PlanSection,
    VideoMetadata,
    SEOMetadata,
    RenderSegment,
)

print("--- Test 1: Tags with whitespace ---")
try:
    v = VideoMetadata(
        title="Title", description="Desc", slug="slug", tags=["   ", "\t\n"]
    )
    print("VideoMetadata accepted whitespace tags:", repr(v.tags))
except ValidationError as e:
    print("VideoMetadata rejected whitespace tags with ValidationError")

print("\n--- Test 2: Prerequisites with whitespace strings ---")
sec = PlanSection(
    section_id="s1", section_type="intro", title="t", narration="n", estimated_duration=10.0
)
try:
    p = EducationalPlan(
        topic="Topic",
        slug="slug",
        learning_objectives=["Obj 1"],
        prerequisites=["   "],
        sections=[sec],
        estimated_total_duration=10.0,
    )
    print("EducationalPlan accepted whitespace prerequisite string:", repr(p.prerequisites))
except ValidationError as e:
    print("EducationalPlan rejected whitespace prerequisite string with ValidationError")

print("\n--- Test 3: Float infinity in total duration vs section duration mismatch ---")
sec_finite = PlanSection(
    section_id="s1", section_type="intro", title="t", narration="n", estimated_duration=10.0
)
try:
    p = EducationalPlan(
        topic="Topic",
        slug="slug",
        learning_objectives=["Obj 1"],
        sections=[sec_finite],
        estimated_total_duration=float("inf"),
    )
    print("EducationalPlan accepted total_duration=inf with finite section duration=10.0!")
except ValidationError as e:
    print("EducationalPlan rejected total_duration=inf with ValidationError:", e)

