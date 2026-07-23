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
