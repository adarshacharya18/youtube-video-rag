# Handoff Report: Core LLM Provider Design (`src/core/llm/provider.py`)

**Agent**: Design Explorer 1 (`explorer_iter1_1`)  
**Role**: Design Explorer 1  
**Working Directory**: `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_iter1_1`  
**Handoff Type**: Hard (Task Complete)  

---

## 1. Observation

Direct observations from codebase inspection and design context:

- **Original Request / Requirements (`/home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md`)**:
  - Phase 06 requires implementing `src/core/llm/provider.py` as a unified Python interface wrapping external LLMs via LangChain (`BaseChatModel` and `with_structured_output`), with rate limit/retry backoff logic and Pydantic V2 schema output enforcement.
- **Orchestrator Specification (`/home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase06/PROJECT.md`)**:
  - `BaseLLMProvider(abc.ABC)` class must accept `model_name`, `api_key`, `temperature`, `max_retries`, `timeout`.
  - Abstract method `@abstractmethod get_chat_model() -> BaseChatModel`.
  - Method `generate_structured(prompt, response_model) -> T` wrapping `get_chat_model().with_structured_output(response_model)`.
  - Maps 429 rate limits to `RateLimitError`, network issues to `NetworkError`, schema/parsing errors to `ValidationError`.
- **Existing Exception Hierarchy (`/home/adarsh/Documents/Youtube-Channel/src/core/exceptions.py`)**:
  - Line 22: `class RetryableError(PipelineError)`
  - Line 30: `class FatalError(PipelineError)`
  - Line 47: `class ValidationError(FatalError)`
  - Line 62: `class NetworkError(RetryableError)`
  - Line 67: `class AuthenticationError(FatalError)`
  - Line 72: `class RateLimitError(RetryableError)`
- **Existing Pydantic Schemas (`/home/adarsh/Documents/Youtube-Channel/src/core/models/video.py`)**:
  - Line 73: `class VideoMetadata(BaseModel)` and related Phase 05 schemas using Pydantic V2.

---

## 2. Logic Chain

1. **Requirement Mapping**: Phase 06 requires a vendor-agnostic provider layer that enforces structured outputs using Phase 05 Pydantic schemas.
2. **Interface Abstraction**: Defining `BaseLLMProvider` as an `abc.ABC` with abstract method `get_chat_model()` enables concrete provider classes (`OpenAIClient`, `AnthropicClient`) to encapsulate vendor SDK instantiation while sharing all execution, retry, and exception translation logic in the base class.
3. **Structured Output Integration**: Using LangChain's `chat_model.with_structured_output(response_model)` delegates JSON schema conversion and model parameter binding to LangChain, guaranteeing type-safe returning of Pydantic models (e.g. `VideoMetadata`).
4. **Resiliency Classification**:
   - `RateLimitError` (HTTP 429) and `NetworkError` (timeouts, connection errors, 5xx status codes) inherit from `RetryableError` in `src/core/exceptions.py`. These must be retried with exponential backoff and full jitter up to `max_retries`.
   - `ValidationError` (schema mismatch/JSON parser failure) and `AuthenticationError` (HTTP 401/403) inherit from `FatalError` in `src/core/exceptions.py`. These must fail fast without retrying.
5. **Exception Translation Layer**: Implementing `_translate_exception(exc)` inspects third-party exceptions (from `openai`, `anthropic`, `httpx`, `langchain`) and translates them into domain exceptions before throwing or logging.

---

## 3. Caveats

- **LangChain Package Dependency**: The design relies on `langchain-core`, `langchain-openai`, and `langchain-anthropic`. These packages must be added to `pyproject.toml` in Milestone 1 before implementing concrete clients.
- **Provider-Specific Null Returns**: Some models (or fallback parsers) might return `None` if structured output generation fails silently. The design explicitly catches this with `if result is None: raise ValidationError(...)`.

---

## 4. Conclusion

The architectural design for `BaseLLMProvider` in `src/core/llm/provider.py` is fully specified and documented in `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_iter1_1/analysis.md`. The design fulfills all Phase 06 requirements:
- Abstract base class interface with standard configuration parameters.
- Generic `generate_structured(prompt, response_model)` method leveraging LangChain's structured output interface.
- Exponential backoff retry loop with full jitter for transient errors.
- Comprehensive exception translation mapping external SDK/HTTP errors into `src/core/exceptions.py` pipeline exception hierarchy.

---

## 5. Verification Method

To verify the design analysis and prepare for implementation:

1. **Inspect Analysis Artifacts**:
   - Read `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_iter1_1/analysis.md` for complete class interfaces, method signatures, exception mapping matrix, sequence flow diagrams, and reference implementation.
2. **Implementation Check (Future Implementer Step)**:
   - When implemented in `src/core/llm/provider.py`, verify syntax and static types:
     ```bash
     python3 -m py_compile src/core/llm/provider.py
     ```
3. **Unit Test Verification (Future Test Suite Step)**:
   - Run provider tests once implemented:
     ```bash
     pytest tests/llm/test_providers.py
     ```
   - Invalidation condition: If `test_providers.py` fails to catch rate limits, fails to retry, or returns unparsed dictionaries instead of validated Pydantic objects.
