# Analysis & Design Report: Mock Test Strategy & Documentation Outline for LLM Provider Abstraction (Phase 06)

**Agent Identity**: `explorer_iter1_3` (Test & Docs Explorer 3)  
**Working Directory**: `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_iter1_3`  
**Date**: 2026-07-26  

---

## 1. Executive Summary

This report establishes the complete design for **Milestone 3 (Unit & Integration Test Suite)** and **Milestone 4 (Documentation)** of Phase 06 (*LLM Provider Abstraction*).

### Key Objectives
1. **Mock Test Strategy**: Design `tests/llm/test_providers.py` to rigorously test `OpenAIClient` and `AnthropicClient` using `unittest.mock` / `pytest-mock` without active API keys or external network calls.
2. **Schema Parity Verification**: Define test cases asserting that both `OpenAIClient` and `AnthropicClient` yield **100% identical Pydantic V2 output objects** (`VideoMetadata`, `EducationalPlan`, `RenderSegment`) when given identical prompt inputs.
3. **Resiliency & Error Mapping Verification**: Outline mock tests for transient rate limits (429), connection timeouts, and invalid LLM structured output, ensuring proper exception translation to `src.core.exceptions` (`RateLimitError`, `NetworkError`, `ValidationError`).
4. **Documentation Outline**: Provide a detailed outline for `PromptBook/Phase06/01_LLM_Abstraction.md` covering architecture, provider implementations, retry mechanisms, exception mapping, and test execution.

---

## 2. Mock Test Strategy for `tests/llm/test_providers.py`

### 2.1 Design Principles & Isolation Guidelines
- **Zero External Network Calls**: Tests must run completely offline without hitting OpenAI or Anthropic API endpoints.
- **Environment Variable Isolation**: Use Pytest `monkeypatch` to set `OPENAI_API_KEY="mock-openai-key"` and `ANTHROPIC_API_KEY="mock-anthropic-key"`, preventing provider initialization errors due to missing environment variables.
- **LangChain Structured Output Interception**: Both `OpenAIClient` and `AnthropicClient` inherit from `BaseLLMProvider` and delegate generation to `get_chat_model().with_structured_output(schema).invoke(prompt)`. Mocking must patch the underlying LangChain model constructor (`langchain_openai.ChatOpenAI` and `langchain_anthropic.ChatAnthropic`) so `with_structured_output` returns a mock `Runnable` whose `.invoke()` returns canonical Pydantic model instances.

### 2.2 Canonical Test Payloads (Fixtures)

Three canonical Pydantic V2 model instances serve as the ground-truth expected outputs for both clients:

```python
import pytest
from src.core.models.video import VideoMetadata, VideoResolution, TargetPlatform, PrivacyStatus, Difficulty, SEOMetadata
from src.core.models.plan import EducationalPlan, PlanSection, CodeSnippet, VisualCue, LearningObjective
from src.core.models.assets import RenderSegment, AssetReference

@pytest.fixture
def canonical_video_metadata() -> VideoMetadata:
    return VideoMetadata(
        title="Two Sum Problem Explained",
        description="Learn how to solve Two Sum in Python with O(n) time complexity.",
        slug="two-sum-explained",
        resolution=VideoResolution.R_1080P,
        width=1920,
        height=1080,
        fps=30,
        tags=["dsa", "leetcode", "twosum", "python"],
        format="mp4",
        target_platform=TargetPlatform.YOUTUBE,
        category_id=27,
        privacy_status=PrivacyStatus.PUBLIC,
        language="en",
        problem_number=1,
        difficulty=Difficulty.EASY,
        seo_metadata=SEOMetadata(
            youtube_title="Two Sum Problem Explained | LeetCode 1 Python",
            youtube_description="Step-by-step solution to Two Sum.",
            tags=["dsa", "leetcode", "python"],
            category_id=27,
            privacy_status=PrivacyStatus.PUBLIC,
        ),
    )

@pytest.fixture
def canonical_educational_plan() -> EducationalPlan:
    return EducationalPlan(
        topic="Two Sum Hash Map Approach",
        slug="two-sum-hash-map",
        target_audience="Beginner",
        difficulty="Easy",
        learning_objectives=[
            LearningObjective(
                objective_id="obj_1",
                description="Understand hash map lookups for complement target.",
                taxonomic_level="Apply"
            )
        ],
        prerequisites=["Python Dictionaries", "Basic Arrays"],
        sections=[
            PlanSection(
                section_id="sec_1",
                section_type="intro",
                title="Problem Statement",
                narration="Welcome! Today we solve Two Sum.",
                estimated_duration=30.0,
                visual_cue_ids=["cue_1"],
                order=1,
            ),
            PlanSection(
                section_id="sec_2",
                section_type="explanation",
                title="Hash Map Technique",
                narration="We store elements as keys and indices as values.",
                estimated_duration=60.0,
                visual_cue_ids=["cue_2"],
                order=2,
            )
        ],
        code_snippets=[
            CodeSnippet(
                snippet_id="snip_1",
                language="python",
                code="def twoSum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        diff = target - num\n        if diff in seen:\n            return [seen[diff], i]\n        seen[num] = i\n    return []",
                explanation="Optimal O(n) hash map solution.",
                line_highlights=[3, 4, 5],
            )
        ],
        visual_cues=[
            VisualCue(
                cue_id="cue_1",
                animation_type="array_visualizer",
                description="Highlight array indices",
                parameters={"highlight_color": "yellow"}
            )
        ],
        estimated_total_duration=90.0,
    )

@pytest.fixture
def canonical_render_segment() -> RenderSegment:
    return RenderSegment(
        segment_id="seg_001",
        segment_type="intro",
        start_time=0.0,
        end_time=15.0,
        duration=15.0,
        asset_references=[
            AssetReference(
                asset_id="asset_intro_audio",
                asset_type="audio",
                file_path="assets/audio/intro.mp3",
                duration=15.0,
            )
        ],
        narration_text="Welcome to the DSA masterclass.",
        volume=1.0,
        scene_type="title_card",
        visual_parameters={"theme": "dark"},
    )
```

---

### 2.3 Comprehensive Pytest Test Suite Inventory

The table below describes all test cases required in `tests/llm/test_providers.py`:

| # | Test Function Name | Targeted Component | Test Description & Assertion Strategy |
|---|-------------------|-------------------|----------------------------------------|
| 1 | `test_openai_client_initialization` | `OpenAIClient` | Asserts `OpenAIClient` instantiates correctly with config settings without making network calls. |
| 2 | `test_anthropic_client_initialization` | `AnthropicClient` | Asserts `AnthropicClient` instantiates correctly with config settings without making network calls. |
| 3 | `test_identical_output_video_metadata` | Both Clients | Mocks `ChatOpenAI` and `ChatAnthropic` structured output. Calls `generate_structured("...", VideoMetadata)` on both clients. Asserts `openai_result == anthropic_result == canonical_video_metadata` and `type(openai_result) == VideoMetadata`. |
| 4 | `test_identical_output_educational_plan` | Both Clients | Calls `generate_structured("...", EducationalPlan)` on both clients. Asserts `openai_result == anthropic_result == canonical_educational_plan` and `type(openai_result) == EducationalPlan`. |
| 5 | `test_identical_output_render_segment` | Both Clients | Calls `generate_structured("...", RenderSegment)` on both clients. Asserts `openai_result == anthropic_result == canonical_render_segment` and `type(openai_result) == RenderSegment`. |
| 6 | `test_provider_rate_limit_retry_and_mapping` | `BaseLLMProvider` / Resiliency | Mocks API rate limit error (HTTP 429) on initial attempts. Asserts retry mechanism executes `max_retries` times, and raises `src.core.exceptions.RateLimitError`. |
| 7 | `test_provider_network_timeout_retry_and_mapping` | `BaseLLMProvider` / Resiliency | Mocks connection timeout error on initial attempts. Asserts retry mechanism attempts retries and converts final failure to `src.core.exceptions.NetworkError`. |
| 8 | `test_provider_schema_validation_failure` | `BaseLLMProvider` / Resiliency | Mocks malformed response or Pydantic `ValidationError`. Asserts provider converts it into `src.core.exceptions.ValidationError`. |
| 9 | `test_provider_fallback_execution` | Provider Orchestration | Verifies that if `OpenAIClient` encounters a non-retryable error, the system can seamlessly fall back to `AnthropicClient` to produce identical structured output. |

---

### 2.4 Mocking Implementation Pattern for Pytest

