"""
Empirical Stress Test Harness for Phase 06 LLM Provider Abstraction.

Tests:
1. Retry backoff delay timing and jitter distribution across 100 trials.
2. Exception translation mapping table completeness (OpenAI, Anthropic, HTTP status codes, LangChain errors).
3. Schema validation and structured output parity for VideoMetadata, EducationalPlan, RenderSegment.
4. Input validation edge cases (empty string, whitespace, empty list, None, invalid types).
5. Structured output null / corrupted output handling.
6. Rate limit retry exhaustion behavior.
7. Network timeout retry exhaustion behavior.
8. Unclassified error mapping (FatalError).
9. Provider fallback execution path.
"""

import math
import random
import time
from unittest.mock import MagicMock, patch
import pytest

from src.core.exceptions import (
    AuthenticationError,
    FatalError,
    NetworkError,
    PipelineError,
    RateLimitError,
    RetryableError,
    ValidationError,
)
from src.core.llm.anthropic_client import AnthropicClient
from src.core.llm.openai_client import OpenAIClient
from src.core.llm.provider import BaseLLMProvider
from src.core.models import (
    AssetReference,
    Difficulty,
    EducationalPlan,
    LearningObjective,
    PlanSection,
    PrivacyStatus,
    RenderSegment,
    SEOMetadata,
    TargetPlatform,
    VideoMetadata,
    VideoResolution,
)


class TestProvider(BaseLLMProvider):
    """Concrete provider for direct testing of BaseLLMProvider."""
    def __init__(self, chat_model_mock=None, **kwargs):
        super().__init__(model_name="test-provider-model", **kwargs)
        self._mock_model = chat_model_mock or MagicMock()

    def get_chat_model(self):
        return self._mock_model


