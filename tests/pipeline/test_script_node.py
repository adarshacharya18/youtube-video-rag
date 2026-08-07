"""Test suite for ScriptGeneratorNode and Error-Feedback Retry Loop."""

import json
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.core.exceptions import ScriptGenerationError
from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.engine import WorkflowEngine
from src.models.script import (
    ComplexitySection,
    ContextSection,
    HookSection,
    ScriptSchema,
    SolutionSection,
    VisualCue,
    YouTubeScript,
)
from src.pipeline.nodes.script_generator_node import ScriptGeneratorNode


class MockLLMProvider:
    """Mock LLM provider returning predetermined responses and tracking prompt history."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.call_count = 0
        self.prompts_received: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts_received.append(prompt)
        if self.call_count >= len(self.responses):
            resp = self.responses[-1]
        else:
            resp = self.responses[self.call_count]
        self.call_count += 1
        return resp


@pytest.fixture
def valid_script_dict():
    """Return a valid YouTube script dictionary with full section visual cues."""
    cues_hook = [
        {
            "cue_id": "cue_h1",
            "animation_type": "title_card",
            "description": "Show Two Sum title card",
            "timestamp_seconds": 0.0,
            "parameters": {"title": "Two Sum", "duration": 5.0},
        },
        {
            "cue_id": "cue_h2",
            "animation_type": "title_card",
            "description": "Show Problem Statement",
            "timestamp_seconds": 5.0,
            "parameters": {"topic": "Target Sum", "duration": 5.0},
        },
        {
            "cue_id": "cue_h3",
            "animation_type": "title_card",
            "description": "Show Challenge Overview",
            "timestamp_seconds": 10.0,
            "parameters": {"difficulty": "Easy", "duration": 5.0},
        },
    ]
    cues_ctx = [
        {
            "cue_id": "cue_c1",
            "animation_type": "array_highlight",
            "description": "Show Input Array",
            "timestamp_seconds": 15.0,
            "parameters": {"array": [2, 7, 11, 15], "duration": 10.0},
        },
        {
            "cue_id": "cue_c2",
            "animation_type": "array_highlight",
            "description": "Show Target Pointer",
            "timestamp_seconds": 25.0,
            "parameters": {"array": [2, 7, 11, 15], "pointers": {"target": 9}, "duration": 10.0},
        },
        {
            "cue_id": "cue_c3",
            "animation_type": "array_highlight",
            "description": "Highlight Candidate Pair",
            "timestamp_seconds": 35.0,
            "parameters": {"array": [2, 7], "duration": 10.0},
        },
    ]
    cues_sol = [
        {
            "cue_id": "cue_s1",
            "animation_type": "hashmap_operation",
            "description": "Initialize HashMap",
            "timestamp_seconds": 45.0,
            "parameters": {"entries": {}, "action": "display", "duration": 15.0},
        },
        {
            "cue_id": "cue_s2",
            "animation_type": "hashmap_operation",
            "description": "Insert Complements",
            "timestamp_seconds": 60.0,
            "parameters": {"entries": {"2": 0}, "action": "put", "duration": 15.0},
        },
        {
            "cue_id": "cue_s3",
            "animation_type": "code_walkthrough",
            "description": "Execute Hash Lookup",
            "timestamp_seconds": 75.0,
            "parameters": {"code": "seen[n] = i", "lines": [1, 2], "duration": 15.0},
        },
    ]
    cues_cx = [
        {
            "cue_id": "cue_x1",
            "animation_type": "complexity_chart",
            "description": "Show Time Complexity",
            "timestamp_seconds": 90.0,
            "parameters": {"time_complexity": "O(N)", "duration": 3.3},
        },
        {
            "cue_id": "cue_x2",
            "animation_type": "complexity_chart",
            "description": "Show Space Complexity",
            "timestamp_seconds": 93.3,
            "parameters": {"space_complexity": "O(N)", "duration": 3.3},
        },
        {
            "cue_id": "cue_x3",
            "animation_type": "complexity_chart",
            "description": "Summary Comparison",
            "timestamp_seconds": 96.6,
            "parameters": {"time_complexity": "O(N)", "space_complexity": "O(N)", "duration": 3.4},
        },
    ]
    all_cues = cues_hook + cues_ctx + cues_sol + cues_cx
    return {
        "topic": "Two Sum",
        "slug": "two-sum",
        "difficulty": "Easy",
        "hook": {
            "title": "Hook",
            "narration": "Can you solve Two Sum in linear time?",
            "visual_cues": cues_hook,
            "estimated_duration": 15.0,
        },
        "context": {
            "title": "Context",
            "narration": "Given an array of integers and a target sum, find two numbers that add up to target.",
            "visual_cues": cues_ctx,
            "estimated_duration": 30.0,
        },
        "solution": {
            "title": "Solution",
            "narration": "Use a hash map to store complements for single-pass O(N) lookup.",
            "code_snippet": "def twoSum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i",
            "visual_cues": cues_sol,
            "estimated_duration": 45.0,
        },
        "complexity": {
            "title": "Complexity",
            "narration": "Time complexity is O(N) and space complexity is O(N).",
            "time_complexity": "O(N)",
            "space_complexity": "O(N)",
            "visual_cues": cues_cx,
            "estimated_duration": 10.0,
        },
        "total_duration": 100.0,
        "spoken_narration": [
            "Can you solve Two Sum in linear time?",
            "Given an array of integers and a target sum, find two numbers that add up to target.",
            "Use a hash map to store complements for single-pass O(N) lookup.",
            "Time complexity is O(N) and space complexity is O(N).",
        ],
        "visual_cues": all_cues,
    }


def test_script_generator_node_name():
    """Verify that node name property returns 'script_generator'."""
    node = ScriptGeneratorNode()
    assert node.name == "script_generator"


def test_script_generator_node_error_feedback_retry_success(valid_script_dict):
    """Verify that ScriptGeneratorNode catches invalid JSON on call 1, passes error string to call 2, and succeeds."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run(slug="two-sum")

    corrupted_json_call_1 = '{"topic": "Two Sum", "slug": "two-sum", "hook": {"title": "Hook", "narration": "Intro"}, INVALID_JSON_TRUNCATED'
    valid_json_call_2 = json.dumps(valid_script_dict)

    mock_llm = MockLLMProvider([corrupted_json_call_1, valid_json_call_2])
    node = ScriptGeneratorNode(llm_provider=mock_llm, max_retries=3)

    output = node.execute(run_id=run_id, ledger=ledger)

    # 1. Verify LLM call count
    assert mock_llm.call_count == 2
    assert len(mock_llm.prompts_received) == 2

    # 2. Verify Call 1 received initial prompt and Call 2 received error feedback
    call_1_prompt = mock_llm.prompts_received[0]
    call_2_prompt = mock_llm.prompts_received[1]

    assert "PREVIOUS ATTEMPT FAILED WITH VALIDATION ERROR" in call_2_prompt
    assert "Unterminated string" in call_2_prompt or "Expecting property name" in call_2_prompt or "JSON" in call_2_prompt

    # 3. Verify execution output payload
    assert output["status"] == "completed"
    assert output["slug"] == "two-sum"
    assert output["topic"] == "Two Sum"
    assert "script" in output
    assert output["script"]["total_duration"] == 100.0


