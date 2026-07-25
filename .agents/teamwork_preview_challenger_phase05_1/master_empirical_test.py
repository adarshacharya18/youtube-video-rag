"""
Master Empirical Stress Test Harness for Phase 05 Core Data Models & State Ledger.
Exhaustively tests Pydantic V2 model validation, edge cases, failure modes, and SQLite State Ledger serialization.
"""

import math
import os
import sys
import tempfile
import traceback
from pathlib import Path
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
from src.core.orchestrator.state_ledger import StateLedger, PipelineError


class TestHarness:
    def __init__(self):
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0

    def add_result(self, category: str, name: str, passed: bool, detail: str):
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
        else:
            self.failed_tests += 1
        self.results.append({
            "category": category,
            "name": name,
            "passed": passed,
            "detail": detail
        })
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] [{category}] {name}: {detail}")


def run_video_metadata_tests(h: TestHarness):
    cat = "VideoMetadata"
    
    # 1. Valid instantiation & resolution auto-alignment
    try:
        v = VideoMetadata(
            title="Valid Title",
            description="Valid Description",
            slug="valid-slug",
            resolution=VideoResolution.R_1080P,
            width=3840,
            height=2160
        )
        # Resolution should be auto-updated to 4K because width/height is (3840, 2160)
        passed = (v.resolution == VideoResolution.R_4K)
        h.add_result(cat, "Resolution auto-alignment (1080p -> 4K)", passed, f"resolution={v.resolution}")
    except Exception as e:
        h.add_result(cat, "Resolution auto-alignment", False, str(e))

    # 2. Whitespace title
    try:
        VideoMetadata(title="   ", description="desc", slug="slug")
        h.add_result(cat, "Reject whitespace title", False, "Validation passed unexpectedly")
    except ValidationError:
        h.add_result(cat, "Reject whitespace title", True, "Raised ValidationError")
    except Exception as e:
        h.add_result(cat, "Reject whitespace title", False, f"Unexpected error {type(e).__name__}: {e}")

    # 3. Invalid slug pattern
    try:
        VideoMetadata(title="Title", description="desc", slug="Invalid_Slug!")
        h.add_result(cat, "Reject invalid slug pattern", False, "Validation passed unexpectedly")
    except ValidationError:
        h.add_result(cat, "Reject invalid slug pattern", True, "Raised ValidationError")

    # 4. Disallowed FPS
    try:
        VideoMetadata(title="Title", description="desc", slug="slug", fps=29)
        h.add_result(cat, "Reject disallowed FPS (29)", False, "Validation passed unexpectedly")
    except ValidationError:
        h.add_result(cat, "Reject disallowed FPS (29)", True, "Raised ValidationError")

    # 5. Tag total character limit (> 500)
    try:
        VideoMetadata(title="Title", description="desc", slug="slug", tags=["a" * 300, "b" * 201])
        h.add_result(cat, "Reject tags total len > 500", False, "Validation passed unexpectedly")
    except ValidationError:
        h.add_result(cat, "Reject tags total len > 500", True, "Raised ValidationError")

    # 6. Edge Case Finding: Whitespace tag items
    try:
        v = VideoMetadata(title="Title", description="desc", slug="slug", tags=["   "])
        h.add_result(cat, "Edge Case: Whitespace tag items allowed", True, f"Tags accepted: {v.tags} (Minor finding)")
    except ValidationError:
        h.add_result(cat, "Edge Case: Whitespace tag items allowed", False, "Rejected whitespace tag")


