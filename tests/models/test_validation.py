"""Unit tests for Pydantic V2 core models validation in Phase 05."""

from datetime import datetime
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
from src.core.orchestrator.state_ledger import StateLedger



def test_video_models_valid():
    seo = SEOMetadata(
        youtube_title="Mastering Two Sum in Python",
        youtube_description="A step-by-step tutorial on solving Two Sum.",
        tags=["dsa", "leetcode", "python"],
        category_id=27,
        privacy_status=PrivacyStatus.PUBLIC,
        chapter_timestamps=[{"00:00": "Intro"}, {"01:30": "Explanation"}],
    )
    assert seo.youtube_title == "Mastering Two Sum in Python"
    assert seo.privacy_status == "public"

    video = VideoMetadata(
        title="Two Sum Algorithm",
        description="Detailed guide to solving Two Sum.",
        slug="two-sum-algorithm",
        resolution=VideoResolution.R_4K,
        fps=60,
        tags=["python", "arrays"],
        target_platform=TargetPlatform.YOUTUBE,
        difficulty=Difficulty.EASY,
        seo_metadata=seo,
    )
    assert video.width == 3840
    assert video.height == 2160
    assert video.fps == 60


def test_video_models_invalid():
    # Whitespace title
    with pytest.raises(ValidationError):
        VideoMetadata(title="   ", description="valid desc", slug="valid-slug")

    # Whitespace description
    with pytest.raises(ValidationError):
        VideoMetadata(title="valid title", description="   ", slug="valid-slug")

    # Whitespace format or language
    with pytest.raises(ValidationError):
        VideoMetadata(title="valid title", description="valid desc", slug="valid-slug", format="  ")

    with pytest.raises(ValidationError):
        VideoMetadata(title="valid title", description="valid desc", slug="valid-slug", language="  ")

    # Invalid slug pattern
    with pytest.raises(ValidationError):
        VideoMetadata(title="Title", description="Desc", slug="Invalid_Slug!")

    # Invalid FPS (29 is not in {24, 25, 30, 50, 60, 120})
    with pytest.raises(ValidationError):
        VideoMetadata(title="Title", description="Desc", slug="valid-slug", fps=29)

    # Tag length > 500 chars
    with pytest.raises(ValidationError):
        VideoMetadata(
            title="Title",
            description="Desc",
            slug="valid-slug",
            tags=["a" * 300, "b" * 201],
        )

    # Invalid resolution enum value
    with pytest.raises(ValidationError):
        VideoMetadata(title="Title", description="Desc", slug="valid-slug", resolution="8K")

    # SEO metadata whitespace title/description
    with pytest.raises(ValidationError):
        SEOMetadata(youtube_title="  ", youtube_description="desc")

    with pytest.raises(ValidationError):
        SEOMetadata(youtube_title="title", youtube_description="  ")

    # SEO metadata tag length > 500 chars
    with pytest.raises(ValidationError):
        SEOMetadata(youtube_title="title", youtube_description="desc", tags=["x" * 501])


def test_plan_models_valid():
    sec1 = PlanSection(
        section_id="sec-1",
        section_type="intro",
        title="Introduction",
        narration="Welcome to the video.",
        estimated_duration=10.0,
        order=1,
    )
    sec2 = PlanSection(
        section_id="sec-2",
        section_type="explanation",
        title="Algorithm Breakdown",
        narration="Here is how the hash map works.",
        estimated_duration=20.0,
        order=2,
    )

    code = CodeSnippet(
        snippet_id="code-1",
        language="python",
        code="def two_sum(nums, target):\n    return []",
        explanation="Initial code stub",
        line_highlights=[1, 2],
    )

    cue = VisualCue(
        cue_id="cue-1",
        animation_type="array_highlight",
        description="Highlight element at index 0",
        parameters={"index": 0},
    )

    obj = LearningObjective(
        objective_id="obj-1",
        description="Understand hash map lookups",
        taxonomic_level="Apply",
    )

    prereq = ConceptPrerequisite(
        concept="Arrays",
        description="Basic understanding of indexed lists",
    )

    plan = EducationalPlan(
        topic="Two Sum",
        slug="two-sum-plan",
        learning_objectives=[obj, "Achieve O(N) Time Complexity"],
        prerequisites=[prereq, "Basic Python syntax"],
        sections=[sec1, sec2],
        code_snippets=[code],
        visual_cues=[cue],
        estimated_total_duration=30.0,
    )
    assert plan.slug == "two-sum-plan"
    assert len(plan.sections) == 2
    assert plan.estimated_total_duration == 30.0


