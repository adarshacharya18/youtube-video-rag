"""
Empirical Stress Test Harness - Iteration 2
Adversarial test harness to empirically verify LLM Provider Abstraction defect resolution.
"""

import sys
import time
import random
from typing import Any
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from src.core.exceptions import (
    AuthenticationError,
    FatalError,
    NetworkError,
    PipelineError,
    RateLimitError,
    RetryableError,
    ValidationError,
)
from src.core.llm.provider import BaseLLMProvider


class MockModel(BaseModel):
    name: str = Field(default="test_mock")


class MockLLMProvider(BaseLLMProvider):
    def __init__(self, mock_runnable=None, **kwargs):
        super().__init__(model_name="mock-model", **kwargs)
        self.mock_runnable = mock_runnable or MagicMock()

    def get_chat_model(self):
        mock_chat = MagicMock()
        mock_chat.with_structured_output.return_value = self.mock_runnable
        return mock_chat


def test_defect1_prompt_validation():
    print("\n" + "=" * 70)
    print("EMPIRICAL TEST 1: PROMPT VALIDATION DEFECT RESOLUTION")
    print("=" * 70)

    provider = MockLLMProvider()

    # Invalid prompts that MUST raise ValidationError
    invalid_prompts = [
        (None, "None prompt"),
        ("", "Empty string ''"),
        ("   \t\n ", "Whitespace string"),
        ([], "Empty list []"),
        ([""], "List with empty string"),
        (["   "], "List with whitespace string"),
        ([HumanMessage(content="")], "List with empty HumanMessage"),
        ([HumanMessage(content="   ")], "List with whitespace HumanMessage"),
        ([{"role": "user", "content": "  "}], "List with whitespace dict content"),
        ([{"role": "user", "content": ""}], "List with empty dict content"),
        ([{"role": "user"}], "List with missing content key"),
        (12345, "Integer prompt"),
        (3.14159, "Float prompt"),
        (True, "Boolean prompt"),
        ({"key": "val"}, "Dict prompt"),
        ((1, 2, 3), "Tuple prompt"),
        ({1, 2, 3}, "Set prompt"),
        ([None], "List containing None"),
    ]

    passed_count = 0
    failed = []

    for prompt_val, desc in invalid_prompts:
        try:
            provider.generate_structured(prompt_val, MockModel)
            print(f"  ❌ FAIL: {desc} did NOT raise ValidationError!")
            failed.append(desc)
        except ValidationError as e:
            print(f"  ✓ PASS: {desc} -> Raised ValidationError upfront ({e})")
            passed_count += 1
        except Exception as e:
            print(f"  ❌ FAIL: {desc} raised wrong exception ({type(e).__name__}: {e})")
            failed.append(f"{desc} ({type(e).__name__})")

    # Check dict with content=None or object with content=None
    try:
        provider.generate_structured([{"role": "user", "content": None}], MockModel)
        print("  ⚠️ WARNING: Dict with content=None passed validation without ValidationError!")
        failed.append("Dict with content=None")
    except ValidationError as e:
        print(f"  ✓ PASS: Dict with content=None -> Raised ValidationError ({e})")
        passed_count += 1
    except Exception as e:
        print(f"  ❌ FAIL: Dict with content=None raised wrong exception ({type(e).__name__}: {e})")
        failed.append(f"Dict with content=None ({type(e).__name__})")

    print(f"\nPrompt Validation Results: {passed_count}/{len(invalid_prompts)+1} passed.")
    return len(failed) == 0, failed