def test_script_generator_node_schema_validation_retry(valid_script_dict):
    """Verify retry trigger when JSON is syntactically valid but fails Pydantic schema validation."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run(slug="two-sum")

    # JSON missing required 'complexity' field
    invalid_schema_call_1 = json.dumps(
        {
            "topic": "Two Sum",
            "slug": "invalid slug with spaces",
            "hook": {"title": "Hook", "narration": "Intro", "estimated_duration": 10.0},
            "context": {"title": "Context", "narration": "Context", "estimated_duration": 20.0},
            "solution": {"title": "Solution", "narration": "Solution", "estimated_duration": 30.0},
            "total_duration": 60.0,
        }
    )
    valid_json_call_2 = json.dumps(valid_script_dict)

    mock_llm = MockLLMProvider([invalid_schema_call_1, valid_json_call_2])
    node = ScriptGeneratorNode(llm_provider=mock_llm, max_retries=3)

    output = node.execute(run_id=run_id, ledger=ledger)

    assert mock_llm.call_count == 2
    call_2_prompt = mock_llm.prompts_received[1]
    assert "PREVIOUS ATTEMPT FAILED WITH VALIDATION ERROR" in call_2_prompt
    assert output["status"] == "completed"


def test_script_generator_node_max_retries_exhausted():
    """Verify that ScriptGenerationError is raised when max retries are exhausted."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run(slug="two-sum")

    corrupted_json = "NOT_JSON_AT_ALL"
    mock_llm = MockLLMProvider([corrupted_json, corrupted_json, corrupted_json])
    node = ScriptGeneratorNode(llm_provider=mock_llm, max_retries=3)

    with pytest.raises(ScriptGenerationError) as exc_info:
        node.execute(run_id=run_id, ledger=ledger)

    assert "failed after 3 attempts" in str(exc_info.value)
    assert mock_llm.call_count == 3