def test_plan_models_invalid():
    sec1 = PlanSection(
        section_id="sec-1",
        section_type="intro",
        title="Intro",
        narration="Hello",
        estimated_duration=10.0,
    )
    sec2_duplicate = PlanSection(
        section_id="sec-1",  # Duplicate section_id!
        section_type="outro",
        title="Outro",
        narration="Bye",
        estimated_duration=10.0,
    )

    # Duplicate section_id validation
    with pytest.raises(ValidationError) as exc_info:
        EducationalPlan(
            topic="Topic",
            slug="valid-slug",
            learning_objectives=["Obj 1"],
            sections=[sec1, sec2_duplicate],
            estimated_total_duration=20.0,
        )
    assert "Duplicate section_id" in str(exc_info.value)

    # Total duration mismatch (> 0.1s tolerance)
    sec2_diff = PlanSection(
        section_id="sec-2",
        section_type="outro",
        title="Outro",
        narration="Bye",
        estimated_duration=10.0,
    )
    with pytest.raises(ValidationError) as exc_info:
        EducationalPlan(
            topic="Topic",
            slug="valid-slug",
            learning_objectives=["Obj 1"],
            sections=[sec1, sec2_diff],
            estimated_total_duration=45.0,  # 10 + 10 = 20 != 45
        )
    assert "estimated_total_duration" in str(exc_info.value)

    # CodeSnippet line_highlights < 1
    with pytest.raises(ValidationError):
        CodeSnippet(snippet_id="c1", code="x = 1", line_highlights=[0])

    # Whitespace code snippet explanation
    with pytest.raises(ValidationError):
        CodeSnippet(snippet_id="c1", code="x = 1", explanation="   ")

    # Empty learning objectives
    with pytest.raises(ValidationError):
        EducationalPlan(
            topic="Topic",
            slug="valid-slug",
            learning_objectives=[],
            sections=[sec1],
            estimated_total_duration=10.0,
        )

    # Whitespace item in learning objectives
    with pytest.raises(ValidationError):
        EducationalPlan(
            topic="Topic",
            slug="valid-slug",
            learning_objectives=["   "],
            sections=[sec1],
            estimated_total_duration=10.0,
        )

    # Whitespace fields in PlanSection
    with pytest.raises(ValidationError):
        PlanSection(
            section_id="   ",
            section_type="intro",
            title="Title",
            narration="Narration",
            estimated_duration=10.0,
        )

    # Whitespace in ConceptPrerequisite / LearningObjective
    with pytest.raises(ValidationError):
        ConceptPrerequisite(concept="   ")

    with pytest.raises(ValidationError):
        ConceptPrerequisite(concept="Arrays", description="   ")

    with pytest.raises(ValidationError):
        LearningObjective(objective_id="   ", description="Desc")

    with pytest.raises(ValidationError):
        LearningObjective(objective_id="o1", description="Desc", taxonomic_level="   ")


def test_asset_models_valid():
    ref = AssetReference(
        asset_id="asset-1",
        asset_type="audio",
        file_path="/path/to/audio.mp3",
        duration=5.0,
    )

    audio_asset = AudioAsset(
        audio_id="aud-1",
        file_path="/path/to/narration.wav",
        duration_seconds=10.0,
        sample_rate=24000,
        voice_model="kokoro",
    )

    video_asset = VideoAsset(
        asset_id="vid-1",
        file_path="/path/to/video.mp4",
        duration_seconds=10.0,
        resolution="1920x1080",
        fps=30,
        file_size_bytes=1024000,
    )
    assert video_asset.file_size_bytes == 1024000

    seg_ref = RenderSegment(
        segment_id="seg-1",
        segment_type="intro",
        start_time=0.0,
        end_time=10.0,
        duration=10.0,
        asset_references=[ref],
    )
    assert seg_ref.duration == 10.0

    seg_audio = RenderSegment(
        segment_id="seg-2",
        segment_type="narration",
        start_time=0.0,
        end_time=10.0,
        duration=10.0,
        audio_asset=audio_asset,
    )
    assert seg_audio.audio_asset.audio_id == "aud-1"

    seg_paths = RenderSegment(
        segment_id="seg-3",
        segment_type="code_walkthrough",
        start_time=0.0,
        end_time=5.0,
        duration=5.0,
        audio_path="/path/to/audio.mp3",
        visual_path="/path/to/visual.mp4",
    )
    assert seg_paths.audio_path == "/path/to/audio.mp3"

    manifest = RenderManifest(
        pipeline_run_id="run-123",
        slug="two-sum-manifest",
        segments=[seg_ref],
        total_duration=10.0,
    )
    assert manifest.pipeline_run_id == "run-123"

    assembled = AssembledVideo(
        slug="two-sum-manifest",
        final_video_path="/path/to/final.mp4",
        thumbnail_path="/path/to/thumb.jpg",
        total_duration_seconds=10.0,
        file_size_bytes=5000000,
        segments=[seg_ref],
        assembled_at=datetime.now(),
    )
    assert assembled.final_video_path == "/path/to/final.mp4"


