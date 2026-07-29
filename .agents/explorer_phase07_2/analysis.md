# Phase 07: Prompt Library & Management Requirements & Architectural Specification

## 1. Executive Summary & Objective Overview

Phase 07 introduces a centralized, version-controlled **Prompt Library & Management System** for the Automated Data Structures and Algorithms (DSA) Educational YouTube Video Pipeline. 

The primary goal of Phase 07 is to separate prompt engineering logic from Python codebase execution. By leveraging the **Jinja2** template engine, system prompts are rendered dynamically with strict variable interpolation, conditional logic, and looping structures. This system seamlessly integrates with the Phase 05 Pydantic V2 schemas (`EducationalPlan`, `VideoMetadata`, `RenderSegment`, etc.) and the Phase 06 LLM Provider Abstraction layer (`BaseLLMProvider`, `OpenAIClient`, `AnthropicClient`).

### Core Deliverables:
1. **Prompt Loading Engine** (`src/core/llm/prompt_loader.py`): A high-performance, version-aware, caching Jinja2 template loader and rendering engine.
2. **Foundational Prompt Templates**:
   - `templates/prompts/v1/educational_plan.j2`: System prompt for generating comprehensive educational lesson plans optimized for deep LLM reasoning.
   - `templates/prompts/v1/code_explanation.j2`: System prompt for generating line-by-line animated code explanations and visualization cues.
3. **Prompt Management Documentation** (`PromptBook/Phase07/01_Prompt_Library.md`): Architectural documentation detailing Jinja2 abstraction strategies, prompt engineering guidelines, and storage/versioning policies.
4. **Test Suite** (`tests/llm/test_prompt_loader.py`): Comprehensive test suite verifying template resolution, variable rendering, whitespace control, and error handling.

---

## 2. System Requirements & Architectural Integration

```
+---------------------------------------------------------------------------------+
|                                 Pipeline Stage                                  |
|                 (Script Generator, Tag Explorer, RAG Summarizer)                 |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                        PromptLoader (src/core/llm/prompt_loader.py)             |
|  - Loads templates from templates/prompts/{version}/{template_name}.j2           |
|  - Manages Jinja2 Environment with FileSystemLoader & StrictUndefined           |
|  - Caches compiled Template instances in-memory                                 |
|  - Renders rendered_prompt = prompt_loader.render("educational_plan", v="v1",..)|
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                    BaseLLMProvider (src/core/llm/provider.py)                   |
|  - Accepts rendered prompt string or message list                               |
|  - Calls LLM via LangChain with_structured_output(EducationalPlan)             |
|  - Returns validated Pydantic V2 domain model                                   |
+---------------------------------------------------------------------------------+
```

### Key Integration Contracts:
- **Configuration Integration**: `PipelineConfig` in `src/core/config.py` is extended to include `PromptConfig`, which specifies default template directories (`templates/prompts`) and default version (`v1`).
- **Exception Hierarchy Integration**: Custom template exceptions (`TemplateNotFoundError`, `TemplateRenderError`) inherit from `PipelineError` in `src/core/exceptions.py` under the operational classification `FatalError`.
- **LLM Provider Integration**: Rendered prompt strings from `PromptLoader.render()` are passed directly to `BaseLLMProvider.generate_structured(prompt, response_model)`.

---

## 3. Prompt Loading Engine Specification (`src/core/llm/prompt_loader.py`)

### 3.1 Configuration Updates (`src/core/config.py`)

A new `PromptConfig` class must be added to `src/core/config.py` and aggregated into `PipelineConfig` / `LLMConfig`:

```python
class PromptConfig(BaseSettings):
    """Configuration for Prompt Loader and Jinja2 Template Library."""

    template_dir: Path = Field(
        default=Path("templates/prompts"),
        description="Root directory containing versioned Jinja2 prompt templates"
    )
    default_version: str = Field(
        default="v1",
        description="Default prompt template version folder"
    )
    enable_cache: bool = Field(
        default=True,
        description="Whether to cache compiled Jinja2 template instances"
    )
    autoescape: bool = Field(
        default=False,
        description="Autoescape setting for Jinja2 environment (False for text/markdown prompts)"
    )
```

### 3.2 Exception Hierarchy Updates (`src/core/exceptions.py`)

New exception classes must be added to `src/core/exceptions.py`:

