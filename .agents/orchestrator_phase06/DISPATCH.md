# DISPATCH

## 2026-07-26T04:12:13Z
<USER_REQUEST>
You are the Project Orchestrator for Phase 06: LLM Provider Abstraction of the Automated DSA Educational YouTube Video Pipeline.

Your agent working directory is `/home/adarsh/Documents/Youtube-Channel/.agents/orchestrator_phase06`.
The project workspace root is `/home/adarsh/Documents/Youtube-Channel`.
The verbatim requirements are recorded in `/home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md` (see the section for Phase 06).

Mission Overview:
Implement Phase 06: LLM Provider Abstraction for the Automated DSA Educational YouTube Video Pipeline. Create a unified, resilient Python interface wrapping external LLMs (OpenAI, Anthropic) that enforces strict structured output using the Pydantic models defined in Phase 05.

Key Requirements:
1. R1: Unified Provider Interface via LangChain
   - Implement `src/core/llm/provider.py` defining the provider interface.
   - Implement concrete classes `src/core/llm/openai_client.py` and `src/core/llm/anthropic_client.py`.
   - Utilize LangChain's `BaseChatModel` and `with_structured_output` as the underlying abstraction engine.
2. R2: Resiliency & Structured Output
   - Gracefully handle rate limits and API failures via built-in retry/backoff logic.
   - Integrate seamlessly with Phase 05 Pydantic models (`VideoMetadata`, `EducationalPlan`, `RenderSegment`, etc. in `src/core/models/`) to guarantee identically structured output regardless of active provider.
3. R3: Documentation
   - Document the provider strategy, retry logic, and fallback mechanisms in `PromptBook/Phase06/01_LLM_Abstraction.md`.
4. R4 & Acceptance Criteria:
   - `pytest tests/llm/test_providers.py` must run successfully with mocked API responses for both OpenAI and Anthropic, asserting identical Pydantic objects.
   - `src/core/llm/provider.py`, `openai_client.py`, and `anthropic_client.py` exist and leverage LangChain's structured output abstraction.
   - `PromptBook/Phase06/01_LLM_Abstraction.md` exists and documents the strategy.

Execute the implementation through your subagent workflow (exploration, implementation, review, testing, challenge). Write progress updates to your `progress.md` and report completion when all acceptance criteria are met.
</USER_REQUEST>
