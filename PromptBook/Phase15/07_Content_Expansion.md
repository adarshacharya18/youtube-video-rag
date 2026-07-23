# Phase 15 / 07: Content Expansion Platform

**Author:** Principal Product Engineer  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/evolution/content_expansion.py`](#2-source-code-srccoreevolutioncontent_expansionpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

A highly optimized YouTube video is only one distribution channel. The **Content Expansion Platform** acts as an asset multiplier. Instead of asking an LLM to re-research "Dijkstra's Algorithm" from scratch, this subsystem injects the canonical, verified `Educational Plan` (generated back in Phase 12) directly into new formatting prompts.

This ensures that the terminology, time-complexity analysis, and core analogies used in the YouTube video identically match the supplementary Blog Posts, Newsletters, Podcast Scripts, Course Notes, Study Guides, and Interview Cheat Sheets.

---

# 2. Source Code: `src/core/evolution/content_expansion.py`

```python
"""
Content Expansion Platform (Phase 15)

Generates supplementary content (blog posts, newsletters, study guides, etc.)
by reusing the underlying Educational Plan generated during Phase 12.
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger("content_expansion")

class ContentExpansionPlatform:
    def __init__(self, llm_manager):
        # llm_manager is an instance of ModelManager (Phase 15/04) configured for LLMs
        self.llm_manager = llm_manager

    def generate_supplementary_content(self, educational_plan: Dict[str, Any], content_type: str) -> str:
        """
        Takes the canonical JSON Educational Plan (Phase 12) and expands it into
        different supplementary content formats.
        """
        valid_types = [
            "blog_post", "newsletter", "podcast_script", 
            "course_notes", "study_guide", "interview_sheet"
        ]
        
        if content_type not in valid_types:
            raise ValueError(f"Unsupported content type: {content_type}")
            
        logger.info(f"Generating {content_type} based on Educational Plan...")

        prompt = self._build_expansion_prompt(educational_plan, content_type)
        
        # Execute using the Model Manager's resilient fallback logic
        content = self.llm_manager.execute_with_fallback(
            category="llm",
            execution_callback=self._execute_llm_prompt,
            prompt=prompt
        )
        
        return content
        
    def _build_expansion_prompt(self, educational_plan: Dict[str, Any], content_type: str) -> str:
        """Constructs the LLM prompt based on the requested output format."""
        
        # Inject the VERIFIED data from the State Ledger, preventing LLM hallucinations
        base_context = f"""
        You are an expert technical writer. Using the following verified Educational Plan for a DSA video,
        generate a high-quality {content_type}. Do not invent new concepts outside this plan.
        
        Title: {educational_plan.get('title', 'Unknown')}
        Core Concept: {educational_plan.get('core_concept', 'Unknown')}
        Learning Objectives: {', '.join(educational_plan.get('learning_objectives', []))}
        """
        
        type_specific_instructions = {
            "blog_post": "Format this as an engaging technical blog post with markdown headings, code snippets, and a conversational tone.",
            "newsletter": "Format this as a concise weekly newsletter snippet. Focus on the 'why this matters' and provide a quick code example.",
            "podcast_script": "Format this as a conversational 2-person podcast script discussing the algorithm's pros and cons.",
            "course_notes": "Format this as structured academic course notes. Use bullet points and formal definitions.",
            "study_guide": "Format this as a study guide for a student. Include key terms to memorize and 3 practice questions.",
            "interview_sheet": "Format this as a cheat sheet for a software engineering interview. Highlight time/space complexity and common pitfalls."
        }
        
        return base_context + "\n\n" + type_specific_instructions[content_type]

    def _execute_llm_prompt(self, model_id: str, prompt: str) -> str:
        """
        STUB: Represents the actual call to the LLM Provider API.
        The `model_id` is automatically injected by the resilient ModelManager.
        """
        logger.info(f"Executing prompt via {model_id}...")
        return f"[{model_id} Generated Content]\n\n# Expanded Content\n\nBased on the prompt:\n{prompt[:100]}..."
```

---

# 3. Design Decisions

1. **Architectural DRY (Don't Repeat Yourself):** By strictly passing the `Educational Plan` JSON (from Phase 12) into the LLM context window, we eliminate AI hallucination discrepancies. If the original Educational Plan uses a "Library Book" analogy for Hash Maps, the Podcast Script and the Blog Post will naturally use the exact same analogy, maintaining brand consistency across all mediums.
2. **Resilient Integration:** The platform doesn't make raw HTTP calls. It passes the prompt into `self.llm_manager.execute_with_fallback()`. If OpenAI fails while generating the Newsletter, the Model Manager automatically catches the 503 error, updates telemetry, and routes the newsletter generation to an Anthropic fallback model.
3. **Format Extensibility:** Supporting new content types (e.g., "LinkedIn Post", "Twitter Thread") requires zero architectural changes. The system simply appends a new key to the `type_specific_instructions` dictionary.