def run_educational_plan_tests(h: TestHarness):
    cat = "EducationalPlan"

    sec1 = PlanSection(
        section_id="sec-1",
        section_type="intro",
        title="Intro",
        narration="Hello world",
        estimated_duration=10.0,
        order=1
    )
    sec2 = PlanSection(
        section_id="sec-2",
        section_type="explanation",
        title="Explanation",
        narration="Deep dive into code",
        estimated_duration=20.0,
        order=2
    )

    # 1. Valid plan creation
    try:
        plan = EducationalPlan(
            topic="Binary Search",
            slug="binary-search",
            learning_objectives=["Master O(log N) search"],
            sections=[sec1, sec2],
            estimated_total_duration=30.0
        )
        h.add_result(cat, "Valid EducationalPlan creation", True, f"Total duration={plan.estimated_total_duration}")
    except Exception as e:
        h.add_result(cat, "Valid EducationalPlan creation", False, str(e))

    # 2. Duplicate section ID
    sec2_dup = PlanSection(
        section_id="sec-1",
        section_type="outro",
        title="Outro",
        narration="Bye",
        estimated_duration=20.0
    )
    try:
        EducationalPlan(
            topic="Binary Search",
            slug="binary-search",
            learning_objectives=["Obj"],
            sections=[sec1, sec2_dup],
            estimated_total_duration=30.0
        )
        h.add_result(cat, "Reject duplicate section_id", False, "Validation passed unexpectedly")
    except ValidationError as e:
        h.add_result(cat, "Reject duplicate section_id", True, f"Raised ValidationError: {e.errors()[0]['msg']}")

    # 3. Total duration mismatch (> 0.1s tolerance)
    try:
        EducationalPlan(
            topic="Binary Search",
            slug="binary-search",
            learning_objectives=["Obj"],
            sections=[sec1, sec2],
            estimated_total_duration=50.0  # 10 + 20 = 30 != 50
        )
        h.add_result(cat, "Reject duration mismatch (> 0.1s)", False, "Validation passed unexpectedly")
    except ValidationError:
        h.add_result(cat, "Reject duration mismatch (> 0.1s)", True, "Raised ValidationError")

    # 4. CodeSnippet line_highlights < 1
    try:
        CodeSnippet(snippet_id="c1", code="print(1)", line_highlights=[0])
        h.add_result(cat, "Reject CodeSnippet line_highlight < 1", False, "Validation passed unexpectedly")
    except ValidationError:
        h.add_result(cat, "Reject CodeSnippet line_highlight < 1", True, "Raised ValidationError")

    # 5. Edge Case Finding: Float Infinity math (inf - inf = nan)
    sec_inf1 = PlanSection(section_id="s1", section_type="intro", title="t", narration="n", estimated_duration=float("inf"))
    sec_inf2 = PlanSection(section_id="s2", section_type="outro", title="t", narration="n", estimated_duration=float("inf"))
    try:
        p_inf = EducationalPlan(
            topic="Inf Plan",
            slug="inf-plan",
            learning_objectives=["Obj"],
            sections=[sec_inf1, sec_inf2],
            estimated_total_duration=float("inf")
        )
        h.add_result(cat, "Edge Case Finding: float('inf') duration bypasses validation", False,
                     f"EducationalPlan accepted total_duration=inf and section duration=inf because inf - inf = nan (bypassing > 0.1 check)")
    except ValidationError:
        h.add_result(cat, "Edge Case Finding: float('inf') duration bypasses validation", True, "Rejected float inf")


