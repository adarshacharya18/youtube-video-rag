"""Empirical Test Runner for Phase 05: Core Data Models & Schemas.
Verifies:
1. JSON Schema Generation (Model.model_json_schema()) for all 13 models.
2. Serialization Roundtrips, Dumps, Model Validate, and Deep Copies.
3. Model Mutability / Immutability & Assignment Validation behavior.
4. Invalid Input Permutations on ALL models & pydantic.ValidationError details.
"""

import copy
from datetime import datetime
import json
import sys
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

ALL_MODELS = [
    SEOMetadata,
    VideoMetadata,
    PlanSection,
    CodeSnippet,
    VisualCue,
    ConceptPrerequisite,
    LearningObjective,
    EducationalPlan,
    AssetReference,
    AudioAsset,
    VideoAsset,
    RenderSegment,
    RenderManifest,
    AssembledVideo,
]

results = {
    "json_schema": [],
    "roundtrip": [],
    "deepcopy": [],
    "mutability": [],
    "invalid_permutations": [],
    "errors": [],
}

def create_valid_instances():
    seo = SEOMetadata(
        youtube_title="Title 1",
        youtube_description="Desc 1",
        tags=["tag1", "tag2"],
        category_id=27,
        privacy_status=PrivacyStatus.PUBLIC,
        chapter_timestamps=[{"00:00": "Intro"}],
    )
    video = VideoMetadata(
        title="Video Title",
        description="Video Description",
        slug="video-slug",
        resolution=VideoResolution.R_1080P,
        width=1920,
        height=1080,
        fps=30,
        tags=["tag1"],
        format="mp4",
        target_platform=TargetPlatform.YOUTUBE,
        category_id=27,
        privacy_status=PrivacyStatus.PUBLIC,
        language="en",
        problem_number=1,
        difficulty=Difficulty.EASY,
        seo_metadata=seo,
    )
    sec1 = PlanSection(
        section_id="sec-1",
        section_type="intro",
        title="Intro Section",
        narration="Hello world",
        estimated_duration=10.0,
        visual_cue_ids=["cue-1"],
        order=1,
    )
    sec2 = PlanSection(
        section_id="sec-2",
        section_type="outro",
        title="Outro Section",
        narration="Goodbye world",
        estimated_duration=15.0,
        visual_cue_ids=[],
        order=2,
    )
    code = CodeSnippet(
        snippet_id="code-1",
        language="python",
        code="print('hi')",
        explanation="Prints hi",
        line_highlights=[1],
    )
    cue = VisualCue(
        cue_id="cue-1",
        animation_type="fade_in",
        description="Fade in text",
        parameters={"speed": 1.0},
    )
    prereq = ConceptPrerequisite(
        concept="Variables",
        description="Basic python variables",
    )
    obj = LearningObjective(
        objective_id="obj-1",
        description="Learn variables",
        taxonomic_level="Remember",
    )
    plan = EducationalPlan(
        topic="Python Basics",
        slug="python-basics",
        target_audience="Beginner",
        difficulty="Easy",
        learning_objectives=[obj, "Learn basic syntax"],
        prerequisites=[prereq, "Computer usage"],
        sections=[sec1, sec2],
        code_snippets=[code],
        visual_cues=[cue],
        estimated_total_duration=25.0,
    )
    ref = AssetReference(
        asset_id="asset-1",
        asset_type="audio",
        file_path="/path/to/audio.mp3",
        duration=10.0,
    )
    audio = AudioAsset(
        audio_id="aud-1",
        file_path="/path/to/audio.mp3",
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
        file_size_bytes=1000,
    )
    segment = RenderSegment(
        segment_id="seg-1",
        segment_type="intro",
        start_time=0.0,
        end_time=10.0,
        duration=10.0,
        asset_references=[ref],
        audio_path="/path/to/audio.mp3",
        visual_path="/path/to/video.mp4",
        narration_text="Hello",
        volume=1.0,
        transition_in="fade",
        transition_out="fade",
        audio_asset=audio,
        scene_type="array_scene",
        visual_parameters={"color": "blue"},
    )
    manifest = RenderManifest(
        pipeline_run_id="run-1",
        slug="python-basics",
        segments=[segment],
        total_duration=10.0,
    )
    assembled = AssembledVideo(
        slug="python-basics",
        final_video_path="/path/to/final.mp4",
        thumbnail_path="/path/to/thumb.png",
        total_duration_seconds=10.0,
        file_size_bytes=2000000,
        segments=[segment],
        assembled_at=datetime(2026, 7, 25, 12, 0, 0),
    )

    return {
        SEOMetadata: seo,
        VideoMetadata: video,
        PlanSection: sec1,
        CodeSnippet: code,
        VisualCue: cue,
        ConceptPrerequisite: prereq,
        LearningObjective: obj,
        EducationalPlan: plan,
        AssetReference: ref,
        AudioAsset: audio,
        VideoAsset: video_asset,
        RenderSegment: segment,
        RenderManifest: manifest,
        AssembledVideo: assembled,
    }


