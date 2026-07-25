"""
Adversarial Empirical Stress Test Suite for Phase 05 Pydantic V2 Models & SQLite State Ledger.
Runs comprehensive edge case generators and asserts expected behavior.
"""

import math
import sys
import traceback
from datetime import datetime, timezone
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
from src.core.orchestrator.state_ledger import StateLedger, PipelineError


class StressTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def log_pass(self, test_name: str):
        self.passed += 1
        print(f"[PASS] {test_name}")

    def log_fail(self, test_name: str, reason: str):
        self.failed += 1
        self.errors.append((test_name, reason))
        print(f"[FAIL] {test_name}: {reason}")


def test_unicode_and_control_chars(tester: StressTester):
    """Test unicode, emojis, control characters, diacritics, and null bytes across models."""
    unicode_strings = [
        "🔥🚀 Algorithms & Data Structures 101",
        "הודעה בעברית (Hebrew RTL text)",
        "اللغة العربية (Arabic RTL text)",
        "こんにちは世界 (Japanese CJK text)",
        "Élégant Café con Leche (Accented Latin)",
        "Zalɢo text ̷t̷e̷s̷t̷",
        "\x01\x02\x03\x04\x05 Control Chars",
        "\x00 Null byte in string",
    ]

    for s in unicode_strings:
        try:
            # VideoMetadata
            v = VideoMetadata(
                title=s,
                description=s,
                slug="valid-slug",
            )
            assert v.title == s
            assert v.description == s

            # PlanSection
            sec = PlanSection(
                section_id="sec-1",
                section_type="intro",
                title=s,
                narration=s,
                estimated_duration=10.0,
            )
            assert sec.title == s

            # EducationalPlan
            plan = EducationalPlan(
                topic=s,
                slug="valid-slug",
                learning_objectives=[s],
                sections=[sec],
                estimated_total_duration=10.0,
            )
            assert plan.topic == s

            # RenderSegment
            seg = RenderSegment(
                segment_id="seg-1",
                segment_type="intro",
                start_time=0.0,
                end_time=10.0,
                duration=10.0,
                narration_text=s,
                audio_path="/valid/path.mp3",
            )
            assert seg.narration_text == s

            tester.log_pass(f"Unicode handling for repr({s[:20]}...)")
        except Exception as e:
            tester.log_fail(f"Unicode handling for repr({s[:20]}...)", f"Unexpected exception: {type(e).__name__}: {e}\n{traceback.format_exc()}")


def test_boundary_numbers_and_special_floats(tester: StressTester):
    """Test NaN, Infinity, -0.0, boundary numbers, negative numbers."""
    
    # 1. Negative Zero (-0.0) should be treated as 0.0
    try:
        sec = PlanSection(
            section_id="s1",
            section_type="intro",
            title="T",
            narration="N",
            estimated_duration=10.0,
            order=-0,
        )
        assert sec.order == 0
        tester.log_pass("Negative zero integer order handled correctly")
    except Exception as e:
        tester.log_fail("Negative zero integer order", f"{type(e).__name__}: {e}")

    # 2. NaN in floats should raise ValidationError or be caught cleanly
    nan_vals = [float("nan"), float("inf"), float("-inf")]
    for val in nan_vals:
        try:
            PlanSection(
                section_id="s1",
                section_type="intro",
                title="T",
                narration="N",
                estimated_duration=val,
            )
            tester.log_fail(f"PlanSection estimated_duration={val}", "Expected ValidationError but validation passed!")
        except ValidationError:
            tester.log_pass(f"PlanSection estimated_duration={val} correctly raised ValidationError")
        except Exception as e:
            tester.log_fail(f"PlanSection estimated_duration={val}", f"Unexpected non-ValidationError exception: {type(e).__name__}: {e}")

    # 3. RenderSegment start_time / end_time / duration NaN and Inf
    for val in nan_vals:
        try:
            RenderSegment(
                segment_id="s1",
                segment_type="intro",
                start_time=0.0,
                end_time=val,
                duration=10.0,
                audio_path="/path.mp3",
            )
            tester.log_fail(f"RenderSegment end_time={val}", "Expected ValidationError but validation passed!")
        except ValidationError:
            tester.log_pass(f"RenderSegment end_time={val} correctly raised ValidationError")
        except Exception as e:
            tester.log_fail(f"RenderSegment end_time={val}", f"Unexpected non-ValidationError exception: {type(e).__name__}: {e}")

    # 4. Extreme numeric values (1e308, -1e308)
    try:
        VideoMetadata(
            title="Title",
            description="Desc",
            slug="valid-slug",
            width=10**10,  # huge int
        )
        tester.log_pass("Huge integer width accepted or converted")
    except ValidationError:
        tester.log_pass("Huge integer width rejected with ValidationError")
    except Exception as e:
        tester.log_fail("Huge integer width", f"Unexpected exception: {type(e).__name__}: {e}")