def test_script_generator_workflow_engine_integration(valid_script_dict):
    """Verify end-to-end integration with WorkflowEngine and StateLedger recording."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run(slug="two-sum")

    valid_json = json.dumps(valid_script_dict)
    mock_llm = MockLLMProvider([valid_json])
    node = ScriptGeneratorNode(llm_provider=mock_llm, max_retries=3)

    engine = WorkflowEngine(nodes=[node], ledger=ledger)
    result = engine.run(run_id=run_id)

    assert result.success is True
    assert "script_generator" in result.completed_steps
    assert result.outputs["script_generator"]["slug"] == "two-sum"

    # Verify step recorded in StateLedger DB
    completed_steps = ledger.get_completed_steps(run_id)
    assert "script_generator" in completed_steps
    assert completed_steps["script_generator"].output_payload["status"] == "completed"


def test_youtube_script_schema_validation(valid_script_dict):
    """Verify Pydantic model invariants, slug regex, and schema export capability."""
    script = YouTubeScript.model_validate(valid_script_dict)
    assert script.slug == "two-sum"
    assert script.total_duration == 100.0
    assert len(script.spoken_narration) == 4

    # Export schema verification
    schema_json = YouTubeScript.export_schema_json()
    assert isinstance(schema_json, str)
    assert "YouTubeScript" in schema_json or "properties" in schema_json

    schema_dict = YouTubeScript.export_schema_dict()
    assert isinstance(schema_dict, dict)
    assert "properties" in schema_dict

    # Verify duration mismatch raises ValidationError
    invalid_duration_dict = dict(valid_script_dict)
    invalid_duration_dict["total_duration"] = 500.0  # Mismatch with sum (100.0)

    with pytest.raises(ValidationError) as exc_info:
        YouTubeScript.model_validate(invalid_duration_dict)

    assert "total_duration" in str(exc_info.value) or "sum of section durations" in str(exc_info.value)


def test_multiple_consecutive_errors_before_success(valid_script_dict):
    """Adversarial Test: 3 consecutive different errors (empty string, incomplete json, schema mismatch) before success on 4th attempt."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run(slug="two-sum")

    err1_empty = ""
    err2_incomplete_json = '{"topic": "Two Sum", "slug": "two-sum"'
    err3_schema_mismatch = json.dumps({"topic": "Two Sum", "slug": "two-sum"})  # missing hook, context, etc.
    success_json = json.dumps(valid_script_dict)

    mock_llm = MockLLMProvider([err1_empty, err2_incomplete_json, err3_schema_mismatch, success_json])
    node = ScriptGeneratorNode(llm_provider=mock_llm, max_retries=4)

    output = node.execute(run_id=run_id, ledger=ledger)

    assert mock_llm.call_count == 4
    assert output["status"] == "completed"
    assert output["slug"] == "two-sum"

    # Verify prompt accumulation
    prompts = mock_llm.prompts_received
    assert len(prompts) == 4
    assert "PREVIOUS ATTEMPT FAILED WITH VALIDATION ERROR" not in prompts[0]
    assert "PREVIOUS ATTEMPT FAILED WITH VALIDATION ERROR" in prompts[1]
    assert "PREVIOUS ATTEMPT FAILED WITH VALIDATION ERROR" in prompts[2]
    assert "PREVIOUS ATTEMPT FAILED WITH VALIDATION ERROR" in prompts[3]