```python
# -- Module 4.1: Prompt Loader --
class PromptTemplateError(PipelineError):
    """Base exception for prompt template operations."""
    pass

class TemplateNotFoundError(PromptTemplateError, FatalError):
    """Raised when a requested prompt template file does not exist on disk."""
    pass

class TemplateRenderError(PromptTemplateError, FatalError):
    """Raised when Jinja2 fails to render a template due to syntax errors or missing variables."""
    pass
```

### 3.3 Class API & Method Specifications (`src/core/llm/prompt_loader.py`)

```python
"""
Prompt Loader Module.

Provides PromptLoader class for reading, caching, and rendering versioned Jinja2
prompt templates from disk.
"""

from pathlib import Path
from typing import Any, Dict, Optional, List
import jinja2
import structlog

from src.core.config import load_config
from src.core.exceptions import TemplateNotFoundError, TemplateRenderError

logger = structlog.get_logger(__name__)


class PromptLoader:
    """
    Centralized loader and renderer for versioned Jinja2 prompt templates.
    """

    def __init__(
        self,
        template_dir: Optional[Path | str] = None,
        default_version: str = "v1",
        enable_cache: bool = True,
    ) -> None:
        """
        Initialize PromptLoader.

        Args:
            template_dir: Path to template directory. Defaults to config settings.
            default_version: Default version subdirectory (e.g. 'v1').
            enable_cache: If True, caches compiled jinja2.Template objects.
        """
        if template_dir is None:
            config = load_config()
            self.template_dir = Path(config.data_dir).parent / "templates" / "prompts"
            if hasattr(config, "llm") and hasattr(config.llm, "prompt"):
                self.template_dir = config.llm.prompt.template_dir
        else:
            self.template_dir = Path(template_dir)

        self.default_version = default_version
        self.enable_cache = enable_cache
        self._template_cache: Dict[str, jinja2.Template] = {}

        # Initialize Jinja2 Environment with StrictUndefined to catch missing variables
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            autoescape=False,
            undefined=jinja2.StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.logger = logger.bind(template_dir=str(self.template_dir))

    def _resolve_template_path(self, template_name: str, version: Optional[str] = None) -> str:
        """
        Resolve relative template path within Jinja2 FileSystemLoader.

        Example:
            _resolve_template_path("educational_plan", "v1") -> "v1/educational_plan.j2"
        """
        ver = version or self.default_version
        clean_name = template_name.removesuffix(".j2")
        return f"{ver}/{clean_name}.j2"

    def get_template(self, template_name: str, version: Optional[str] = None) -> jinja2.Template:
        """
        Retrieve compiled Jinja2 Template object.

        Args:
            template_name: Name of template (with or without .j2 extension).
            version: Optional version identifier (defaults to self.default_version).

        Returns:
            jinja2.Template instance.

        Raises:
            TemplateNotFoundError: If template file does not exist on disk.
        """
        rel_path = self._resolve_template_path(template_name, version)

        if self.enable_cache and rel_path in self._template_cache:
            return self._template_cache[rel_path]

        try:
            template = self.env.get_template(rel_path)
            if self.enable_cache:
                self._template_cache[rel_path] = template
            return template
        except jinja2.TemplateNotFound as exc:
            full_path = self.template_dir / rel_path
            self.logger.error("prompt_template_not_found", path=str(full_path))
            raise TemplateNotFoundError(
                f"Prompt template '{template_name}' (version '{version or self.default_version}') not found at {full_path}"
            ) from exc

    def render(self, template_name: str, version: Optional[str] = None, **kwargs: Any) -> str:
        """
        Render a Jinja2 prompt template with context variables.

        Args:
            template_name: Name of template (e.g. 'educational_plan').
            version: Version string (e.g. 'v1').
            **kwargs: Context variables passed to Jinja2 rendering engine.

        Returns:
            Rendered prompt string stripped of leading/trailing extra whitespace.

        Raises:
            TemplateNotFoundError: If template file is missing.
            TemplateRenderError: If Jinja2 fails due to undefined variable or syntax error.
        """
        template = self.get_template(template_name, version)
        try:
            rendered = template.render(**kwargs)
            if not rendered or not rendered.strip():
                raise TemplateRenderError(
                    f"Template '{template_name}' rendered to an empty string."
                )
            return rendered.strip()
        except jinja2.UndefinedError as exc:
            self.logger.error("prompt_template_missing_variable", template=template_name, error=str(exc))
            raise TemplateRenderError(
                f"Missing required context variable in template '{template_name}': {exc}"
            ) from exc
        except jinja2.TemplateSyntaxError as exc:
            self.logger.error("prompt_template_syntax_error", template=template_name, line=exc.lineno, error=str(exc))
            raise TemplateRenderError(
                f"Syntax error in template '{template_name}' at line {exc.lineno}: {exc}"
            ) from exc
        except jinja2.TemplateError as exc:
            self.logger.error("prompt_template_render_failed", template=template_name, error=str(exc))
            raise TemplateRenderError(
                f"Failed to render template '{template_name}': {exc}"
            ) from exc

    def list_templates(self, version: Optional[str] = None) -> List[str]:
        """
        List all available template names for a given version directory.
        """
        target_ver = version or self.default_version
        version_dir = self.template_dir / target_ver
        if not version_dir.is_dir():
            return []
        return [p.stem for p in version_dir.glob("*.j2")]
```