def test_defect2_exception_translation():
    print("\n" + "=" * 70)
    print("EMPIRICAL TEST 2: EXCEPTION TRANSLATION & HTTP 529 DEFECT RESOLUTION")
    print("=" * 70)

    class CustomSDKError(Exception):
        def __init__(self, message, status_code=None, code=None):
            super().__init__(message)
            if status_code is not None:
                self.status_code = status_code
            if code is not None:
                self.code = code

    class RateLimitErrorSDK(Exception):
        pass

    class AuthenticationErrorSDK(Exception):
        pass

    class OverloadedErrorSDK(Exception):
        pass

    provider = MockLLMProvider()

    matrix = [
        # Rate Limit Cases
        (CustomSDKError("RateLimitError: 30000 TPM limit exceeded"), RateLimitError, "Wrapped RateLimitError in str"),
        (RateLimitErrorSDK("429 Too Many Requests"), RateLimitError, "RateLimitError class name"),
        (CustomSDKError("Error code: 429", status_code=429), RateLimitError, "status_code 429"),
        (CustomSDKError("quota exceeded for current month"), RateLimitError, "quota exceeded in str"),

        # Auth Cases
        (CustomSDKError("AuthenticationError: invalid key provided"), AuthenticationError, "Wrapped AuthenticationError in str"),
        (AuthenticationErrorSDK("401 Unauthorized"), AuthenticationError, "AuthenticationError class name"),
        (CustomSDKError("Error code: 401", status_code=401), AuthenticationError, "status_code 401"),
        (CustomSDKError("Error code: 403", status_code=403), AuthenticationError, "status_code 403"),
        (CustomSDKError("api key invalid or missing"), AuthenticationError, "api key in str"),

        # Validation Cases
        (CustomSDKError("ValidationError: 1 validation error for VideoMetadata"), ValidationError, "Wrapped ValidationError in str"),
        (CustomSDKError("OutputParserException: Invalid JSON response"), ValidationError, "OutputParserException in str"),
        (CustomSDKError("json decoding failed"), ValidationError, "json decoding in str"),

        # Network & 5xx / 529 Cases
        (CustomSDKError("Error code: 529 - Anthropic Overloaded", status_code=529), NetworkError, "Anthropic HTTP status 529"),
        (OverloadedErrorSDK("Anthropic server overloaded"), NetworkError, "OverloadedErrorSDK class name"),
        (CustomSDKError("ConnectionResetError: Connection lost"), NetworkError, "ConnectionResetError in str"),
        (TimeoutError("Read timeout after 60s"), NetworkError, "TimeoutError standard python"),
        (ConnectionError("Failed to establish connection"), NetworkError, "ConnectionError standard python"),
        (CustomSDKError("Error code: 500 Internal Server Error", status_code=500), NetworkError, "status_code 500"),
        (CustomSDKError("Error code: 502 Bad Gateway", status_code=502), NetworkError, "status_code 502"),
        (CustomSDKError("Error code: 503 Service Unavailable", status_code=503), NetworkError, "status_code 503"),
        (CustomSDKError("Error code: 504 Gateway Timeout", status_code=504), NetworkError, "status_code 504"),
    ]

    passed_count = 0
    failed = []

    for raw_exc, expected_domain_exc, desc in matrix:
        translated = provider._translate_exception(raw_exc)
        if isinstance(translated, expected_domain_exc):
            print(f"  ✓ PASS: {desc:<45} -> Translated to {translated.__class__.__name__}")
            passed_count += 1
        else:
            print(f"  ❌ FAIL: {desc:<45} -> Got {translated.__class__.__name__}, Expected {expected_domain_exc.__name__}")
            failed.append(desc)

    print(f"\nException Translation Results: {passed_count}/{len(matrix)} passed.")
    return len(failed) == 0, failed


def test_defect3_dead_code_and_retry_loop():
    print("\n" + "=" * 70)
    print("EMPIRICAL TEST 3: RETRY LOOP EXECUTION & UNREACHABLE CODE VERIFICATION")
    print("=" * 70)

    # Verify retry loop behavior when max_retries reached
    mock_runnable = MagicMock()
    mock_runnable.invoke.side_effect = TimeoutError("Connection timed out")

    provider = MockLLMProvider(mock_runnable=mock_runnable, max_retries=2, initial_backoff=0.001)

    attempt_count = 0
    try:
        provider.generate_structured("Test prompt", MockModel)
    except NetworkError as e:
        print(f"  ✓ PASS: Raised NetworkError on retry exhaustion: {e}")
        attempt_count = mock_runnable.invoke.call_count

    if attempt_count == 3:
        print(f"  ✓ PASS: Invoked exactly 3 times (1 initial + 2 retries).")
        return True, []
    else:
        print(f"  ❌ FAIL: Expected 3 attempts, got {attempt_count}.")
        return False, ["Retry count mismatch"]


def run_all():
    print("RUNNING CHALLENGER ITERATION 2 EMPIRICAL TEST SUITE")
    p1_pass, p1_failed = test_defect1_prompt_validation()
    p2_pass, p2_failed = test_defect2_exception_translation()
    p3_pass, p3_failed = test_defect3_dead_code_and_retry_loop()

    print("\n" + "=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)
    print(f"  Prompt Validation:      {'PASS' if p1_pass else 'FAIL'}")
    print(f"  Exception Translation:  {'PASS' if p2_pass else 'FAIL'}")
    print(f"  Retry Loop Execution:   {'PASS' if p3_pass else 'FAIL'}")

    all_failed = p1_failed + p2_failed + p3_failed
    if all_failed:
        print(f"\n  FAILED ITEMS: {all_failed}")
    else:
        print("\n  🎉 ALL EMPIRICAL TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    run_all()
