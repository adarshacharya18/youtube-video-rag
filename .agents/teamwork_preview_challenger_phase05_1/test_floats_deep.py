import math
from pydantic import ValidationError

from src.core.models import (
    AssembledVideo,
    AssetReference,
    AudioAsset,
    EducationalPlan,
    PlanSection,
    RenderManifest,
    RenderSegment,
    VideoAsset,
)

inf = float("inf")
nan = float("nan")

print("--- Testing PlanSection ---")
try:
    s = PlanSection(
        section_id="s1", section_type="intro", title="t", narration="n", estimated_duration=inf
    )
    print(f"PlanSection accepts inf duration! val={s.estimated_duration}")
except ValidationError as e:
    print(f"PlanSection rejected inf duration with ValidationError: {e}")

try:
    s = PlanSection(
        section_id="s1", section_type="intro", title="t", narration="n", estimated_duration=nan
    )
    print(f"PlanSection accepts nan duration! val={s.estimated_duration}")
except ValidationError as e:
    print(f"PlanSection rejected nan duration with ValidationError")


print("\n--- Testing EducationalPlan with inf duration ---")
sec_inf = PlanSection(
    section_id="s1", section_type="intro", title="t", narration="n", estimated_duration=inf
)
try:
    p = EducationalPlan(
        topic="t",
        slug="s",
        learning_objectives=["obj"],
        sections=[sec_inf],
        estimated_total_duration=inf,
    )
    print(f"EducationalPlan accepts inf total duration and inf section duration! val={p.estimated_total_duration}")
except ValidationError as e:
    print(f"EducationalPlan rejected inf with ValidationError: {e}")
except Exception as e:
    print(f"EducationalPlan crashed with {type(e).__name__}: {e}")


print("\n--- Testing EducationalPlan with NaN duration ---")
sec_10 = PlanSection(
    section_id="s1", section_type="intro", title="t", narration="n", estimated_duration=10.0
)
try:
    p = EducationalPlan(
        topic="t",
        slug="s",
        learning_objectives=["obj"],
        sections=[sec_10],
        estimated_total_duration=nan,
    )
    print(f"EducationalPlan accepts NaN total duration! val={p.estimated_total_duration}")
except ValidationError as e:
    print(f"EducationalPlan rejected NaN total duration with ValidationError: {e}")
except Exception as e:
    print(f"EducationalPlan crashed with {type(e).__name__}: {e}")


print("\n--- Testing RenderSegment with inf start_time / end_time / duration ---")
ref = AssetReference(asset_id="a1", asset_type="audio", file_path="/p.mp3", duration=5.0)

try:
    seg = RenderSegment(
        segment_id="s1",
        segment_type="intro",
        start_time=0.0,
        end_time=inf,
        duration=inf,
        asset_references=[ref],
    )
    print(f"RenderSegment accepts inf end_time & duration! end_time={seg.end_time}, duration={seg.duration}")
except ValidationError as e:
    print(f"RenderSegment rejected inf end_time with ValidationError: {e}")
except Exception as e:
    print(f"RenderSegment crashed with {type(e).__name__}: {e}")


print("\n--- Testing RenderSegment with inf volume ---")
try:
    seg = RenderSegment(
        segment_id="s1",
        segment_type="intro",
        start_time=0.0,
        end_time=10.0,
        duration=10.0,
        volume=inf,
        asset_references=[ref],
    )
    print(f"RenderSegment accepts inf volume! volume={seg.volume}")
except ValidationError as e:
    print(f"RenderSegment rejected inf volume with ValidationError")
except Exception as e:
    print(f"RenderSegment crashed with {type(e).__name__}: {e}")


print("\n--- Testing AudioAsset & VideoAsset with inf duration ---")
try:
    aud = AudioAsset(audio_id="a1", file_path="/p.mp3", duration_seconds=inf)
    print(f"AudioAsset accepts inf duration_seconds! val={aud.duration_seconds}")
except ValidationError as e:
    print(f"AudioAsset rejected inf duration_seconds with ValidationError")

try:
    vid = VideoAsset(asset_id="v1", file_path="/p.mp4", duration_seconds=inf)
    print(f"VideoAsset accepts inf duration_seconds! val={vid.duration_seconds}")
except ValidationError as e:
    print(f"VideoAsset rejected inf duration_seconds with ValidationError")