def test_asset_models_invalid():
    ref = AssetReference(
        asset_id="asset-1",
        asset_type="audio",
        file_path="/path/to/audio.mp3",
        duration=5.0,
    )

    # end_time <= start_time
    with pytest.raises(ValidationError):
        RenderSegment(
            segment_id="seg-1",
            segment_type="intro",
            start_time=10.0,
            end_time=5.0,
            duration=5.0,
            asset_references=[ref],
        )

    # duration mismatch (duration != end_time - start_time)
    with pytest.raises(ValidationError):
        RenderSegment(
            segment_id="seg-1",
            segment_type="intro",
            start_time=0.0,
            end_time=10.0,
            duration=5.0,  # 10 - 0 != 5
            asset_references=[ref],
        )

    # Missing at least one asset reference
    with pytest.raises(ValidationError) as exc_info:
        RenderSegment(
            segment_id="seg-1",
            segment_type="intro",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            asset_references=[],
            audio_path=None,
            visual_path=None,
            audio_asset=None,
        )
    assert "at least one asset reference" in str(exc_info.value)

    # Invalid segment type
    with pytest.raises(ValidationError):
        RenderSegment(
            segment_id="seg-1",
            segment_type="invalid_type",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            asset_references=[ref],
        )

    # Whitespace in AssetReference
    with pytest.raises(ValidationError):
        AssetReference(asset_id="  ", asset_type="audio", file_path="/path")

    # Whitespace in AudioAsset / VideoAsset
    with pytest.raises(ValidationError):
        AudioAsset(audio_id="aud-1", file_path="  ", duration_seconds=5.0)

    with pytest.raises(ValidationError):
        VideoAsset(asset_id="vid-1", file_path="  ", duration_seconds=5.0)

    # RenderManifest empty segments / whitespace pipeline_run_id / invalid slug
    with pytest.raises(ValidationError):
        RenderManifest(
            pipeline_run_id="run-1",
            slug="slug",
            segments=[],
            total_duration=10.0,
        )

    with pytest.raises(ValidationError):
        RenderManifest(
            pipeline_run_id="   ",
            slug="slug",
            segments=[
                RenderSegment(
                    segment_id="s1",
                    segment_type="intro",
                    start_time=0.0,
                    end_time=5.0,
                    duration=5.0,
                    asset_references=[ref],
                )
            ],
            total_duration=5.0,
        )

    # AssembledVideo invalid slug / whitespace final_video_path
    with pytest.raises(ValidationError):
        AssembledVideo(
            slug="INVALID SLUG!",
            final_video_path="/path/to/final.mp4",
            total_duration_seconds=10.0,
        )

    with pytest.raises(ValidationError):
        AssembledVideo(
            slug="valid-slug",
            final_video_path="   ",
            total_duration_seconds=10.0,
        )


