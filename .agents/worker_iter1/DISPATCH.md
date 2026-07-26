# DISPATCH — Worker Iteration 1

Objective: Implement Phase 06: LLM Provider Abstraction.

Read:
- `/home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md` (Phase 06 section)
- `/home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase06/PROJECT.md`
- Explorer Reports:
  - `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_iter1_1/analysis.md`
  - `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_iter1_2/analysis.md`
  - `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_iter1_3/analysis.md`

Tasks:
1. Update `requirements.txt` and `pyproject.toml` to include `langchain`, `langchain-core`, `langchain-openai`, `langchain-anthropic`, `openai`, `anthropic`.
   (Ensure dependencies are installed into `.venv` using `pip install`).
2. Update `src/core/config.py` to add `OpenAIConfig`, `AnthropicConfig`, and `LLMConfig`.
3. Create `src/core/llm/__init__.py` and `src/core/llm/provider.py` defining `BaseLLMProvider` with:
   - `generate_structured(prompt, response_model)` leveraging LangChain's `with_structured_output`
   - Resiliency retry & exponential backoff logic mapping API failures to `src/core/exceptions.py` (`RateLimitError`, `NetworkError`, `ValidationError`).
4. Create `src/core/llm/openai_client.py` (`OpenAIClient` wrapping `ChatOpenAI`).
5. Create `src/core/llm/anthropic_client.py` (`AnthropicClient` wrapping `ChatAnthropic`).
6. Create `tests/llm/__init__.py` and `tests/llm/test_providers.py`:
   - Unit tests using mocked API responses (`unittest.mock` / `pytest-mock`) testing both `OpenAIClient` and `AnthropicClient`.
   - Assert identical Pydantic object outputs (`VideoMetadata`, `EducationalPlan`, `RenderSegment`, etc.) from both clients.
   - Assert error handling and retry logic.
7. Create `PromptBook/Phase06/01_LLM_Abstraction.md`:
   - Document LLM provider strategy, retry logic, error mapping matrix, fallback mechanisms, and test usage.
8. Execute verification:
   - Run `./.venv/bin/pytest tests/llm/test_providers.py`
   - Run existing core tests: `./.venv/bin/pytest tests/core tests/models`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Deliverable: Write comprehensive implementation summary in `/home/adarsh/Documents/Youtube-Channel/.agents/worker_iter1/changes.md` and `handoff.md`.