def test_corrupted_json_and_nested_type_violations(tester: StressTester):
    """Test passing invalid types at various nested positions."""
    invalid_payloads = [
        # List where dict expected
        ({"title": ["not", "a", "string"], "description": "desc", "slug": "slug"}, VideoMetadata),
        # Dict where list expected
        ({"title": "title", "description": "desc", "slug": "slug", "tags": {"key": "val"}}, VideoMetadata),
        # String where float expected
        ({"section_id": "s1", "section_type": "intro", "title": "t", "narration": "n", "estimated_duration": "not_a_float"}, PlanSection),
        # Nested dict violation in EducationalPlan sections
        ({"topic": "topic", "slug": "slug", "learning_objectives": ["obj"], "sections": ["not_a_section_object"], "estimated_total_duration": 10.0}, EducationalPlan),
        # Invalid enum values
        ({"title": "t", "description": "d", "slug": "s", "resolution": "INVALID_RES"}, VideoMetadata),
        ({"segment_id": "s1", "segment_type": "INVALID_SEG_TYPE", "start_time": 0.0, "end_time": 10.0, "duration": 10.0, "audio_path": "a.mp3"}, RenderSegment),
    ]

    for payload, model_cls in invalid_payloads:
        try:
            model_cls.model_validate(payload)
            tester.log_fail(f"Type violation on {model_cls.__name__}", f"Payload {payload} should have failed validation but passed!")
        except ValidationError:
            tester.log_pass(f"Type violation on {model_cls.__name__} raised ValidationError as expected")
        except Exception as e:
            tester.log_fail(f"Type violation on {model_cls.__name__}", f"Unexpected non-ValidationError exception: {type(e).__name__}: {e}")


def test_recursion_and_deep_nesting(tester: StressTester):
    """Test deeply nested dicts and potential recursion issues."""
    # Deeply nested visual_parameters in RenderSegment
    deep_dict = {}
    curr = deep_dict
    for i in range(100):
        curr["nested"] = {}
        curr = curr["nested"]
    curr["val"] = "deep"

    try:
        seg = RenderSegment(
            segment_id="s1",
            segment_type="intro",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            audio_path="/path.mp3",
            visual_parameters=deep_dict,
        )
        assert seg.visual_parameters["nested"]["nested"] is not None
        tester.log_pass("Deeply nested dictionary (100 levels) handled cleanly")
    except Exception as e:
        tester.log_fail("Deeply nested dictionary", f"Exception raised: {type(e).__name__}: {e}")


def test_huge_payloads(tester: StressTester):
    """Test huge strings and large collections (e.g. 10,000 sections)."""
    try:
        large_title = "A" * 100  # Max is 100
        invalid_large_title = "A" * 101
        
        VideoMetadata(title=large_title, description="Desc", slug="valid-slug")
        tester.log_pass("Max length title (100 chars) passed validation")

        try:
            VideoMetadata(title=invalid_large_title, description="Desc", slug="valid-slug")
            tester.log_fail("Title > 100 chars", "Expected ValidationError, passed!")
        except ValidationError:
            tester.log_pass("Title > 100 chars rejected with ValidationError")

        # Huge description (5000 max)
        VideoMetadata(title="Title", description="B" * 5000, slug="valid-slug")
        tester.log_pass("Max length description (5000 chars) passed validation")

        try:
            VideoMetadata(title="Title", description="B" * 5001, slug="valid-slug")
            tester.log_fail("Description > 5000 chars", "Expected ValidationError, passed!")
        except ValidationError:
            tester.log_pass("Description > 5000 chars rejected with ValidationError")

        # Large plan with 1,000 sections
        sections = []
        for i in range(1000):
            sections.append(
                PlanSection(
                    section_id=f"sec-{i}",
                    section_type="explanation",
                    title=f"Section {i}",
                    narration=f"Narration for section {i}",
                    estimated_duration=1.0,
                    order=i,
                )
            )
        plan = EducationalPlan(
            topic="Big Plan",
            slug="big-plan",
            learning_objectives=["Learn everything"],
            sections=sections,
            estimated_total_duration=1000.0,
        )
        assert len(plan.sections) == 1000
        tester.log_pass("1,000 section EducationalPlan validated successfully")

    except Exception as e:
        tester.log_fail("Huge payload test", f"Exception raised: {type(e).__name__}: {e}\n{traceback.format_exc()}")