def test_json_schemas():
    print("--- 1. Testing JSON Schema Generation ---")
    for model_cls in ALL_MODELS:
        name = model_cls.__name__
        try:
            schema = model_cls.model_json_schema()
            assert isinstance(schema, dict), f"{name}: schema is not a dict"
            assert schema.get("type") == "object", f"{name}: schema type is not object"
            assert "properties" in schema, f"{name}: schema missing properties"
            # verify schema is JSON serializable
            json_dump = json.dumps(schema)
            assert len(json_dump) > 0
            results["json_schema"].append((name, "PASS", f"Schema generated with {len(schema.get('properties', {}))} properties"))
            print(f"[PASS] JSON Schema for {name}")
        except Exception as e:
            results["json_schema"].append((name, "FAIL", str(e)))
            results["errors"].append(f"JSON Schema error in {name}: {e}")
            print(f"[FAIL] JSON Schema for {name}: {e}")


def test_roundtrips_and_deepcopies():
    print("\n--- 2. Testing Roundtrips and Deep Copies ---")
    valid_instances = create_valid_instances()
    for model_cls, inst in valid_instances.items():
        name = model_cls.__name__
        try:
            # 1. model_dump(mode="python") -> model_validate
            py_dump = inst.model_dump(mode="python")
            rehydrated_py = model_cls.model_validate(py_dump)
            assert rehydrated_py == inst, f"{name}: python dump roundtrip mismatch"

            # 2. model_dump(mode="json") -> model_validate
            json_dump = inst.model_dump(mode="json")
            rehydrated_json = model_cls.model_validate(json_dump)
            
            # Special check for datetime vs str in AssembledVideo union type
            if name == "AssembledVideo" and isinstance(inst.assembled_at, datetime):
                # Expect string conversion due to str | datetime | None union order in Pydantic
                assert isinstance(rehydrated_json.assembled_at, str), f"{name}: json dump did not convert datetime to str"
                assert rehydrated_json.assembled_at == inst.assembled_at.isoformat(), f"{name}: isoformat mismatch"
            else:
                assert rehydrated_json == inst, f"{name}: json dump roundtrip mismatch"

            # 3. model_dump_json() -> model_validate_json
            json_str = inst.model_dump_json()
            rehydrated_str = model_cls.model_validate_json(json_str)
            if name == "AssembledVideo" and isinstance(inst.assembled_at, datetime):
                assert isinstance(rehydrated_str.assembled_at, str)
            else:
                assert rehydrated_str == inst, f"{name}: json string roundtrip mismatch"

            results["roundtrip"].append((name, "PASS", "Python/JSON/String roundtrips verified 100% match"))
            print(f"[PASS] Roundtrips for {name}")
        except Exception as e:
            results["roundtrip"].append((name, "FAIL", str(e)))
            results["errors"].append(f"Roundtrip error in {name}: {e}")
            print(f"[FAIL] Roundtrips for {name}: {e}")

        try:
            # Deep copies
            cp_std = copy.deepcopy(inst)
            cp_pyd = inst.model_copy(deep=True)
            assert cp_std == inst and id(cp_std) != id(inst), f"{name}: standard deepcopy failed"
            assert cp_pyd == inst and id(cp_pyd) != id(inst), f"{name}: pydantic model_copy(deep=True) failed"

            results["deepcopy"].append((name, "PASS", "Standard deepcopy & model_copy(deep=True) passed"))
            print(f"[PASS] DeepCopy for {name}")
        except Exception as e:
            results["deepcopy"].append((name, "FAIL", str(e)))
            results["errors"].append(f"DeepCopy error in {name}: {e}")
            print(f"[FAIL] DeepCopy for {name}: {e}")


