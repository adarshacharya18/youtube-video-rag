"""
Unit and integration tests for LLM provider abstraction layer.

Tests OpenAIClient and AnthropicClient using mocked API responses, asserting identical
Pydantic V2 object outputs, error handling, exponential backoff retries, and fallback logic.
"""

from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import HumanMessage

from src.core.exceptions import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from src.core.llm.anthropic_client import AnthropicClient
from src.core.llm.openai_client import OpenAIClient
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


@pytest.fixture
def monkeypatch_api_keys(monkeypatch):
    """Set dummy API keys in environment to prevent initialization errors."""
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "mock-anthropic-key")


@pytest.fixture
def canonical_video_metadata() -> VideoMetadata:
    """Ground-truth VideoMetadata model instance."""
    return VideoMetadata(
        title="Two Sum Algorithm Solution",
        description="Complete guide to solving Two Sum in Python.",
        slug="two-sum-algorithm",
        resolution=VideoResolution.R_1080P,
        fps=30,
        tags=["python", "dsa", "leetcode"],
        target_platform=TargetPlatform.YOUTUBE,
        difficulty=Difficulty.EASY,
        seo_metadata=SEOMetadata(
            youtube_title="Two Sum Algorithm Solution",
            youtube_description="Complete guide to solving Two Sum in Python.",
            tags=["python", "dsa", "leetcode"],
            category_id=27,
            privacy_status=PrivacyStatus.PUBLIC,
        ),
    )


@pytest.fixture
def canonical_educational_plan() -> EducationalPlan:
    """Ground-truth EducationalPlan model instance."""
    sec1 = PlanSection(
        section_id="sec-1",
        section_type="intro",
        title="Introduction to Two Sum",
        narration="Welcome to this video on Two Sum.",
        estimated_duration=15.0,
        order=1,
    )
    obj1 = LearningObjective(
        objective_id="obj-1",
        description="Understand Hash Map Approach",
        taxonomic_level="Apply",
    )
    return EducationalPlan(
        topic="Two Sum",
        slug="two-sum-algorithm",
        learning_objectives=[obj1],
        sections=[sec1],
        estimated_total_duration=15.0,
    )


@pytest.fixture
def canonical_render_segment() -> RenderSegment:
    """Ground-truth RenderSegment model instance."""
    ref1 = AssetReference(
        asset_id="asset-1",
        asset_type="audio",
        file_path="/assets/intro_narration.mp3",
        duration=15.0,
    )
    return RenderSegment(
        segment_id="seg-1",
        segment_type="intro",
        start_time=0.0,
        end_time=15.0,
        duration=15.0,
        asset_references=[ref1],
    )


def test_openai_client_initialization(monkeypatch_api_keys):
    """Test OpenAIClient instantiation and parameter resolution."""
    client = OpenAIClient(
        model_name="gpt-4o-test",
        api_key="test-key",
        temperature=0.5,
        max_retries=2,
        timeout=30.0,
    )
    assert client.model_name == "gpt-4o-test"
    assert client.api_key == "test-key"
    assert client.temperature == 0.5
    assert client.max_retries == 2
    assert client.timeout == 30.0

    chat_model = client.get_chat_model()
    assert chat_model.model_name == "gpt-4o-test"


def test_anthropic_client_initialization(monkeypatch_api_keys):
    """Test AnthropicClient instantiation and parameter resolution."""
    client = AnthropicClient(
        model_name="claude-3-5-sonnet-test",
        api_key="test-key",
        temperature=0.2,
        max_retries=4,
        timeout=45.0,
    )
    assert client.model_name == "claude-3-5-sonnet-test"
    assert client.api_key == "test-key"
    assert client.temperature == 0.2
    assert client.max_retries == 4
    assert client.timeout == 45.0

    chat_model = client.get_chat_model()
    assert chat_model.model == "claude-3-5-sonnet-test"


@pytest.mark.parametrize(
    "client_cls, patch_target",
    [
        (OpenAIClient, "src.core.llm.openai_client.ChatOpenAI"),
        (AnthropicClient, "src.core.llm.anthropic_client.ChatAnthropic"),
    ],
)
def test_providers_return_identical_video_metadata(
    monkeypatch_api_keys, client_cls, patch_target, canonical_video_metadata
):
    """Verify both OpenAI and Anthropic clients return identical VideoMetadata Pydantic objects."""
    with patch(patch_target) as mock_chat_cls:
        mock_chat_instance = MagicMock()
        mock_runnable = MagicMock()
        mock_runnable.invoke.return_value = canonical_video_metadata
        mock_chat_instance.with_structured_output.return_value = mock_runnable
        mock_chat_cls.return_value = mock_chat_instance

        client = client_cls(model_name="test-model")
        result = client.generate_structured("Generate metadata for Two Sum", VideoMetadata)

        assert result == canonical_video_metadata
        assert isinstance(result, VideoMetadata)
        mock_chat_instance.with_structured_output.assert_called_once_with(VideoMetadata)
        mock_runnable.invoke.assert_called_once_with("Generate metadata for Two Sum")