def test_state_ledger_model_serialization_roundtrip(tmp_path):
    """Verify Pydantic V2 models serialize cleanly to SQLite State Ledger and re-hydrate without loss."""
    db_path = tmp_path / "ledger_test.db"
    with StateLedger(db_path) as ledger:
        # Instantiates valid VideoMetadata, EducationalPlan, and RenderSegment models
        seo = SEOMetadata(
            youtube_title="Two Sum Algorithm Solution",
            youtube_description="Step by step solution to Two Sum in Python.",
            tags=["dsa", "leetcode", "two-sum"],
            category_id=27,
            privacy_status=PrivacyStatus.PUBLIC,
        )
        video_meta = VideoMetadata(
            title="Two Sum Algorithm",
            description="Complete guide to Two Sum.",
            slug="two-sum",
            resolution=VideoResolution.R_1080P,
            fps=30,
            tags=["python", "dsa"],
            target_platform=TargetPlatform.YOUTUBE,
            difficulty=Difficulty.EASY,
            seo_metadata=seo,
        )

        sec = PlanSection(
            section_id="sec-1",
            section_type="intro",
            title="Introduction to Two Sum",
            narration="Welcome to this video on Two Sum.",
            estimated_duration=15.0,
            order=1,
        )
        plan = EducationalPlan(
            topic="Two Sum",
            slug="two-sum",
            learning_objectives=["Understand Hash Map Approach"],
            sections=[sec],
            estimated_total_duration=15.0,
        )

        ref = AssetReference(
            asset_id="asset-1",
            asset_type="audio",
            file_path="/assets/intro_narration.mp3",
            duration=15.0,
        )
        segment = RenderSegment(
            segment_id="seg-1",
            segment_type="intro",
            start_time=0.0,
            end_time=15.0,
            duration=15.0,
            asset_references=[ref],
        )

        # c. Calls ledger.create_run(slug="two-sum", metadata=video_meta.model_dump(mode="json"))
        run_id = ledger.create_run(
            slug="two-sum",
            metadata=video_meta.model_dump(mode="json"),
        )

        # d. Retrieves the run via ledger.get_run(...), verifies run.metadata deserializes back via VideoMetadata.model_validate
        run_record = ledger.get_run(run_id)
        assert run_record is not None
        assert run_record.metadata is not None
        rehydrated_meta = VideoMetadata.model_validate(run_record.metadata)
        assert rehydrated_meta == video_meta

        # e. Calls ledger.record_step_start(...) and ledger.record_step_completion(...) with input_payload and output_payload
        step_id_plan = ledger.record_step_start(
            pipeline_run_id=run_id,
            step_name="plan_generation",
            input_payload=video_meta.model_dump(mode="json"),
        )
        ledger.record_step_completion(
            step_execution_id=step_id_plan,
            output_payload=plan.model_dump(mode="json"),
        )

        step_id_seg = ledger.record_step_start(
            pipeline_run_id=run_id,
            step_name="segment_rendering",
            input_payload=plan.model_dump(mode="json"),
        )
        ledger.record_step_completion(
            step_execution_id=step_id_seg,
            output_payload=segment.model_dump(mode="json"),
        )

        # f. Retrieves step execution via ledger.get_step_execution(...), verifies EducationalPlan and RenderSegment re-hydrate cleanly
        plan_step = ledger.get_step_execution(step_id_plan)
        assert plan_step is not None
        assert plan_step.output_payload is not None
        rehydrated_plan = EducationalPlan.model_validate(plan_step.output_payload)
        assert rehydrated_plan == plan

        seg_step = ledger.get_step_execution(step_id_seg)
        assert seg_step is not None
        assert seg_step.output_payload is not None
        rehydrated_segment = RenderSegment.model_validate(seg_step.output_payload)
        assert rehydrated_segment == segment