---

## 4. Foundational Templates Specification

### 4.1 Template Directory Structure

The templates will be placed in the project root under:
```
templates/
└── prompts/
    └── v1/
        ├── educational_plan.j2
        └── code_explanation.j2
```

### 4.2 Educational Plan Generation Template (`templates/prompts/v1/educational_plan.j2`)

#### Purpose:
Generates system prompts instructing an LLM to act as a World-Class Computer Science Educator and produce a comprehensive, structured lesson plan (`EducationalPlan`) for a specific Data Structure or Algorithm problem.

#### Required Input Context Variables:
- `topic` (str): e.g. "Two Sum - Hash Map Approach"
- `slug` (str): e.g. "two-sum"
- `difficulty` (str): e.g. "Easy" | "Medium" | "Hard"
- `target_audience` (str): e.g. "Beginner" | "Intermediate" | "Advanced"
- `problem_description` (str): The full problem statement.
- `constraints` (list[str]): Memory/time constraints (e.g. `["1 <= nums.length <= 10^4"]`).
- `target_duration_seconds` (float): Target video duration (e.g. 180.0).
- `rag_context` (optional list[str]): Retrieved relevant algorithm knowledge base chunks.
- `code_implementations` (optional dict[str, str]): Code snippets keyed by language.

#### Template Content Specification (`educational_plan.j2`):
```jinja2
You are a World-Class Computer Science Educator and Senior Software Architect specializing in Data Structures and Algorithms (DSA).
Your mission is to construct a detailed, highly engaging educational lesson plan for a YouTube video explaining the DSA topic: "{{ topic }}".

=== TOPIC SPECIFICATIONS ===
- Topic Name: {{ topic }}
- URL Slug: {{ slug }}
- Target Audience: {{ target_audience }}
- Problem Difficulty: {{ difficulty }}
- Target Video Duration: {{ target_duration_seconds }} seconds

=== PROBLEM STATEMENT ===
{{ problem_description }}

{% if constraints %}
=== CONSTRAINTS & LIMITS ===
{% for constraint in constraints %}
- {{ constraint }}
{% endfor %}
{% endif %}

{% if rag_context %}
=== KNOWLEDGE BASE CONTEXT (RAG) ===
{% for chunk in rag_context %}
--- Context Block {{ loop.index }} ---
{{ chunk }}
{% endfor %}
{% endif %}

{% if code_implementations %}
=== REFERENCE CODE IMPLEMENTATIONS ===
{% for lang, code in code_implementations.items() %}
Language: {{ lang }}
```{{ lang }}
{{ code }}
```
{% endfor %}
{% endif %}

=== DEEP REASONING INSTRUCTIONS ===
Before outputting the structured educational plan, execute deep chain-of-thought analysis:
1. Pedagogical Breakdown: Determine the fundamental intuition needed to understand this problem.
2. Naive vs Optimal Approach: Highlight why the brute-force solution fails constraints and how the optimal solution overcomes it.
3. Target Audience Calibration:
{% if target_audience == 'Beginner' %}
   - Use clear real-world analogies (e.g., hash maps as labeled physical lockers).
   - Avoid overly dense mathematical notation without immediate plain-English translation.
{% elif target_audience == 'Advanced' %}
   - Focus on memory cache locality, bitwise optimizations, and formal asymptotic bounds.
   - Skip introductory syntax explanations.
{% else %}
   - Balance intuitive visual breakdown with rigorous Big-O time and space complexity analysis.
{% endif %}
4. Visual Animation Planning: Identify key moments that require animated visual cues (e.g., array pointer movements, hash table lookups, tree traversals).

=== REQUIRED OUTPUT STRUCTURE & INVARIANTS ===
Produce an educational plan matching the following invariants:
- Topic: "{{ topic }}"
- Slug: "{{ slug }}"
- Target Audience: "{{ target_audience }}"
- Difficulty: "{{ difficulty }}"
- Learning Objectives: At least 2 clear, actionable objectives.
- Sections: Sequential video sections (Intro, Problem Breakdown, Intuition, Algorithm Walkthrough, Complexity Analysis, Outro).
- Section Durations: The sum of all `estimated_duration` values across all sections MUST strictly equal {{ target_duration_seconds }} seconds (tolerance ±0.1s).
- Section IDs must be unique strings (e.g., "sec_01_intro", "sec_02_problem").
```