def test_openai_and_anthropic_identical_outputs_video_metadata(
    monkeypatch_api_keys, canonical_video_metadata
):
    """Direct comparative test asserting OpenAI and Anthropic clients return identical VideoMetadata."""
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_openai_cls, patch(
        "src.core.llm.anthropic_client.ChatAnthropic"
    ) as mock_anthropic_cls:
        mock_openai_inst = MagicMock()
        mock_openai_runnable = MagicMock()
        mock_openai_runnable.invoke.return_value = canonical_video_metadata
        mock_openai_inst.with_structured_output.return_value = mock_openai_runnable
        mock_openai_cls.return_value = mock_openai_inst

        mock_anthropic_inst = MagicMock()
        mock_anthropic_runnable = MagicMock()
        mock_anthropic_runnable.invoke.return_value = canonical_video_metadata
        mock_anthropic_inst.with_structured_output.return_value = mock_anthropic_runnable
        mock_anthropic_cls.return_value = mock_anthropic_inst

        openai_client = OpenAIClient()
        anthropic_client = AnthropicClient()

        prompt = "Generate video metadata"
        res_openai = openai_client.generate_structured(prompt, VideoMetadata)
        res_anthropic = anthropic_client.generate_structured(prompt, VideoMetadata)

        assert res_openai == res_anthropic
        assert res_openai == canonical_video_metadata


def test_openai_and_anthropic_identical_outputs_educational_plan(
    monkeypatch_api_keys, canonical_educational_plan
):
    """Direct comparative test asserting OpenAI and Anthropic clients return identical EducationalPlan."""
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_openai_cls, patch(
        "src.core.llm.anthropic_client.ChatAnthropic"
    ) as mock_anthropic_cls:
        mock_openai_inst = MagicMock()
        mock_openai_runnable = MagicMock()
        mock_openai_runnable.invoke.return_value = canonical_educational_plan
        mock_openai_inst.with_structured_output.return_value = mock_openai_runnable
        mock_openai_cls.return_value = mock_openai_inst

        mock_anthropic_inst = MagicMock()
        mock_anthropic_runnable = MagicMock()
        mock_anthropic_runnable.invoke.return_value = canonical_educational_plan
        mock_anthropic_inst.with_structured_output.return_value = mock_anthropic_runnable
        mock_anthropic_cls.return_value = mock_anthropic_inst

        openai_client = OpenAIClient()
        anthropic_client = AnthropicClient()

        prompt = "Generate educational plan"
        res_openai = openai_client.generate_structured(prompt, EducationalPlan)
        res_anthropic = anthropic_client.generate_structured(prompt, EducationalPlan)

        assert res_openai == res_anthropic
        assert res_openai == canonical_educational_plan
        assert isinstance(res_openai, EducationalPlan)


def test_openai_and_anthropic_identical_outputs_render_segment(
    monkeypatch_api_keys, canonical_render_segment
):
    """Direct comparative test asserting OpenAI and Anthropic clients return identical RenderSegment."""
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_openai_cls, patch(
        "src.core.llm.anthropic_client.ChatAnthropic"
    ) as mock_anthropic_cls:
        mock_openai_inst = MagicMock()
        mock_openai_runnable = MagicMock()
        mock_openai_runnable.invoke.return_value = canonical_render_segment
        mock_openai_inst.with_structured_output.return_value = mock_openai_runnable
        mock_openai_cls.return_value = mock_openai_inst

        mock_anthropic_inst = MagicMock()
        mock_anthropic_runnable = MagicMock()
        mock_anthropic_runnable.invoke.return_value = canonical_render_segment
        mock_anthropic_inst.with_structured_output.return_value = mock_anthropic_runnable
        mock_anthropic_cls.return_value = mock_anthropic_inst

        openai_client = OpenAIClient()
        anthropic_client = AnthropicClient()

        prompt = "Generate render segment"
        res_openai = openai_client.generate_structured(prompt, RenderSegment)
        res_anthropic = anthropic_client.generate_structured(prompt, RenderSegment)

        assert res_openai == res_anthropic
        assert res_openai == canonical_render_segment
        assert isinstance(res_openai, RenderSegment)