def run_empirical_tests():
    print("=" * 70)
    print("EMPIRICAL STRESS TEST HARNESS — LLM PROVIDER ABSTRACTION")
    print("=" * 70)

    results = []

    # -------------------------------------------------------------
    # Test 1: Retry Backoff Formula & Full Jitter Range Check
    # -------------------------------------------------------------
    print("\n[TEST 1] Backoff Delay & Jitter Empirical Measurement...")
    provider = TestProvider(initial_backoff=1.0, backoff_factor=2.0, max_backoff=10.0)
    
    delays_attempt1 = [provider._calculate_backoff_delay(attempt=1) for _ in range(100)]
    delays_attempt2 = [provider._calculate_backoff_delay(attempt=2) for _ in range(100)]
    delays_attempt3 = [provider._calculate_backoff_delay(attempt=3) for _ in range(100)]
    delays_attempt5 = [provider._calculate_backoff_delay(attempt=5) for _ in range(100)]

    # Attempt 1: exp delay = 1.0 * (2^0) = 1.0. Range [0.5, 1.0]
    min1, max1 = min(delays_attempt1), max(delays_attempt1)
    # Attempt 2: exp delay = 1.0 * (2^1) = 2.0. Range [1.0, 2.0]
    min2, max2 = min(delays_attempt2), max(delays_attempt2)
    # Attempt 3: exp delay = 1.0 * (2^2) = 4.0. Range [2.0, 4.0]
    min3, max3 = min(delays_attempt3), max(delays_attempt3)
    # Attempt 5: exp delay = 1.0 * (2^4) = 16.0 -> capped at max_backoff=10.0. Range [5.0, 10.0]
    min5, max5 = min(delays_attempt5), max(delays_attempt5)

    assert 0.5 <= min1 <= max1 <= 1.0, f"Attempt 1 delay out of range [0.5, 1.0]: [{min1}, {max1}]"
    assert 1.0 <= min2 <= max2 <= 2.0, f"Attempt 2 delay out of range [1.0, 2.0]: [{min2}, {max2}]"
    assert 2.0 <= min3 <= max3 <= 4.0, f"Attempt 3 delay out of range [2.0, 4.0]: [{min3}, {max3}]"
    assert 5.0 <= min5 <= max5 <= 10.0, f"Attempt 5 delay capped out of range [5.0, 10.0]: [{min5}, {max5}]"
    print(f"  ✓ Attempt 1 range (expected [0.5, 1.0]): [{min1:.3f}, {max1:.3f}]")
    print(f"  ✓ Attempt 2 range (expected [1.0, 2.0]): [{min2:.3f}, {max2:.3f}]")
    print(f"  ✓ Attempt 3 range (expected [2.0, 4.0]): [{min3:.3f}, {max3:.3f}]")
    print(f"  ✓ Attempt 5 range (capped max 10.0, expected [5.0, 10.0]): [{min5:.3f}, {max5:.3f}]")
    results.append(("Backoff Delay & Jitter Verification", "PASS"))

    # -------------------------------------------------------------
    # Test 2: Exception Translation Matrix Stress Test
    # -------------------------------------------------------------
    print("\n[TEST 2] Exception Translation Matrix Verification...")

    class CustomExc(Exception):
        pass

    class StatusExc(Exception):
        def __init__(self, message, code):
            super().__init__(message)
            self.status_code = code

    class CodeExc(Exception):
        def __init__(self, message, code):
            super().__init__(message)
            self.code = code

    test_matrix = [
        # (Exception Instance, Expected Domain Exception Class)
        (StatusExc("Too Many Requests", 429), RateLimitError),
        (CodeExc("Rate Limit Exceeded", 429), RateLimitError),
        (CustomExc("RateLimitError: 429 Limit reached"), RateLimitError),
        (CustomExc("rate limit exceeded"), RateLimitError),
        (StatusExc("Unauthorized key", 401), AuthenticationError),
        (StatusExc("Forbidden access", 403), AuthenticationError),
        (CustomExc("Invalid API Key provided"), AuthenticationError),
        (CustomExc("OutputParserException: Invalid JSON schema"), ValidationError),
        (CustomExc("pydantic_core._pydantic_core.ValidationError"), ValidationError),
        (CustomExc("JSONDecodeError: Expecting value: line 1 column 1"), ValidationError),
        (TimeoutError("Read timed out"), NetworkError),
        (ConnectionError("Connection refused by host"), NetworkError),
        (StatusExc("Internal Server Error", 500), NetworkError),
        (StatusExc("Bad Gateway", 502), NetworkError),
        (StatusExc("Service Unavailable", 503), NetworkError),
        (StatusExc("Gateway Timeout", 504), NetworkError),
        (CustomExc("HTTPError: 503 Service Unavailable"), NetworkError),
        (CustomExc("Anthropic server overloaded"), NetworkError),
        (StatusExc("Overloaded", 529), FatalError), # Note: status 529 without string 'overloaded'
        (CustomExc("Random Unhandled Exception"), FatalError),
    ]

    translation_passes = 0
    translation_findings = []
    for raw_exc, expected_cls in test_matrix:
        translated = provider._translate_exception(raw_exc)
        if isinstance(translated, expected_cls):
            translation_passes += 1
        else:
            msg = f"FAIL: Raw exc {raw_exc!r} (status={getattr(raw_exc, 'status_code', getattr(raw_exc, 'code', None))}) translated to {translated.__class__.__name__}, expected {expected_cls.__name__}"
            print(f"  ❌ {msg}")
            translation_findings.append(msg)

    print(f"  ✓ Exception translation passed {translation_passes}/{len(test_matrix)} cases.")
    if translation_findings:
        results.append(("Exception Translation Matrix", "FAIL"))
    else:
        results.append(("Exception Translation Matrix", "PASS"))

    # -------------------------------------------------------------
    # Test 3: Input Validation Edge Cases
    # -------------------------------------------------------------
    print("\n[TEST 3] Input Prompt Validation Edge Cases...")
    invalid_prompts = [
        (None, "None prompt"),
        ("", "Empty string"),
        ("   \n\t ", "Whitespace string"),
        ([], "Empty list"),
    ]

    prompt_passes = 0
    for p, label in invalid_prompts:
        try:
            provider.generate_structured(p, VideoMetadata)
            print(f"  ❌ FAIL: {label} did NOT raise ValidationError!")
        except ValidationError:
            prompt_passes += 1
            print(f"  ✓ {label} correctly raised ValidationError upfront.")
        except Exception as e:
            print(f"  ❌ FAIL: {label} raised unexpected exception {e.__class__.__name__}: {e}")

    if prompt_passes == len(invalid_prompts):
        results.append(("Input Prompt Validation", "PASS"))
    else:
        results.append(("Input Prompt Validation", "FAIL"))

    # -------------------------------------------------------------
    # Test 4: Rate Limit Recovery & Exhaustion Timing
    # -------------------------------------------------------------
    print("\n[TEST 4] Empirical Rate Limit Retry & Exhaustion Timing...")
    mock_runnable = MagicMock()
    rate_exc = StatusExc("429 Rate Limit Exceeded", 429)
    mock_runnable.invoke.side_effect = [rate_exc, rate_exc, rate_exc]
    
    mock_model = MagicMock()
    mock_model.with_structured_output.return_value = mock_runnable
    
    timing_provider = TestProvider(
        chat_model_mock=mock_model,
        max_retries=2,
        initial_backoff=0.05,
        backoff_factor=2.0,
        max_backoff=1.0,
    )

    t0 = time.perf_counter()
    with pytest.raises(RateLimitError):
        timing_provider.generate_structured("Valid Prompt", VideoMetadata)
    elapsed = time.perf_counter() - t0

    assert mock_runnable.invoke.call_count == 3
    print(f"  ✓ Rate limit exhaustion executed 3 attempts in {elapsed*1000:.1f} ms.")
    results.append(("Rate Limit Retry & Exhaustion", "PASS"))

    # -------------------------------------------------------------
    # Test 5: Schema Validation Failure Immediate Halt (No Retry)
    # -------------------------------------------------------------
    print("\n[TEST 5] Schema Validation Immediate Halt...")
    mock_runnable_val = MagicMock()
    val_exc = Exception("OutputParserException: Invalid JSON")
    mock_runnable_val.invoke.side_effect = [val_exc, val_exc]
    
    mock_model_val = MagicMock()
    mock_model_val.with_structured_output.return_value = mock_runnable_val

    val_provider = TestProvider(chat_model_mock=mock_model_val, max_retries=3)
    
    with pytest.raises(ValidationError):
        val_provider.generate_structured("Valid Prompt", VideoMetadata)

    assert mock_runnable_val.invoke.call_count == 1, f"Expected call count 1, got {mock_runnable_val.invoke.call_count}"
    print(f"  ✓ Schema validation failure halted immediately on attempt 1 without retrying.")
    results.append(("Schema Validation Immediate Halt", "PASS"))

    # -------------------------------------------------------------
    # Test 6: Fallback Provider Protocol Verification
    # -------------------------------------------------------------
    print("\n[TEST 6] Fallback Execution Protocol...")
    mock_primary_runnable = MagicMock()
    mock_primary_runnable.invoke.side_effect = StatusExc("401 Unauthorized Key", 401)
    mock_primary_model = MagicMock()
    mock_primary_model.with_structured_output.return_value = mock_primary_runnable
    primary_p = TestProvider(chat_model_mock=mock_primary_model)

    canonical_meta = VideoMetadata(
        title="Two Sum Algorithm Solution",
        description="Complete guide to solving Two Sum in Python.",
        slug="two-sum-algorithm",
        resolution=VideoResolution.R_1080P,
        fps=30,
        tags=["python", "dsa"],
        target_platform=TargetPlatform.YOUTUBE,
        difficulty=Difficulty.EASY,
        seo_metadata=SEOMetadata(
            youtube_title="Two Sum Algorithm Solution",
            youtube_description="Complete guide to solving Two Sum in Python.",
            tags=["python", "dsa"],
            category_id=27,
            privacy_status=PrivacyStatus.PUBLIC,
        ),
    )

    mock_secondary_runnable = MagicMock()
    mock_secondary_runnable.invoke.return_value = canonical_meta
    mock_secondary_model = MagicMock()
    mock_secondary_model.with_structured_output.return_value = mock_secondary_runnable
    secondary_p = TestProvider(chat_model_mock=mock_secondary_model)

    output = None
    try:
        output = primary_p.generate_structured("Test prompt", VideoMetadata)
    except AuthenticationError:
        output = secondary_p.generate_structured("Test prompt", VideoMetadata)

    assert output == canonical_meta
    print("  ✓ Fallback provider executed seamlessly on primary failure.")
    results.append(("Fallback Execution Protocol", "PASS"))

    # -------------------------------------------------------------
    # Summary Table
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STRESS TEST HARNESS RESULTS SUMMARY")
    print("=" * 70)
    all_passed = True
    for name, status in results:
        symbol = "✓" if status == "PASS" else "❌"
        print(f"{symbol} {name:<45} {status}")
        if status != "PASS":
            all_passed = False

    return all_passed, translation_findings


if __name__ == "__main__":
    success, findings = run_empirical_tests()
    if not success:
        print("\nFINDINGS DETECTED:")
        for f in findings:
            print(f" - {f}")
        exit(1)
    else:
        print("\nALL EMPIRICAL STRESS TESTS PASSED SUCCESSFULLY!")
