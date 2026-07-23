# Phase 12 / 09: Prompt Manager

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/script/prompts.py`](#2-source-code-srccorescriptpromptspy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

Hardcoding multi-line prompt strings deep inside business logic classes (like `EducationalPlanner` or `StoryboardGenerator`) violates the Single Responsibility Principle and makes prompt engineering—a notoriously iterative and fragile process—impossible to manage.

The **Prompt Manager** fully decouples the Generative AI text from the Python execution logic. It provides a strict `PromptTemplate` dataclass that supports versioning, required variable validation, few-shot example injection, and model-specific targeting. This guarantees that if a variable like `{rag_context}` is missing, the system throws a deterministic `ValueError` before making an expensive API call to Google Gemini.

---

# 2. Source Code: `src/core/script/prompts.py`

```python
"""
Prompt Manager for the Script Pipeline.

Decouples hardcoded prompt strings from the business logic.
Manages templates, variable substitution, and few-shot examples
for the Generative LLM integrations.
"""

import logging
import string
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class PromptTemplate:
    """A strictly versioned, model-specific prompt template."""
    id: str
    version: str
    target_model: str  # e.g., "gemini-1.5-pro", "gpt-4o"
    system_role: str
    template_text: str
    required_variables: List[str]
    few_shot_examples: List[Dict[str, str]] = field(default_factory=list)


class PromptManager:
    """Manages the loading, validation, and rendering of PromptTemplates."""
    
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._templates: Dict[str, PromptTemplate] = {}
        self._register_default_templates()

    def _register_default_templates(self) -> None:
        """Loads the baseline templates into memory."""
        # 1. Planner Template
        self._templates["educational_planner"] = PromptTemplate(
            id="educational_planner",
            version="1.0",
            target_model="gemini-1.5-pro",
            system_role="You are an expert Computer Science Professor creating a YouTube video script plan. Do NOT write the video script. ONLY write the pedagogical plan.",
            template_text="Target Problem: {slug}\n\n--- RAG CONTEXT ---\n{rag_context}\n--- END CONTEXT ---",
            required_variables=["slug", "rag_context"]
        )
        
        # 2. Narration Template with Few-Shot constraints
        self._templates["narration_planner"] = PromptTemplate(
            id="narration_planner",
            version="1.0",
            target_model="gemini-1.5-pro",
            system_role="You are a professional YouTube scriptwriter. Based on the Storyboard JSON, write the exact spoken narration. Adhere strictly to the estimated duration.",
            template_text="Problem: {slug}\n\n--- STORYBOARD ---\n{storyboard_json}",
            required_variables=["slug", "storyboard_json"],
            few_shot_examples=[
                {
                    "input": "Scene 1 (45s): Hook viewer on Two Sum.",
                    "output": "Welcome back! Today we are tackling Two Sum."
                }
            ]
        )
        
        # 3. Reviewer Template
        self._templates["content_reviewer"] = PromptTemplate(
            id="content_reviewer",
            version="1.0",
            target_model="gemini-1.5-pro",
            system_role="You are a Senior Principal Software Engineer reviewing a YouTube script. You MUST flag any mathematical hallucination as CRITICAL.",
            template_text="--- ORIGINAL RAG CONTEXT ---\n{original_rag_context}\n\n--- SCRIPT PAYLOAD ---\n{payload_json}",
            required_variables=["original_rag_context", "payload_json"]
        )

    def render(self, template_id: str, variables: Dict[str, str]) -> Tuple[str, str]:
        """
        Retrieves a template, validates the variables, and renders the strings.
        Returns a tuple of (system_prompt, user_prompt).
        """
        if template_id not in self._templates:
            self._logger.error(f"Template '{template_id}' not found.")
            raise ValueError(f"Template '{template_id}' not found.")
            
        template = self._templates[template_id]
        
        # Validate variables to fail fast before making expensive network API calls
        missing = [v for v in template.required_variables if v not in variables]
        if missing:
            self._logger.error(f"Missing variables for '{template_id}': {missing}")
            raise ValueError(f"Missing variables for prompt template: {missing}")
            
        # Render User Prompt strictly
        try:
            user_prompt = template.template_text.format(**variables)
        except KeyError as e:
            raise ValueError(f"Failed to render template. Missing key in payload: {e}")
            
        # Append few-shot examples if present to lock the LLM's behavioral output
        if template.few_shot_examples:
            user_prompt += "\n\n--- EXAMPLES ---\n"
            for ex in template.few_shot_examples:
                user_prompt += f"Input: {ex['input']}\nOutput: {ex['output']}\n\n"
                
        self._logger.debug(f"Successfully rendered prompt '{template_id}' v{template.version}")
        return (template.system_role, user_prompt)
```

---

# 3. Design Decisions

1. **Validation & Fail-Fast Mechanics:** In dynamic languages like Python, passing `**kwargs` into an f-string often masks missing variables until runtime, resulting in half-rendered prompts (e.g., `Target Problem: None`) being sent to the LLM. The `required_variables` array forces explicit validation, failing instantly if the upstream Orchestrator forgets to inject the RAG context.
2. **Few-Shot Decoupling (`few_shot_examples`):** Adding examples drastically improves LLM output stability, but appending them manually clutters code. By treating them as a generic array in the dataclass, the `render()` function automatically loops and structures them perfectly, preventing formatting drift.
3. **Model Targeting (`target_model`):** OpenAI's `gpt-4o` and Google's `gemini-1.5-pro` often respond completely differently to the same system role. By tagging each template with a `target_model`, the pipeline allows for future A/B testing where specific templates are routed to specific vendors for maximum efficiency.