def test_provider_rate_limit_retry_and_recovery(monkeypatch_api_keys, canonical_video_metadata):
    """Test retry mechanism recovers after transient rate limit (429) errors."""
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_openai_cls, patch(
        "time.sleep"
    ) as mock_sleep:
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        # Fail twice with RateLimitError, succeed on 3rd attempt
        rate_limit_exc = Exception("429 Too Many Requests: Rate limit exceeded")
        rate_limit_exc.status_code = 429
        mock_runnable.invoke.side_effect = [
            rate_limit_exc,
            rate_limit_exc,
            canonical_video_metadata,
        ]
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_openai_cls.return_value = mock_inst

        client = OpenAIClient(max_retries=3, initial_backoff=0.01)
        result = client.generate_structured("Prompt", VideoMetadata)

        assert result == canonical_video_metadata
        assert mock_runnable.invoke.call_count == 3
        assert mock_sleep.call_count == 2


def test_provider_rate_limit_exhaustion(monkeypatch_api_keys):
    """Test retry exhaustion raises RateLimitError when retries are exceeded."""
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_openai_cls, patch("time.sleep"):
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        rate_limit_exc = Exception("429 Too Many Requests: Rate limit exceeded")
        rate_limit_exc.status_code = 429
        mock_runnable.invoke.side_effect = rate_limit_exc
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_openai_cls.return_value = mock_inst

        client = OpenAIClient(max_retries=2, initial_backoff=0.01)

        with pytest.raises(RateLimitError) as exc_info:
            client.generate_structured("Prompt", VideoMetadata)

        assert "Rate limit" in str(exc_info.value)
        # Attempt 1 + 2 retries = 3 attempts total
        assert mock_runnable.invoke.call_count == 3


def test_provider_network_timeout_retry_and_exhaustion(monkeypatch_api_keys):
    """Test network/connection errors retry and map to NetworkError on exhaustion."""
    with patch("src.core.llm.anthropic_client.ChatAnthropic") as mock_anthropic_cls, patch(
        "time.sleep"
    ):
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        timeout_exc = TimeoutError("Connection timed out after 60s")
        mock_runnable.invoke.side_effect = timeout_exc
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_anthropic_cls.return_value = mock_inst

        client = AnthropicClient(max_retries=2, initial_backoff=0.01)

        with pytest.raises(NetworkError) as exc_info:
            client.generate_structured("Prompt", VideoMetadata)

        assert "network issue" in str(exc_info.value).lower() or "connection" in str(exc_info.value).lower()
        assert mock_runnable.invoke.call_count == 3


def test_provider_schema_validation_failure_immediate_raise(monkeypatch_api_keys):
    """Test output parser / schema validation failure raises ValidationError immediately without retry."""
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_openai_cls:
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        val_exc = Exception("OutputParserException: Invalid JSON output structure")
        mock_runnable.invoke.side_effect = val_exc
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_openai_cls.return_value = mock_inst

        client = OpenAIClient(max_retries=3)

        with pytest.raises(ValidationError) as exc_info:
            client.generate_structured("Prompt", VideoMetadata)

        assert "validation failed" in str(exc_info.value).lower()
        # Must fail immediately on attempt 1
        assert mock_runnable.invoke.call_count == 1


def test_provider_authentication_error_immediate_raise(monkeypatch_api_keys):
    """Test HTTP 401/403 authentication error raises AuthenticationError immediately without retry."""
    with patch("src.core.llm.anthropic_client.ChatAnthropic") as mock_anthropic_cls:
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        auth_exc = Exception("401 Unauthorized: Invalid API Key")
        auth_exc.status_code = 401
        mock_runnable.invoke.side_effect = auth_exc
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_anthropic_cls.return_value = mock_inst

        client = AnthropicClient(max_retries=3)

        with pytest.raises(AuthenticationError) as exc_info:
            client.generate_structured("Prompt", VideoMetadata)

        assert "authentication failed" in str(exc_info.value).lower()
        assert mock_runnable.invoke.call_count == 1


def test_provider_null_output_raises_validation_error(monkeypatch_api_keys):
    """Test returning None from LLM raises ValidationError."""
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_openai_cls:
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        mock_runnable.invoke.return_value = None
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_openai_cls.return_value = mock_inst

        client = OpenAIClient(max_retries=1)

        with pytest.raises(ValidationError) as exc_info:
            client.generate_structured("Prompt", VideoMetadata)

        assert "null or empty" in str(exc_info.value).lower()


def test_provider_empty_prompt_raises_validation_error(monkeypatch_api_keys):
    """Test passing empty prompt raises ValidationError upfront without API call."""
    client = OpenAIClient()
    with pytest.raises(ValidationError) as exc_info:
        client.generate_structured("", VideoMetadata)

    assert "cannot be empty" in str(exc_info.value).lower()