def run_render_segment_tests(h: TestHarness):
    cat = "RenderSegment"
    ref = AssetReference(asset_id="a1", asset_type="audio", file_path="/path/audio.mp3", duration=10.0)

    # 1. Valid segment
    try:
        seg = RenderSegment(
            segment_id="seg-1",
            segment_type="intro",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            asset_references=[ref]
        )
        h.add_result(cat, "Valid RenderSegment creation", True, f"segment_id={seg.segment_id}")
    except Exception as e:
        h.add_result(cat, "Valid RenderSegment creation", False, str(e))

    # 2. end_time <= start_time
    try:
        RenderSegment(
            segment_id="seg-1",
            segment_type="intro",
            start_time=10.0,
            end_time=5.0,
            duration=5.0,
            asset_references=[ref]
        )
        h.add_result(cat, "Reject end_time <= start_time", False, "Validation passed unexpectedly")
    except ValidationError:
        h.add_result(cat, "Reject end_time <= start_time", True, "Raised ValidationError")

    # 3. duration != end_time - start_time (> 1e-3)
    try:
        RenderSegment(
            segment_id="seg-1",
            segment_type="intro",
            start_time=0.0,
            end_time=10.0,
            duration=4.0,
            asset_references=[ref]
        )
        h.add_result(cat, "Reject duration mismatch", False, "Validation passed unexpectedly")
    except ValidationError:
        h.add_result(cat, "Reject duration mismatch", True, "Raised ValidationError")

    # 4. No asset references provided
    try:
        RenderSegment(
            segment_id="seg-1",
            segment_type="intro",
            start_time=0.0,
            end_time=10.0,
            duration=10.0
        )
        h.add_result(cat, "Reject segment without any asset reference", False, "Validation passed unexpectedly")
    except ValidationError:
        h.add_result(cat, "Reject segment without any asset reference", True, "Raised ValidationError")

    # 5. Invalid segment_type enum
    try:
        RenderSegment(
            segment_id="seg-1",
            segment_type="invalid_type",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            asset_references=[ref]
        )
        h.add_result(cat, "Reject invalid segment_type", False, "Validation passed unexpectedly")
    except ValidationError:
        h.add_result(cat, "Reject invalid segment_type", True, "Raised ValidationError")


def run_state_ledger_tests(h: TestHarness):
    cat = "StateLedger"
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_ledger.db"
        with StateLedger(db_path) as ledger:
            # 1. Create run with complex metadata
            meta = {
                "title": "State Ledger Test",
                "unicode": "こんにちは 🚀",
                "nested": {"a": [1, 2, 3]},
                "null_val": None
            }
            try:
                run_id = ledger.create_run(slug="ledger-test", metadata=meta)
                run_rec = ledger.get_run(run_id)
                passed = (run_rec is not None and run_rec.metadata == meta)
                h.add_result(cat, "Create and retrieve pipeline run with metadata", passed, f"run_id={run_id}")
            except Exception as e:
                h.add_result(cat, "Create and retrieve pipeline run with metadata", False, str(e))

            # 2. Step execution lifecycle (start -> complete)
            try:
                step_id = ledger.record_step_start(run_id, "step_1", input_payload={"in": 1})
                ledger.record_step_completion(step_id, output_payload={"out": 2})
                step_rec = ledger.get_step_execution(step_id)
                passed = (step_rec is not None and step_rec.status == "COMPLETED" and step_rec.output_payload == {"out": 2})
                h.add_result(cat, "Step execution start and completion lifecycle", passed, f"step_id={step_id}")
            except Exception as e:
                h.add_result(cat, "Step execution start and completion lifecycle", False, str(e))

            # 3. Step failure lifecycle & run status update
            try:
                step_f_id = ledger.record_step_start(run_id, "failing_step")
                ledger.record_step_failure(step_f_id, error_message="Failed cleanly", error_details={"code": 500})
                step_f_rec = ledger.get_step_execution(step_f_id)
                run_after_f = ledger.get_run(run_id)
                passed = (step_f_rec.status == "FAILED" and run_after_f.status == "FAILED")
                h.add_result(cat, "Step execution failure & run status propagation", passed, "Run status updated to FAILED")
            except Exception as e:
                h.add_result(cat, "Step execution failure & run status propagation", False, str(e))

            # 4. Foreign key constraint violation on non-existent run ID
            try:
                ledger.record_step_start("non_existent_run_id", "step_x")
                h.add_result(cat, "Foreign key constraint enforcement on step start", False, "Did not raise PipelineError")
            except PipelineError:
                h.add_result(cat, "Foreign key constraint enforcement on step start", True, "Raised PipelineError as expected")


if __name__ == "__main__":
    h = TestHarness()
    print("==================================================")
    print("    RUNNING MASTER EMPIRICAL TEST SUITE           ")
    print("==================================================")
    run_video_metadata_tests(h)
    run_educational_plan_tests(h)
    run_render_segment_tests(h)
    run_state_ledger_tests(h)

    print("\n==================================================")
    print(f"SUMMARY: Total={h.total_tests}, Passed={h.passed_tests}, Failed={h.failed_tests}")
    print("==================================================")
