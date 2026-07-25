import math
from src.core.models import EducationalPlan, PlanSection, RenderSegment, AssetReference

inf = float("inf")

# Test EducationalPlan inf - inf = nan
sec1 = PlanSection(section_id="s1", section_type="intro", title="t", narration="n", estimated_duration=inf)
sec2 = PlanSection(section_id="s2", section_type="outro", title="t", narration="n", estimated_duration=10.0)

print("sum_durations = inf + 10.0 =", inf + 10.0)
print("estimated_total_duration - sum_durations = inf - inf =", inf - inf)
print("abs(inf - inf) > 0.1 =", abs(inf - inf) > 0.1)

p = EducationalPlan(
    topic="t",
    slug="s",
    learning_objectives=["obj"],
    sections=[sec1, sec2],
    estimated_total_duration=inf,
)
print("EducationalPlan created with inf:", p.estimated_total_duration)

# Test RenderSegment inf - inf = nan
ref = AssetReference(asset_id="a1", asset_type="audio", file_path="/p.mp3", duration=5.0)
seg = RenderSegment(
    segment_id="s1",
    segment_type="intro",
    start_time=0.0,
    end_time=inf,
    duration=inf,
    asset_references=[ref],
)
print("RenderSegment created with inf:", seg.end_time, seg.duration)