def test_provider_fallback_execution(monkeypatch_api_keys, canonical_video_metadata):
    """Test provider fallback pattern when primary provider encounters unrecoverable failure."""
    primary_client = OpenAIClient()
    secondary_client = AnthropicClient()

    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_openai_cls, patch(
        "src.core.llm.anthropic_client.ChatAnthropic"
    ) as mock_anthropic_cls:

        # Primary OpenAI client fails with AuthenticationError
        mock_openai_inst = MagicMock()
        mock_openai_runnable = MagicMock()
        auth_exc = Exception("401 Unauthorized: Invalid Key")
        auth_exc.status_code = 401
        mock_openai_runnable.invoke.side_effect = auth_exc
        mock_openai_inst.with_structured_output.return_value = mock_openai_runnable
        mock_openai_cls.return_value = mock_openai_inst

        # Secondary Anthropic client succeeds
        mock_anthropic_inst = MagicMock()
        mock_anthropic_runnable = MagicMock()
        mock_anthropic_runnable.invoke.return_value = canonical_video_metadata
        mock_anthropic_inst.with_structured_output.return_value = mock_anthropic_runnable
        mock_anthropic_cls.return_value = mock_anthropic_inst

        prompt = "Generate video metadata"
        result = None

        try:
            result = primary_client.generate_structured(prompt, VideoMetadata)
        except AuthenticationError:
            # Fallback to secondary provider
            result = secondary_client.generate_structured(prompt, VideoMetadata)

        assert result == canonical_video_metadata
        assert isinstance(result, VideoMetadata)


@pytest.mark.parametrize(
    "invalid_prompt",
    [
        [],
        12345,
        {"key": "val"},
        [""],
        ["   "],
        [HumanMessage(content="")],
        [HumanMessage(content="   ")],
        [{"role": "user", "content": "  "}],
    ],
)
def test_provider_boundary_prompt_validation_failures(monkeypatch_api_keys, invalid_prompt):
    """Test boundary prompt inputs (empty list, int, dict, empty message content) raise ValidationError upfront."""
    client = OpenAIClient()
    with pytest.raises(ValidationError) as exc_info:
        client.generate_structured(invalid_prompt, VideoMetadata)

    assert "prompt" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()


def test_provider_exception_translation_wrapped_sdk_errors(monkeypatch_api_keys):
    """Test translation of generic wrapped SDK exceptions into domain exception types."""
    class CustomSDKError(Exception):
        pass

    # 1. Wrapped Rate Limit Error
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_cls, patch("time.sleep"):
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        mock_runnable.invoke.side_effect = CustomSDKError("RateLimitError: 30000 TPM limit exceeded")
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_cls.return_value = mock_inst

        client = OpenAIClient(max_retries=1, initial_backoff=0.01)
        with pytest.raises(RateLimitError):
            client.generate_structured("Valid prompt", VideoMetadata)

    # 2. Wrapped Authentication Error
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_cls:
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        mock_runnable.invoke.side_effect = CustomSDKError("AuthenticationError: invalid key provided")
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_cls.return_value = mock_inst

        client = OpenAIClient(max_retries=1, initial_backoff=0.01)
        with pytest.raises(AuthenticationError):
            client.generate_structured("Valid prompt", VideoMetadata)

    # 3. Wrapped Validation Error
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_cls:
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        mock_runnable.invoke.side_effect = CustomSDKError("ValidationError: 1 validation error for VideoMetadata")
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_cls.return_value = mock_inst

        client = OpenAIClient(max_retries=1, initial_backoff=0.01)
        with pytest.raises(ValidationError):
            client.generate_structured("Valid prompt", VideoMetadata)

    # 4. Anthropic HTTP 529 Overloaded Error
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_cls, patch("time.sleep"):
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        err_529 = CustomSDKError("Error code: 529 - Anthropic Overloaded")
        err_529.status_code = 529
        mock_runnable.invoke.side_effect = err_529
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_cls.return_value = mock_inst

        client = OpenAIClient(max_retries=1, initial_backoff=0.01)
        with pytest.raises(NetworkError):
            client.generate_structured("Valid prompt", VideoMetadata)

    # 5. Connection Reset Error String
    with patch("src.core.llm.openai_client.ChatOpenAI") as mock_cls, patch("time.sleep"):
        mock_inst = MagicMock()
        mock_runnable = MagicMock()
        mock_runnable.invoke.side_effect = CustomSDKError("ConnectionResetError: Connection lost")
        mock_inst.with_structured_output.return_value = mock_runnable
        mock_cls.return_value = mock_inst

        client = OpenAIClient(max_retries=1, initial_backoff=0.01)
        with pytest.raises(NetworkError):
            client.generate_structured("Valid prompt", VideoMetadata)
