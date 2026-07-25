"""Master empirical re-challenge test suite for Phase 05 remediated Pydantic V2 models."""

import json
import pytest
from pydantic import ValidationError

from src.core.models import (
    AssembledVideo,
    AssetReference,
    AudioAsset,
    CodeSnippet,
    ConceptPrerequisite,
    Difficulty,
    EducationalPlan,
    LearningObjective,
    PlanSection,
    PrivacyStatus,
    RenderManifest,
    RenderSegment,
    SEOMetadata,
    TargetPlatform,
    VideoAsset,
    VideoMetadata,
    VideoResolution,
    VisualCue,
)


def test_rechallenge_non_finite_floats_python():
    """1. Verify that float('inf'), float('-inf'), float('nan') raise ValidationError in all models."""
    bad_floats = [float("inf"), float("-inf"), float("nan")]

    sec_valid = PlanSection(
        section_id="s1", section_type="intro", title="Intro", narration="Hi", estimated_duration=5.0
    )
    ref_valid = AssetReference(asset_id="a1", asset_type="audio", file_path="/p.mp3", duration=5.0)

    for val in bad_floats:
        # PlanSection estimated_duration
        with pytest.raises(ValidationError) as exc:
            PlanSection(section_id="s1", section_type="intro", title="Intro", narration="Hi", estimated_duration=val)
        assert "finite number" in str(exc.value)

        # EducationalPlan estimated_total_duration
        with pytest.raises(ValidationError) as exc:
            EducationalPlan(
                topic="Topic", slug="slug", learning_objectives=["Obj"], sections=[sec_valid], estimated_total_duration=val
            )
        assert "finite number" in str(exc.value)

        # AssetReference duration
        with pytest.raises(ValidationError) as exc:
            AssetReference(asset_id="a1", asset_type="audio", file_path="/p.mp3", duration=val)
        assert "finite number" in str(exc.value)

        # AudioAsset duration_seconds
        with pytest.raises(ValidationError) as exc:
            AudioAsset(audio_id="a1", file_path="/p.wav", duration_seconds=val)
        assert "finite number" in str(exc.value)

        # VideoAsset duration_seconds
        with pytest.raises(ValidationError) as exc:
            VideoAsset(asset_id="v1", file_path="/p.mp4", duration_seconds=val)
        assert "finite number" in str(exc.value)

        # RenderSegment start_time, end_time, duration, volume
        with pytest.raises(ValidationError) as exc:
            RenderSegment(
                segment_id="s1", segment_type="intro", start_time=val, end_time=5.0, duration=5.0, asset_references=[ref_valid]
            )
        assert "finite number" in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            RenderSegment(
                segment_id="s1", segment_type="intro", start_time=0.0, end_time=val, duration=5.0, asset_references=[ref_valid]
            )
        assert "finite number" in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            RenderSegment(
                segment_id="s1", segment_type="intro", start_time=0.0, end_time=5.0, duration=val, asset_references=[ref_valid]
            )
        assert "finite number" in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            RenderSegment(
                segment_id="s1", segment_type="intro", start_time=0.0, end_time=5.0, duration=5.0, volume=val, asset_references=[ref_valid]
            )
        assert "finite number" in str(exc.value)

        # RenderManifest total_duration
        with pytest.raises(ValidationError) as exc:
            RenderManifest(pipeline_run_id="r1", slug="slug", segments=[], total_duration=val)
        assert "finite number" in str(exc.value)

        # AssembledVideo total_duration_seconds
        with pytest.raises(ValidationError) as exc:
            AssembledVideo(slug="slug", final_video_path="/p.mp4", total_duration_seconds=val)
        assert "finite number" in str(exc.value)


def test_rechallenge_non_finite_floats_json():
    """Verify JSON payloads with Infinity / -Infinity / NaN raise ValidationError."""
    json_samples = [
        ('{"section_id":"s1","section_type":"intro","title":"T","narration":"N","estimated_duration":Infinity}', PlanSection),
        ('{"section_id":"s1","section_type":"intro","title":"T","narration":"N","estimated_duration":-Infinity}', PlanSection),
        ('{"section_id":"s1","section_type":"intro","title":"T","narration":"N","estimated_duration":NaN}', PlanSection),
    ]
    for payload, model_cls in json_samples:
        with pytest.raises(ValidationError):
            model_cls.model_validate_json(payload)


def test_rechallenge_whitespace_string_lists():
    """2. Verify that whitespace-only string list items raise ValidationError."""
    whitespace_items = ["   ", "\t", "\n", " \t \n "]

    sec_valid = PlanSection(
        section_id="s1", section_type="intro", title="Intro", narration="Hi", estimated_duration=5.0
    )

    for item in whitespace_items:
        # VideoMetadata tags
        with pytest.raises(ValidationError) as exc:
            VideoMetadata(title="Title", description="Desc", slug="slug", tags=[item])
        assert "List item cannot be empty or whitespace only" in str(exc.value)

        # SEOMetadata tags
        with pytest.raises(ValidationError) as exc:
            SEOMetadata(youtube_title="Title", youtube_description="Desc", tags=[item])
        assert "List item cannot be empty or whitespace only" in str(exc.value)

        # PlanSection visual_cue_ids
        with pytest.raises(ValidationError) as exc:
            PlanSection(section_id="s1", section_type="intro", title="T", narration="N", estimated_duration=5.0, visual_cue_ids=[item])
        assert "List item cannot be empty or whitespace only" in str(exc.value)

        # EducationalPlan learning_objectives
        with pytest.raises(ValidationError) as exc:
            EducationalPlan(topic="Top", slug="slug", learning_objectives=[item], sections=[sec_valid], estimated_total_duration=5.0)
        assert "List item cannot be empty or whitespace only" in str(exc.value)

        # EducationalPlan prerequisites
        with pytest.raises(ValidationError) as exc:
            EducationalPlan(topic="Top", slug="slug", learning_objectives=["Valid"], prerequisites=[item], sections=[sec_valid], estimated_total_duration=5.0)
        assert "List item cannot be empty or whitespace only" in str(exc.value)


def test_rechallenge_invariant_math_protection():
    """Verify that inf math tricks cannot bypass plan or segment invariant validators."""
    sec1 = PlanSection(
        section_id="sec-1", section_type="intro", title="Title", narration="Narr", estimated_duration=10.0
    )

    # EducationalPlan with total_duration = inf (attempting inf - inf = nan bypass)
    with pytest.raises(ValidationError) as exc:
        EducationalPlan(
            topic="Topic",
            slug="slug",
            learning_objectives=["Obj"],
            sections=[sec1],
            estimated_total_duration=float("inf"),
        )
    assert "finite number" in str(exc.value)

    ref = AssetReference(asset_id="a1", asset_type="audio", file_path="/p.mp3", duration=10.0)
    # RenderSegment with end_time = inf, start_time = 0.0, duration = inf
    with pytest.raises(ValidationError) as exc:
        RenderSegment(
            segment_id="s1",
            segment_type="intro",
            start_time=0.0,
            end_time=float("inf"),
            duration=float("inf"),
            asset_references=[ref],
        )
    assert "finite number" in str(exc.value)
