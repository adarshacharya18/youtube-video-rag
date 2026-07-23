# Phase02/09_Prompt_Assembly.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (Script Generation Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Core Prompt Components](#2-core-prompt-components)
3. [Prompt Template Architecture](#3-prompt-template-architecture)
4. [Variable Substitution](#4-variable-substitution)
5. [Validation & Output Schema](#5-validation--output-schema)
6. [Fallback Strategies](#6-fallback-strategies)
7. [Future Extensibility](#7-future-extensibility)

---

# 1. Executive Summary

This document specifies the **Prompt Assembly** architecture. After the RAG Engine retrieves and builds the educational context, the system must construct the final prompt injected into the LLM (Module 4: Script Generator). The Prompt Assembler ensures that the LLM perfectly balances rigid output formatting (for the Manim renderer) with engaging, educational narration.

---

# 2. Core Prompt Components

The final prompt is a strict concatenation of distinct instruction blocks:

1. **System Persona:** Defines the AI's identity (e.g., "You are an expert DSA instructor...").
2. **Problem Metadata:** The raw LeetCode problem, its constraints, difficulty, and algorithmic tags.
3. **Teaching Goals:** Directives based on difficulty (e.g., "For Hard problems, spend 30% of the script on math proofs").
4. **RAG Context:** The sanitized, token-limited payload from the Context Builder.
5. **Narration Style:** Guidelines on pacing, tone, and pacing (e.g., "Use simple analogies, avoid academic jargon, pace for a 5-minute video").
6. **Animation Requirements & Visual Cues:** Strict rules on how to format visual descriptions for the Manim parser (e.g., "Use hex codes for colors, define pointer movements").
7. **Output Schema:** The exact JSON structure the LLM must return.

---

# 3. Prompt Template Architecture

We use **Jinja2** (or standard Python `string.Formatter`) to maintain a clean, declarative prompt template. Hardcoding strings in Python is prohibited.

```text
=== SYSTEM IDENTITY ===
You are a world-class Data Structures and Algorithms instructor creating a script for a YouTube video.

=== PROBLEM ===
Name: {{ problem_name }}
Difficulty: {{ problem_difficulty }}
Tags: {{ problem_tags }}
Description: {{ problem_description }}

=== RETRIEVED EDUCATIONAL CONTEXT ===
You MUST base your theoretical explanations on the following curated context:
{{ rag_context }}

=== TEACHING & NARRATION GOALS ===
{{ teaching_goals }}
{{ narration_style }}

=== VISUAL & ANIMATION RULES ===
{{ visual_cues_instructions }}

=== OUTPUT SCHEMA ===
You must respond with ONLY valid JSON matching this schema. Do not include markdown blocks.
{{ json_schema }}
```

---

# 4. Variable Substitution

The Orchestrator passes the canonical Data Models into the Prompt Assembler, which maps the frozen dataclasses to the template variables.

- `problem_name` <- `ScrapedProblem.title`
- `problem_difficulty` <- `ScrapedProblem.difficulty`
- `rag_context` <- `ContextBuilder.build(RAGContext.retrieved_chunks)`
- `json_schema` <- `VideoScript.model_json_schema()` (using Pydantic/dataclass schema generation).

### 4.1 Security Sanitization (Prompt Injection Mitigation)
Before injection, `ScrapedProblem.description` is run through a strict regex sanitization pipeline. This step explicitly strips adversarial meta-prompts (e.g., words like "ignore previous instructions", "system prompt", "output instead") that a malicious user might have sneaked into a community LeetCode problem description, thereby protecting the Script Generator from generating off-brand content.

### 4.2 Dynamic Injection
The `teaching_goals` and `narration_style` variables are injected dynamically based on the tags. If `TagKnowledge.primary_pattern == "Graph"`, the `visual_cues_instructions` variable injects specific rules on how to animate nodes and edges in Manim, rather than rules for arrays.

---

# 5. Validation & Output Schema

The LLM is tasked with producing a highly complex structured output (`VideoScript`). 

### Structured Generation
We enforce JSON generation at the API level using Gemini's `response_schema` parameter (Structured Outputs) or by explicitly appending the JSON schema string to the prompt.

### Pydantic Validation
Upon receiving the string from the LLM, the system attempts to parse it into the `VideoScript` dataclass.
```python
try:
    script = VideoScript(**json.loads(llm_response))
except ValueError as e:
    raise SchemaValidationError(f"LLM failed to match schema: {e}")
```

---

# 6. Fallback Strategies

If the LLM fails to generate a valid schema (or triggers a safety filter):

1. **Auto-Correction Prompting:** 
   The system catches the `SchemaValidationError`, appends the exact Pydantic error message to the end of the original prompt, and instructs the LLM: *"Your previous output failed validation with the following error: {error}. Please fix the JSON and try again."*
2. **Context Reduction (Token Exhaustion Fallback):**
   If the failure was due to maximum output tokens reached (the script was too long), the pipeline truncates the `rag_context` by 50% and explicitly commands the LLM to write a shorter, more concise script.
3. **Graceful Degradation:**
   If 3 retries fail, a `CriticalError` is raised, saving the prompt and error to the `MemorySystem` for developer debugging, and the orchestrator moves to the next LeetCode problem.

---

# 7. Future Extensibility

The template-based architecture ensures long-term scalability.

1. **A/B Testing Prompts:** By decoupling the prompt text from the Python code, we can easily swap `templates/prompt_v1.jinja` with `templates/prompt_v2_aggressive_humor.jinja` to A/B test viewer engagement metrics.
2. **Multi-Agent Expansion:** In the future, the prompt assembly can be split. One LLM (Agent A) is prompted to write the narration using the RAG context, and a second LLM (Agent B) is prompted to take Agent A's narration and write the Manim visual cues. 
3. **Language Localization:** The template can easily inject a `{{ target_language }}` variable to prompt the LLM to write the narration in Spanish or Hindi while keeping the code and visual cues in English.