def test_empty_and_corrupted_llm_responses():
    """Adversarial Test: Empty strings, whitespace, null, integer, list, and HTML responses."""
    corrupted_inputs = [
        "",
        "   ",
        "null",
        "<html>500 Internal Server Error</html>",
        "[1, 2, 3]",
        12345,
        None,
    ]

    for corrupt_val in corrupted_inputs:
        mock_llm = MagicMock()
        mock_llm.generate.return_value = corrupt_val
        node = ScriptGeneratorNode(llm_provider=mock_llm, max_retries=1)

        with pytest.raises(ScriptGenerationError):
            node.execute(run_id="run_test", ledger=None)


def test_prompt_feedback_accumulation(valid_script_dict):
    """Adversarial Test: Verify feedback accumulation across multiple retry attempts."""
    err1 = "INVALID_JSON_1"
    err2 = '{"invalid": "schema"}'
    success = json.dumps(valid_script_dict)

    mock_llm = MockLLMProvider([err1, err2, success])
    node = ScriptGeneratorNode(llm_provider=mock_llm, max_retries=3)

    output = node.execute(run_id="run_test", ledger=None)

    assert mock_llm.call_count == 3
    prompts = mock_llm.prompts_received

    # Attempt 1: Base prompt only
    assert "PREVIOUS ATTEMPT FAILED WITH VALIDATION ERROR" not in prompts[0]

    # Attempt 2: Base prompt + feedback from err1
    assert "PREVIOUS ATTEMPT FAILED WITH VALIDATION ERROR" in prompts[1]
    assert "Expecting value" in prompts[1] or "JSON" in prompts[1]

    # Attempt 3: Contains feedback from err2 as well
    assert prompts[2].count("=== PREVIOUS ATTEMPT FAILED WITH VALIDATION ERROR ===") == 2
    assert output["status"] == "completed"


def test_llm_provider_interface_variants(valid_script_dict):
    """Adversarial Test: Test generate_structured, invoke, callable, None, and invalid provider types."""
    # 1. generate_structured provider
    script_obj = YouTubeScript.model_validate(valid_script_dict)
    class StructProvider:
        def generate_structured(self, prompt, schema):
            return script_obj
    node1 = ScriptGeneratorNode(llm_provider=StructProvider(), max_retries=1)
    out1 = node1.execute(run_id="r1", ledger=None)
    assert out1["status"] == "completed"

    # 2. invoke provider
    class InvokeProvider:
        def invoke(self, prompt):
            return json.dumps(valid_script_dict)
    node2 = ScriptGeneratorNode(llm_provider=InvokeProvider(), max_retries=1)
    out2 = node2.execute(run_id="r2", ledger=None)
    assert out2["status"] == "completed"

    # 3. callable provider
    callable_provider = lambda p: valid_script_dict
    node3 = ScriptGeneratorNode(llm_provider=callable_provider, max_retries=1)
    out3 = node3.execute(run_id="r3", ledger=None)
    assert out3["status"] == "completed"

    # 4. None provider
    node4 = ScriptGeneratorNode(llm_provider=None, max_retries=1)
    with pytest.raises(ScriptGenerationError) as exc4:
        node4.execute(run_id="r4", ledger=None)
    assert "No LLM provider configured" in str(exc4.value)

    # 5. Unsupported type provider
    node5 = ScriptGeneratorNode(llm_provider=12345, max_retries=1)
    with pytest.raises(ScriptGenerationError) as exc5:
        node5.execute(run_id="r5", ledger=None)
    assert "Unsupported LLM provider type" in str(exc5.value)