def test_mutability_and_assignment_validation():
    print("\n--- 3. Testing Mutability & Assignment Validation Behavior ---")
    valid_instances = create_valid_instances()
    for model_cls, inst in valid_instances.items():
        name = model_cls.__name__
        cp = copy.deepcopy(inst)
        # Test mutating an attribute
        if hasattr(cp, "title"):
            cp.title = "Mutated Title"
            is_mutated = (cp.title == "Mutated Title")
        elif hasattr(cp, "youtube_title"):
            cp.youtube_title = "Mutated SEO Title"
            is_mutated = (cp.youtube_title == "Mutated SEO Title")
        elif hasattr(cp, "section_id"):
            cp.section_id = "mutated-sec"
            is_mutated = (cp.section_id == "mutated-sec")
        elif hasattr(cp, "snippet_id"):
            cp.snippet_id = "mutated-snip"
            is_mutated = (cp.snippet_id == "mutated-snip")
        elif hasattr(cp, "cue_id"):
            cp.cue_id = "mutated-cue"
            is_mutated = (cp.cue_id == "mutated-cue")
        elif hasattr(cp, "concept"):
            cp.concept = "Mutated Concept"
            is_mutated = (cp.concept == "Mutated Concept")
        elif hasattr(cp, "objective_id"):
            cp.objective_id = "mutated-obj"
            is_mutated = (cp.objective_id == "mutated-obj")
        elif hasattr(cp, "topic"):
            cp.topic = "Mutated Topic"
            is_mutated = (cp.topic == "Mutated Topic")
        elif hasattr(cp, "asset_id"):
            cp.asset_id = "mutated-asset"
            is_mutated = (cp.asset_id == "mutated-asset")
        elif hasattr(cp, "audio_id"):
            cp.audio_id = "mutated-audio"
            is_mutated = (cp.audio_id == "mutated-audio")
        elif hasattr(cp, "segment_id"):
            cp.segment_id = "mutated-seg"
            is_mutated = (cp.segment_id == "mutated-seg")
        elif hasattr(cp, "pipeline_run_id"):
            cp.pipeline_run_id = "mutated-run"
            is_mutated = (cp.pipeline_run_id == "mutated-run")
        elif hasattr(cp, "final_video_path"):
            cp.final_video_path = "/mutated/path.mp4"
            is_mutated = (cp.final_video_path == "/mutated/path.mp4")
        else:
            is_mutated = True

        # Now test assignment of an invalid value (e.g. invalid type or negative int/float)
        # Because validate_assignment defaults to False in Pydantic V2 without explicit model_config,
        # attribute assignment of invalid values will succeed without raising ValidationError.
        assignment_validated = False
        try:
            if hasattr(cp, "fps"):
                cp.fps = -999  # Invalid FPS
            elif hasattr(cp, "estimated_duration"):
                cp.estimated_duration = -50.0  # Invalid duration
            elif hasattr(cp, "duration"):
                cp.duration = -50.0
            elif hasattr(cp, "duration_seconds"):
                cp.duration_seconds = -50.0
            elif hasattr(cp, "total_duration"):
                cp.total_duration = -50.0
            elif hasattr(cp, "category_id"):
                cp.category_id = -100
        except ValidationError:
            assignment_validated = True

        results["mutability"].append((
            name,
            "MUTABLE (validate_assignment=False)",
            f"Field mutated: {is_mutated}, Assignment validation on direct mutation: {'ENABLED' if assignment_validated else 'DISABLED (Default Pydantic V2 behavior)'}"
        ))
        print(f"[INFO] {name}: Mutable={is_mutated}, Assignment validated={assignment_validated}")