---

### 4.3 Code Explanation Template (`templates/prompts/v1/code_explanation.j2`)

#### Purpose:
Generates system prompts instructing an LLM to generate line-by-line animated code walkthroughs and state tracking cues (`CodeSnippet` & `PlanSection`).

#### Required Input Context Variables:
- `topic` (str): Algorithm name.
- `language` (str): e.g. "python", "cpp", "java".
- `code` (str): Complete solution code block.
- `line_highlights` (optional list[int]): Specific 1-based line numbers to emphasize.
- `common_pitfalls` (optional list[str]): Common bug patterns.
- `time_complexity` (str): e.g. "O(N)"
- `space_complexity` (str): e.g. "O(N)"

#### Template Content Specification (`code_explanation.j2`):
```jinja2
You are an Expert Visual Educator for Data Structures and Algorithms.
Your goal is to produce an in-depth, line-by-line code explanation script and animation sequence for the following algorithm: "{{ topic }}".

=== CODE SPECIFICATION ===
Language: {{ language }}
Source Code:
```{{ language }}
{{ code }}
```

=== COMPLEXITY BOUNDS ===
- Time Complexity: {{ time_complexity }}
- Space Complexity: {{ space_complexity }}

{% if line_highlights %}
=== KEY FOCUS LINES ===
Highlight and detail execution state for the following 1-based line numbers:
{% for line_num in line_highlights %}
- Line {{ line_num }}: Pay extra attention to state changes on this line.
{% endfor %}
{% endif %}

{% if common_pitfalls %}
=== COMMON PITFALLS & BUGS TO ADDRESS ===
{% for pitfall in common_pitfalls %}
- {{ pitfall }}
{% endfor %}
{% endif %}

=== DEEP REASONING & ANIMATION STATE INSTRUCTIONS ===
1. Step-by-Step State Tracking: Trace variable values, pointer locations, and data structure states (e.g., stack frames, hash map entries) line by line.
2. Code-to-Visual Mapping: Map code statements directly to visual animation cues (e.g., highlighting array indices in green, sliding window borders, tree node color changes).
{% if language == 'python' %}
3. Python Specifics: Explain Pythonic features used (e.g., enumerate, dictionary get defaults, list comprehensions).
{% elif language == 'cpp' %}
3. C++ Specifics: Highlight memory layout, vector allocations, and pointer/reference semantics.
{% endif %}

=== OUTPUT REQUIREMENTS ===
Return a structured code snippet explanation containing:
- snippet_id: Unique string identifier (e.g. "code_snippet_01")
- language: "{{ language }}"
- code: Full solution code
- explanation: Detailed line-by-line explanation narrative
- line_highlights: List of key line numbers {{ line_highlights | default([]) }}
```

---

## 5. Prompt Management Documentation Specification (`PromptBook/Phase07/01_Prompt_Library.md`)

The file `PromptBook/Phase07/01_Prompt_Library.md` must be documented with the following mandatory sections:

### Required Document Structure:

1. **Executive Summary & Architecture Overview**: High-level design of the Jinja2 Prompt Library & Management System, explaining template decoupling, versioning, and LLM provider integration.
2. **Prompt Loading Engine Architecture**:
   - Detailed specification of `PromptLoader` API in `src/core/llm/prompt_loader.py`.
   - Explanation of `jinja2.FileSystemLoader`, `StrictUndefined` variable checking, and in-memory caching.
   - Exception handling mapping (`TemplateNotFoundError`, `TemplateRenderError`).