```python
from unittest.mock import MagicMock, patch
import pytest

from src.core.llm.openai_client import OpenAIClient
from src.core.llm.anthropic_client import AnthropicClient
from src.core.exceptions import RateLimitError, NetworkError, ValidationError

@pytest.mark.parametrize("client_cls, patch_target", [
    (OpenAIClient, "src.core.llm.openai_client.ChatOpenAI"),
    (AnthropicClient, "src.core.llm.anthropic_client.ChatAnthropic"),
])
def test_providers_return_identical_video_metadata(
    monkeypatch, client_cls, patch_target, canonical_video_metadata
):
    # Set dummy API keys
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "mock-anthropic-key")

    with patch(patch_target) as mock_chat_cls:
        # Set up mock ChatModel instance and structured output runnable
        mock_chat_instance = MagicMock()
        mock_structured_runnable = MagicMock()
        mock_structured_runnable.invoke.return_value = canonical_video_metadata
        mock_chat_instance.with_structured_output.return_value = mock_structured_runnable
        mock_chat_cls.return_value = mock_chat_instance

        client = client_cls(model_name="test-model")
        result = client.generate_structured("Generate metadata", VideoMetadata)

        # Assertions
        assert result == canonical_video_metadata
        assert isinstance(result, VideoMetadata)
        mock_chat_instance.with_structured_output.assert_called_once_with(VideoMetadata)
        mock_structured_runnable.invoke.assert_called_once()
```

---

## 3. Documentation Outline for `PromptBook/Phase06/01_LLM_Abstraction.md`

The file `PromptBook/Phase06/01_LLM_Abstraction.md` must provide a comprehensive, developer-facing guide for the LLM abstraction layer. Below is the detailed structural outline:

```markdown
# Phase 06: LLM Provider Abstraction Architecture

## 1. Executive Summary & Architecture Overview
- High-level purpose: Unified interface wrapping external LLM providers (OpenAI, Anthropic) via LangChain.
- Core design goals:
  - Provider interchangeability (OpenAI GPT-4o / Anthropic Claude 3.5 Sonnet).
  - Guaranteed structured output enforcing Phase 05 Pydantic V2 models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`).
  - Built-in resiliency: Exponential backoff retries and exception mapping to `src.core.exceptions`.

## 2. Class Hierarchy & Interface Contracts
- `BaseLLMProvider(abc.ABC)` (`src/core/llm/provider.py`)
  - Abstract methods: `get_chat_model()`
  - Public interface: `generate_structured(prompt, response_model: Type[T]) -> T`
- Concrete Clients:
  - `OpenAIClient` (`src/core/llm/openai_client.py` wrapping `langchain_openai.ChatOpenAI`)
  - `AnthropicClient` (`src/core/llm/anthropic_client.py` wrapping `langchain_anthropic.ChatAnthropic`)

## 3. Resiliency, Retries & Exception Mapping
- Retry Strategy: `tenacity` exponential backoff configuration (`max_retries=3`, `min_wait=1s`, `max_wait=10s`).
- Exception Mapping Matrix:
  - Provider Rate Limits (HTTP 429) -> `src.core.exceptions.RateLimitError`
  - Connection Timeouts / Network Issues -> `src.core.exceptions.NetworkError`
  - Schema / Parsing Violations -> `src.core.exceptions.ValidationError`
  - Authentication Errors -> `src.core.exceptions.AuthenticationError`

## 4. Structured Output Integration with Pydantic V2 Models
- Deep integration with `with_structured_output(response_model)`.
- Support for complex nested models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`).
- Invariant validation preservation (ensuring model validation post-generation).

## 5. Mocking & Testing Strategy
- Unit testing with `pytest-mock` and `unittest.mock`.
- Asserting identical schema outputs across providers without external network access.
- Running test suite: `pytest tests/llm/test_providers.py`.
```

---

## 4. Summary of Deliverables & Handoff Readiness

1. **Test Strategy**: Fully designed for offline pytest execution with strict assertion of Pydantic V2 model parity between OpenAI and Anthropic clients.
2. **Documentation Outline**: Comprehensive layout ready to be authored as `PromptBook/Phase06/01_LLM_Abstraction.md`.
3. **Implementer Guidance**: Concrete code snippets and fixture designs provided for immediate implementation in `implementer_iter1_3`.