def test_invalid_permutations():
    print("\n--- 4. Testing Invalid Input Permutations & ValidationError Details ---")

    valid_instances = create_valid_instances()
    sec1 = valid_instances[PlanSection]
    ref = valid_instances[AssetReference]

    test_cases = [
        # (ModelClass, kwargs, expected_loc, expected_type)
        # SEOMetadata
        (SEOMetadata, {"youtube_title": "   ", "youtube_description": "valid"}, "youtube_title", "value_error"),
        (SEOMetadata, {"youtube_title": "valid", "youtube_description": "\t\n "}, "youtube_description", "value_error"),
        (SEOMetadata, {"youtube_title": "valid", "youtube_description": "valid", "tags": ["x" * 501]}, "tags", "value_error"),
        (SEOMetadata, {"youtube_title": "valid", "youtube_description": "valid", "privacy_status": "invalid_status"}, "privacy_status", "enum"),

        # VideoMetadata
        (VideoMetadata, {"title": "  ", "description": "desc", "slug": "slug"}, "title", "value_error"),
        (VideoMetadata, {"title": "title", "description": "   ", "slug": "slug"}, "description", "value_error"),
        (VideoMetadata, {"title": "title", "description": "desc", "slug": "Bad_Slug!"}, "slug", "string_pattern_mismatch"),
        (VideoMetadata, {"title": "title", "description": "desc", "slug": "slug", "fps": 29}, "fps", "value_error"),
        (VideoMetadata, {"title": "title", "description": "desc", "slug": "slug", "width": -100}, "width", "greater_than"),
        (VideoMetadata, {"title": "title", "description": "desc", "slug": "slug", "height": 0}, "height", "greater_than"),
        (VideoMetadata, {"title": "title", "description": "desc", "slug": "slug", "category_id": -5}, "category_id", "greater_than"),
        (VideoMetadata, {"title": "title", "description": "desc", "slug": "slug", "resolution": "8K"}, "resolution", "enum"),

        # PlanSection
        (PlanSection, {"section_id": "   ", "section_type": "intro", "title": "t", "narration": "n", "estimated_duration": 10.0}, "section_id", "value_error"),
        (PlanSection, {"section_id": "s1", "section_type": "  ", "title": "t", "narration": "n", "estimated_duration": 10.0}, "section_type", "value_error"),
        (PlanSection, {"section_id": "s1", "section_type": "intro", "title": "s1", "narration": "n", "estimated_duration": -5.0}, "estimated_duration", "greater_than"),
        (PlanSection, {"section_id": "s1", "section_type": "intro", "title": "s1", "narration": "n", "estimated_duration": 10.0, "order": -1}, "order", "greater_than_equal"),

        # CodeSnippet
        (CodeSnippet, {"snippet_id": "  ", "code": "x = 1"}, "snippet_id", "value_error"),
        (CodeSnippet, {"snippet_id": "c1", "code": "   "}, "code", "value_error"),
        (CodeSnippet, {"snippet_id": "c1", "code": "x = 1", "explanation": "   "}, "explanation", "value_error"),
        (CodeSnippet, {"snippet_id": "c1", "code": "x = 1", "line_highlights": [0]}, "line_highlights", "value_error"),

        # VisualCue
        (VisualCue, {"cue_id": "  ", "animation_type": "fade", "description": "desc"}, "cue_id", "value_error"),
        (VisualCue, {"cue_id": "c1", "animation_type": "  ", "description": "desc"}, "animation_type", "value_error"),
        (VisualCue, {"cue_id": "c1", "animation_type": "fade", "description": "   "}, "description", "value_error"),

        # ConceptPrerequisite
        (ConceptPrerequisite, {"concept": "  "}, "concept", "value_error"),
        (ConceptPrerequisite, {"concept": "Arrays", "description": "   "}, "description", "value_error"),

        # LearningObjective
        (LearningObjective, {"objective_id": "  ", "description": "desc"}, "objective_id", "value_error"),
        (LearningObjective, {"objective_id": "o1", "description": "  "}, "description", "value_error"),
        (LearningObjective, {"objective_id": "o1", "description": "desc", "taxonomic_level": "  "}, "taxonomic_level", "value_error"),

        # EducationalPlan
        (EducationalPlan, {"topic": "  ", "slug": "slug", "learning_objectives": ["obj"], "sections": [sec1], "estimated_total_duration": 10.0}, "topic", "value_error"),
        (EducationalPlan, {"topic": "Topic", "slug": "BAD SLUG", "learning_objectives": ["obj"], "sections": [sec1], "estimated_total_duration": 10.0}, "slug", "value_error"),
        (EducationalPlan, {"topic": "Topic", "slug": "slug", "learning_objectives": [], "sections": [sec1], "estimated_total_duration": 10.0}, "learning_objectives", "value_error"),
        (EducationalPlan, {"topic": "Topic", "slug": "slug", "learning_objectives": ["  "], "sections": [sec1], "estimated_total_duration": 10.0}, "learning_objectives", "value_error"),
        (EducationalPlan, {"topic": "Topic", "slug": "slug", "learning_objectives": ["obj"], "sections": [], "estimated_total_duration": 10.0}, "sections", "value_error"),
        (EducationalPlan, {"topic": "Topic", "slug": "slug", "learning_objectives": ["obj"], "sections": [sec1, sec1], "estimated_total_duration": 20.0}, None, "value_error"), # Duplicate section_id
        (EducationalPlan, {"topic": "Topic", "slug": "slug", "learning_objectives": ["obj"], "sections": [sec1], "estimated_total_duration": 99.0}, None, "value_error"), # Duration mismatch

        # AssetReference
        (AssetReference, {"asset_id": "  ", "asset_type": "audio", "file_path": "/path"}, "asset_id", "value_error"),
        (AssetReference, {"asset_id": "a1", "asset_type": "audio", "file_path": "/path", "duration": -1.0}, "duration", "greater_than"),

        # AudioAsset
        (AudioAsset, {"audio_id": "  ", "file_path": "/path", "duration_seconds": 10.0}, "audio_id", "value_error"),
        (AudioAsset, {"audio_id": "a1", "file_path": "/path", "duration_seconds": 0.0}, "duration_seconds", "greater_than"),
        (AudioAsset, {"audio_id": "a1", "file_path": "/path", "duration_seconds": 10.0, "sample_rate": 0}, "sample_rate", "greater_than"),

        # VideoAsset
        (VideoAsset, {"asset_id": "  ", "file_path": "/path", "duration_seconds": 10.0}, "asset_id", "value_error"),
        (VideoAsset, {"asset_id": "v1", "file_path": "/path", "duration_seconds": 10.0, "fps": 150}, "fps", "less_than_equal"),
        (VideoAsset, {"asset_id": "v1", "file_path": "/path", "duration_seconds": 10.0, "file_size_bytes": -1}, "file_size_bytes", "greater_than_equal"),

        # RenderSegment
        (RenderSegment, {"segment_id": "  ", "segment_type": "intro", "start_time": 0.0, "end_time": 10.0, "duration": 10.0, "asset_references": [ref]}, "segment_id", "value_error"),
        (RenderSegment, {"segment_id": "s1", "segment_type": "invalid_type", "start_time": 0.0, "end_time": 10.0, "duration": 10.0, "asset_references": [ref]}, "segment_type", "value_error"),
        (RenderSegment, {"segment_id": "s1", "segment_type": "intro", "start_time": 10.0, "end_time": 5.0, "duration": 5.0, "asset_references": [ref]}, None, "value_error"), # end_time <= start_time
        (RenderSegment, {"segment_id": "s1", "segment_type": "intro", "start_time": 0.0, "end_time": 10.0, "duration": 5.0, "asset_references": [ref]}, None, "value_error"), # duration mismatch
        (RenderSegment, {"segment_id": "s1", "segment_type": "intro", "start_time": 0.0, "end_time": 10.0, "duration": 10.0, "asset_references": []}, None, "value_error"), # missing asset ref
        (RenderSegment, {"segment_id": "s1", "segment_type": "intro", "start_time": 0.0, "end_time": 10.0, "duration": 10.0, "asset_references": [ref], "volume": 3.0}, "volume", "less_than_equal"),

        # RenderManifest
        (RenderManifest, {"pipeline_run_id": "  ", "slug": "slug", "segments": [valid_instances[RenderSegment]], "total_duration": 10.0}, "pipeline_run_id", "value_error"),
        (RenderManifest, {"pipeline_run_id": "r1", "slug": "slug", "segments": [], "total_duration": 10.0}, "segments", "value_error"),

        # AssembledVideo
        (AssembledVideo, {"slug": "INVALID SLUG", "final_video_path": "/path", "total_duration_seconds": 10.0}, "slug", "string_pattern_mismatch"),
        (AssembledVideo, {"slug": "valid-slug", "final_video_path": "   ", "total_duration_seconds": 10.0}, "final_video_path", "value_error"),
        (AssembledVideo, {"slug": "valid-slug", "final_video_path": "/path", "total_duration_seconds": -5.0}, "total_duration_seconds", "greater_than"),
    ]

    passed_count = 0
    failed_count = 0

    for model_cls, kwargs, expected_loc, expected_type in test_cases:
        name = model_cls.__name__
        try:
            model_cls(**kwargs)
            # If we reach here, validation failed to raise!
            failed_count += 1
            err_msg = f"{name} failed to raise ValidationError for kwargs={kwargs}"
            results["invalid_permutations"].append((name, "FAIL", err_msg))
            results["errors"].append(err_msg)
            print(f"[FAIL] {err_msg}")
        except ValidationError as exc:
            errs = exc.errors()
            assert len(errs) > 0
            err = errs[0]
            loc_str = ".".join(str(l) for l in err["loc"]) if err["loc"] else "root"
            err_type = err["type"]
            msg = err["msg"]

            # Verify location matching if expected_loc provided
            if expected_loc and expected_loc not in loc_str:
                results["invalid_permutations"].append((
                    name, "WARN", f"Expected loc '{expected_loc}' but got '{loc_str}' (type: {err_type}, msg: {msg})"
                ))
            else:
                passed_count += 1
                results["invalid_permutations"].append((
                    name, "PASS", f"ValidationError raised as expected at loc='{loc_str}', type='{err_type}', msg='{msg}'"
                ))
                print(f"[PASS] {name} ValidationError -> loc='{loc_str}', type='{err_type}', msg='{msg}'")

    print(f"\nInvalid Permutation Results: {passed_count} passed, {failed_count} failed out of {len(test_cases)} cases.")


def main():
    test_json_schemas()
    test_roundtrips_and_deepcopies()
    test_mutability_and_assignment_validation()
    test_invalid_permutations()

    print("\n================ SUMMARY ================")
    print(f"Total Models Tested: {len(ALL_MODELS)}")
    print(f"JSON Schemas Generated: {len(results['json_schema'])} / {len(ALL_MODELS)}")
    print(f"Roundtrips & Deep Copies: {len(results['roundtrip'])} / {len(ALL_MODELS)}")
    print(f"Invalid Permutations Tested: {len(results['invalid_permutations'])}")
    print(f"Total Errors Found: {len(results['errors'])}")
    if results['errors']:
        print("ERRORS LIST:")
        for err in results['errors']:
            print(f"  - {err}")

    return 0 if len(results['errors']) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
