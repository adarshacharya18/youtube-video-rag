# Project: Automated DSA Educational YouTube Video Pipeline — Phase 06: LLM Provider Abstraction

## Architecture
- **Module boundaries**: `src/core/llm/` provides a unified provider interface (`provider.py`) and concrete implementations for OpenAI (`openai_client.py`) and Anthropic (`anthropic_client.py`).
- **Integration**: Wraps LangChain's `BaseChatModel` and `.with_structured_output()` to guarantee structured Pydantic model outputs from `src/core/models/` (`VideoMetadata`, `EducationalPlan`, `RenderSegment`, etc.).
- **Resiliency**: Built-in retry and backoff logic for handling API failures, rate limits, and network errors, mapping external SDK exceptions into structured pipeline exceptions in `src/core/exceptions.py`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Dependencies & Core Config | Add `langchain`, `langchain-openai`, `langchain-anthropic`, `openai`, `anthropic` to project dependencies and update `src/core/config.py` with LLM settings | M1 | survey |
| 2 | Unified LLM Provider Interface | Implement `src/core/llm/provider.py` with `BaseLLMProvider` abstract base class, retry/backoff mechanism, and exception translation | M2 | R1, R2 |
| 3 | OpenAI Client Implementation | Implement `src/core/llm/openai_client.py` wrapping `ChatOpenAI` and `with_structured_output` | M2 | R1 |
| 4 | Anthropic Client Implementation | Implement `src/core/llm/anthropic_client.py` wrapping `ChatAnthropic` and `with_structured_output` | M2 | R1 |
| 5 | Pytest Provider Test Suite | Implement `tests/llm/test_providers.py` with mocked API responses for OpenAI and Anthropic asserting identical Pydantic outputs | M3 | R4 |
| 6 | Phase 06 Documentation | Create `PromptBook/Phase06/01_LLM_Abstraction.md` documenting strategy, retry logic, and fallback mechanisms | M4 | R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Dependencies & Config | `pyproject.toml`, `requirements.txt`, `src/core/config.py` | none | DONE |
| 2 | LLM Provider Abstraction & Clients | `src/core/llm/provider.py`, `src/core/llm/openai_client.py`, `src/core/llm/anthropic_client.py`, `src/core/llm/__init__.py` | M1 | DONE |
| 3 | Unit & Integration Test Suite | `tests/llm/test_providers.py`, `tests/llm/__init__.py` | M2 | DONE |
| 4 | Documentation | `PromptBook/Phase06/01_LLM_Abstraction.md` | M2 | DONE |

## Interface Contracts
### `src/core/llm/provider.py`
- `BaseLLMProvider(abc.ABC)`:
  - `__init__(model_name: str, api_key: Optional[str] = None, temperature: float = 0.0, max_retries: int = 3, timeout: float = 60.0)`
  - `@abstractmethod get_chat_model() -> BaseChatModel`
  - `generate_structured(prompt: Union[str, List[Any]], response_model: Type[T]) -> T`:
    - Wraps `get_chat_model().with_structured_output(response_model)`
    - Applies exponential backoff retry on retryable errors (e.g. rate limits, 5xx server errors, connection timeouts).
    - Maps API rate limit errors (429) -> `RateLimitError`, network issues -> `NetworkError`, validation failures -> `ValidationError`.

### `src/core/llm/openai_client.py`
- `OpenAIClient(BaseLLMProvider)`:
  - Instantiates `langchain_openai.ChatOpenAI`.

### `src/core/llm/anthropic_client.py`
- `AnthropicClient(BaseLLMProvider)`:
  - Instantiates `langchain_anthropic.ChatAnthropic`.

## Code Layout
- `src/core/llm/__init__.py`
- `src/core/llm/provider.py`
- `src/core/llm/openai_client.py`
- `src/core/llm/anthropic_client.py`
- `tests/llm/__init__.py`
- `tests/llm/test_providers.py`
- `PromptBook/Phase06/01_LLM_Abstraction.md`