3. **Template Storage & Versioning Strategy**:
   - File system layout (`templates/prompts/{version}/{template_name}.j2`).
   - Semantic versioning policy (`v1`, `v2`, etc.) and backward compatibility rules.
   - Adding new templates and migrating existing prompt versions.
4. **Prompt Engineering & Deep Reasoning Guidelines**:
   - CoT (Chain-of-Thought) reasoning prompting patterns.
   - Persona / Role definition standards ("World-Class Computer Science Educator").
   - Audience calibration rules (Beginner vs Intermediate vs Advanced).
   - Structured Output Enforcement: How prompts instruct LLMs to adhere strictly to Pydantic V2 schemas (`EducationalPlan`, `VideoMetadata`).
5. **Jinja2 Usage Standards & Conventions**:
   - Control flow standards (`{% if %}`, `{% for %}`).
   - Whitespace trimming rules (`trim_blocks=True`, `lstrip_blocks=True`, `-}}` usage).
   - Strict Undefined Enforcement: Why every variable must be provided or given explicit defaults (`| default(...)`).
6. **Foundational Template Catalog**:
   - Full documentation for `educational_plan.j2` and `code_explanation.j2`.
   - Input contracts (required and optional variables).
   - Rendered output examples.
7. **Verification & Testing Strategy**:
   - Pytest execution instructions (`pytest tests/llm/test_prompt_loader.py`).
   - Unit testing patterns using mock variables and string assertions.

---

## 6. Verification & Test Plan (`tests/llm/test_prompt_loader.py`)

### 6.1 Test Suite Objectives
The test suite in `tests/llm/test_prompt_loader.py` must achieve 100% test coverage for `PromptLoader` and foundational `.j2` templates:

### 6.2 Test Cases Matrix:

| Test Case Name | Goal / Description | Input Setup | Expected Result / Assertion |
|---|---|---|---|
| `test_prompt_loader_init_defaults` | Verify default path and Jinja2 environment initialization | Instantiate `PromptLoader()` | `loader.template_dir` points to `templates/prompts`, `loader.default_version == "v1"` |
| `test_render_educational_plan_success` | Render `educational_plan.j2` with valid mock variables | Topic="Two Sum", Slug="two-sum", Duration=180.0, etc. | Returns rendered string containing "Two Sum", "two-sum", "180.0 seconds", and deep reasoning prompts. Assert rendered output strictly matches expected string pattern. |
| `test_render_code_explanation_success` | Render `code_explanation.j2` with valid mock variables | Topic="Two Sum", Language="python", Code="def twoSum...", LineHighlights=[1, 4] | Returns rendered string containing "python", "def twoSum", and line highlights section. |
| `test_missing_template_raises_error` | Request non-existent template name | `loader.render("non_existent_template")` | Raises `TemplateNotFoundError` |
| `test_missing_required_variable_raises_error` | Omit required template variable | Render `educational_plan.j2` without `topic` | Raises `TemplateRenderError` due to `StrictUndefined` |
| `test_template_caching_behavior` | Verify template caching | Call `loader.get_template()` twice | Second call returns cached instance from `_template_cache` |
| `test_list_templates` | Verify template discovery | Call `loader.list_templates("v1")` | Returns list containing `['educational_plan', 'code_explanation']` |

---

## 7. Operational & Implementation Checklist

- [ ] Add `PromptConfig` to `src/core/config.py`.
- [ ] Add `PromptTemplateError`, `TemplateNotFoundError`, and `TemplateRenderError` to `src/core/exceptions.py`.
- [ ] Implement `PromptLoader` in `src/core/llm/prompt_loader.py`.
- [ ] Create folder structure `templates/prompts/v1/`.
- [ ] Implement `educational_plan.j2` in `templates/prompts/v1/educational_plan.j2`.
- [ ] Implement `code_explanation.j2` in `templates/prompts/v1/code_explanation.j2`.
- [ ] Document complete architecture in `PromptBook/Phase07/01_Prompt_Library.md`.
- [ ] Implement unit test suite in `tests/llm/test_prompt_loader.py` and run `pytest tests/llm/test_prompt_loader.py`.