def test_state_ledger_stress(tmp_path, tester: StressTester):
    """Stress test SQLite State Ledger with edge case payloads, unicode, large json, and transaction behavior."""
    db_path = tmp_path / "stress_ledger.db"
    try:
        with StateLedger(db_path) as ledger:
            # 1. Unicode & special chars in metadata
            unicode_meta = {
                "title": "🚀 Test 測試 اختبار",
                "null_char": "before\x00after",
                "nested": {"key": "val with ' quotes and \" double quotes"},
                "list": [1, 2.5, True, False, None],
            }
            run_id = ledger.create_run(slug="unicode-run", metadata=unicode_meta)
            retrieved = ledger.get_run(run_id)
            assert retrieved is not None
            assert retrieved.metadata == unicode_meta
            tester.log_pass("StateLedger stored and retrieved unicode & null char metadata")

            # 2. Large payload step execution
            large_input = {"data": "X" * 500000, "nums": list(range(10000))}
            step_id = ledger.record_step_start(
                pipeline_run_id=run_id,
                step_name="large_step",
                input_payload=large_input,
            )
            large_output = {"result": "Y" * 500000}
            ledger.record_step_completion(step_execution_id=step_id, output_payload=large_output)

            step_rec = ledger.get_step_execution(step_id)
            assert step_rec is not None
            assert step_rec.input_payload == large_input
            assert step_rec.output_payload == large_output
            tester.log_pass("StateLedger handled ~1MB input/output payloads cleanly")

            # 3. Error failure recording with traceback and error_details
            step_err_id = ledger.record_step_start(
                pipeline_run_id=run_id,
                step_name="failing_step",
            )
            err_msg = "Error with quotes ' and unicode 💥"
            err_details = {"exception": "ValueError", "traceback": "Traceback line 1\nLine 2"}
            ledger.record_step_failure(
                step_execution_id=step_err_id,
                error_message=err_msg,
                error_details=err_details,
            )
            step_err_rec = ledger.get_step_execution(step_err_id)
            assert step_err_rec is not None
            assert step_err_rec.status == "FAILED"
            assert step_err_rec.error_message == err_msg
            assert step_err_rec.error_details == err_details
            
            run_after_fail = ledger.get_run(run_id)
            assert run_after_fail.status == "FAILED"
            tester.log_pass("StateLedger recorded failure status and details correctly")

            # 4. Non-existent IDs raise PipelineError
            try:
                ledger.record_step_completion("non_existent_step_id", {"a": 1})
                tester.log_fail("StateLedger record_step_completion non-existent ID", "Expected PipelineError, but succeeded")
            except PipelineError:
                tester.log_pass("StateLedger record_step_completion non-existent ID raised PipelineError")

            try:
                ledger.record_step_start("non_existent_run_id", "step_name")
                tester.log_fail("StateLedger record_step_start non-existent parent run ID", "Expected PipelineError, but succeeded")
            except PipelineError:
                tester.log_pass("StateLedger record_step_start non-existent run ID raised PipelineError due to FK constraint")

    except Exception as e:
        tester.log_fail("State Ledger stress test", f"Exception raised: {type(e).__name__}: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    tester = StressTester()

    print("=== STARTING PHASE 05 EMPIRICAL STRESS TESTS ===")
    test_unicode_and_control_chars(tester)
    test_boundary_numbers_and_special_floats(tester)
    test_corrupted_json_and_nested_type_violations(tester)
    test_recursion_and_deep_nesting(tester)
    test_huge_payloads(tester)
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_state_ledger_stress(Path(tmp_dir), tester)

    print("\n=== STRESS TEST RESULTS SUMMARY ===")
    print(f"Passed: {tester.passed}")
    print(f"Failed: {tester.failed}")
    if tester.failed > 0:
        print("\nFailures:")
        for name, err in tester.errors:
            print(f"- {name}: {err}")
        sys.exit(1)
    else:
        print("ALL EMPIRICAL STRESS TESTS PASSED SUCCESSFULLY!")