def test_non_finite_float_validation():
    """Verify that passing float('inf'), float('-inf'), or float('nan') raises ValidationError."""
    non_finite_values = [float("inf"), float("-inf"), float("nan")]

    sec1 = PlanSection(
        section_id="sec-1",
        section_type="intro",
        title="Intro",
        narration="Hello",
        estimated_duration=10.0,
    )
    ref1 = AssetReference(
        asset_id="asset-1",
        asset_type="audio",
        file_path="/path/audio.mp3",
        duration=10.0,
    )

    for val in non_finite_values:
        # PlanSection - estimated_duration
        with pytest.raises(ValidationError) as exc_info:
            PlanSection(
                section_id="sec-1",
                section_type="intro",
                title="Intro",
                narration="Hello",
                estimated_duration=val,
            )
        assert "Float field must be a finite number" in str(exc_info.value)

        # EducationalPlan - estimated_total_duration
        with pytest.raises(ValidationError) as exc_info:
            EducationalPlan(
                topic="Topic",
                slug="topic-slug",
                learning_objectives=["Obj"],
                sections=[sec1],
                estimated_total_duration=val,
            )
        assert "Float field must be a finite number" in str(exc_info.value)

        # AssetReference - duration
        with pytest.raises(ValidationError) as exc_info:
            AssetReference(
                asset_id="a1",
                asset_type="audio",
                file_path="/path",
                duration=val,
            )
        assert "Float field must be a finite number" in str(exc_info.value)

        # AudioAsset - duration_seconds
        with pytest.raises(ValidationError) as exc_info:
            AudioAsset(
                audio_id="aud-1",
                file_path="/path/narration.wav",
                duration_seconds=val,
            )
        assert "Float field must be a finite number" in str(exc_info.value)

        # VideoAsset - duration_seconds
        with pytest.raises(ValidationError) as exc_info:
            VideoAsset(
                asset_id="vid-1",
                file_path="/path/video.mp4",
                duration_seconds=val,
            )
        assert "Float field must be a finite number" in str(exc_info.value)

        # RenderSegment - start_time
        with pytest.raises(ValidationError) as exc_info:
            RenderSegment(
                segment_id="seg-1",
                segment_type="intro",
                start_time=val,
                end_time=10.0,
                duration=10.0,
                asset_references=[ref1],
            )
        assert "Float field must be a finite number" in str(exc_info.value)

        # RenderSegment - end_time
        with pytest.raises(ValidationError) as exc_info:
            RenderSegment(
                segment_id="seg-1",
                segment_type="intro",
                start_time=0.0,
                end_time=val,
                duration=10.0,
                asset_references=[ref1],
            )
        assert "Float field must be a finite number" in str(exc_info.value)

        # RenderSegment - duration
        with pytest.raises(ValidationError) as exc_info:
            RenderSegment(
                segment_id="seg-1",
                segment_type="intro",
                start_time=0.0,
                end_time=10.0,
                duration=val,
                asset_references=[ref1],
            )
        assert "Float field must be a finite number" in str(exc_info.value)

        # RenderSegment - volume
        with pytest.raises(ValidationError) as exc_info:
            RenderSegment(
                segment_id="seg-1",
                segment_type="intro",
                start_time=0.0,
                end_time=10.0,
                duration=10.0,
                volume=val,
                asset_references=[ref1],
            )
        assert "Float field must be a finite number" in str(exc_info.value)

        # RenderManifest - total_duration
        with pytest.raises(ValidationError) as exc_info:
            RenderManifest(
                pipeline_run_id="run-1",
                slug="test-slug",
                segments=[],
                total_duration=val,
            )
        assert "Float field must be a finite number" in str(exc_info.value)

        # AssembledVideo - total_duration_seconds
        with pytest.raises(ValidationError) as exc_info:
            AssembledVideo(
                slug="test-slug",
                final_video_path="/path/final.mp4",
                total_duration_seconds=val,
            )
        assert "Float field must be a finite number" in str(exc_info.value)


def test_whitespace_string_list_validation():
    """Verify that passing whitespace-only elements in string lists raises ValidationError."""
    whitespace_list = ["   "]

    sec1 = PlanSection(
        section_id="sec-1",
        section_type="intro",
        title="Intro",
        narration="Hello",
        estimated_duration=10.0,
    )

    # VideoMetadata tags
    with pytest.raises(ValidationError) as exc_info:
        VideoMetadata(
            title="Title",
            description="Desc",
            slug="test-slug",
            tags=whitespace_list,
        )
    assert "List item cannot be empty or whitespace only" in str(exc_info.value)

    # SEOMetadata tags
    with pytest.raises(ValidationError) as exc_info:
        SEOMetadata(
            youtube_title="Title",
            youtube_description="Desc",
            tags=whitespace_list,
        )
    assert "List item cannot be empty or whitespace only" in str(exc_info.value)

    # PlanSection visual_cue_ids
    with pytest.raises(ValidationError) as exc_info:
        PlanSection(
            section_id="sec-1",
            section_type="intro",
            title="Intro",
            narration="Hello",
            estimated_duration=10.0,
            visual_cue_ids=whitespace_list,
        )
    assert "List item cannot be empty or whitespace only" in str(exc_info.value)

    # EducationalPlan learning_objectives
    with pytest.raises(ValidationError) as exc_info:
        EducationalPlan(
            topic="Topic",
            slug="test-slug",
            learning_objectives=whitespace_list,
            sections=[sec1],
            estimated_total_duration=10.0,
        )
    assert "List item cannot be empty or whitespace only" in str(exc_info.value)

    # EducationalPlan prerequisites
    with pytest.raises(ValidationError) as exc_info:
        EducationalPlan(
            topic="Topic",
            slug="test-slug",
            learning_objectives=["Valid Obj"],
            prerequisites=whitespace_list,
            sections=[sec1],
            estimated_total_duration=10.0,
        )
    assert "List item cannot be empty or whitespace only" in str(exc_info.value)