def test_state_ledger_input_context_retrieval(valid_script_dict):
    """Adversarial Test: Verify ScriptGeneratorNode retrieves problem details from StateLedger step outputs."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run(slug="three-sum")

    # Record step output for plan using correct StateLedger API
    plan_output = {
        "slug": "three-sum",
        "topic": "Three Sum Problem",
        "difficulty": "Medium",
        "problem_description": "Find all unique triplets in array that sum to zero.",
        "constraints": ["3 <= nums.length <= 3000"],
        "code": "def threeSum(nums): pass",
    }
    step_id = ledger.record_step_start(pipeline_run_id=run_id, step_name="plan", input_payload={})
    ledger.record_step_completion(step_execution_id=step_id, output_payload=plan_output)

    received_prompts = []

    def mock_llm_func(prompt: str):
        received_prompts.append(prompt)
        custom_dict = dict(valid_script_dict)
        custom_dict["slug"] = "three-sum"
        custom_dict["topic"] = "Three Sum Problem"
        return custom_dict

    node = ScriptGeneratorNode(llm_provider=mock_llm_func, max_retries=1)
    output = node.execute(run_id=run_id, ledger=ledger)

    assert output["status"] == "completed"
    assert output["slug"] == "three-sum"
    assert output["topic"] == "Three Sum Problem"
    assert len(received_prompts) == 1
    assert "Three Sum Problem" in received_prompts[0]
    assert "three-sum" in received_prompts[0]



def test_slug_validation_invariants():
    """Adversarial Test: Verify slug regex validation in YouTubeScript model."""
    valid_slugs = ["two-sum", "3sum-closest", "valid-slug-123"]
    invalid_slugs = ["Two-Sum", "two sum", "two_sum!", "slug_with_underscores", ""]

    for slug in invalid_slugs:
        with pytest.raises(ValidationError):
            YouTubeScript.model_validate(
                {
                    "topic": "Test Topic",
                    "slug": slug,
                    "difficulty": "Easy",
                    "hook": {"title": "H", "narration": "N", "estimated_duration": 10.0},
                    "context": {"title": "C", "narration": "N", "estimated_duration": 10.0},
                    "solution": {"title": "S", "narration": "N", "estimated_duration": 10.0},
                    "complexity": {
                        "title": "X",
                        "narration": "N",
                        "time_complexity": "O(1)",
                        "space_complexity": "O(1)",
                        "estimated_duration": 10.0,
                    },
                    "total_duration": 40.0,
                }
            )


def test_duration_validation_tolerance(valid_script_dict):
    """Adversarial Test: Verify 0.1s tolerance rule for section duration vs total_duration."""
    # Sum is 15.0 + 30.0 + 45.0 + 10.0 = 100.0
    d_valid = dict(valid_script_dict)
    d_valid["total_duration"] = 100.08  # within 0.1 tolerance
    script = YouTubeScript.model_validate(d_valid)
    assert script.total_duration == 100.08

    d_invalid = dict(valid_script_dict)
    d_invalid["total_duration"] = 100.20  # exceeds 0.1 tolerance
    with pytest.raises(ValidationError):
        YouTubeScript.model_validate(d_invalid)

    # Float precision boundary test case:
    # 55.8 + 38.08 + 15.47 + 13.91 = 123.25999999999999 in IEEE 754 floating-point arithmetic.
    # total_duration = 123.36 (exact diff = 0.10) must validate cleanly without false positive error.
    float_boundary_dict = dict(valid_script_dict)
    float_boundary_dict["hook"] = dict(valid_script_dict["hook"], estimated_duration=55.8)
    float_boundary_dict["context"] = dict(valid_script_dict["context"], estimated_duration=38.08)
    float_boundary_dict["solution"] = dict(valid_script_dict["solution"], estimated_duration=15.47)
    float_boundary_dict["complexity"] = dict(valid_script_dict["complexity"], estimated_duration=13.91)
    float_boundary_dict["total_duration"] = 123.36

    script_float = YouTubeScript.model_validate(float_boundary_dict)
    assert script_float.total_duration == 123.36


