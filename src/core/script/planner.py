"""
Educational Planner for the Script Generation Pipeline.

Uses a Generative LLM to digest RAG context and output a strictly typed
pedagogical blueprint (Teaching Plan) which sets the boundaries for
downstream script generation.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TeachingPlan:
    """The strictly typed pedagogical blueprint."""
    learning_objectives: List[str]
    target_audience: str
    difficulty_level: str
    prerequisites: List[str]
    teaching_order: List[str]
    common_misconceptions: List[str]
    core_analogy: str
    visual_opportunities: List[str]
    examples: List[str]


class EducationalPlanner:
    """Generates the pedagogical blueprint from raw RAG chunks."""
    
    def __init__(self, llm_client: Any) -> None:
        # In a real environment, this is an injected Gemini or OpenAI client
        # that specifically supports Structured JSON Outputs (e.g., instructor).
        self._llm = llm_client
        self._logger = logging.getLogger(__name__)

    def generate_plan(self, slug: str, rag_context: str) -> TeachingPlan:
        """
        Analyzes the physical markdown context provided by the RAG Engine
        and mathematically extracts a pedagogical execution plan.
        """
        self._logger.info(f"Generating Educational Plan for '{slug}'...")
        
        system_prompt = (
            "You are an expert Computer Science Professor creating a YouTube video script plan. "
            "Analyze the provided RAG Context and generate a strict JSON payload mapping to the TeachingPlan schema. "
            "Do NOT write the video script. ONLY write the pedagogical plan."
        )
        
        user_prompt = f"Target Problem: {slug}\n\n--- RAG CONTEXT ---\n{rag_context}\n--- END CONTEXT ---"
        
        # ---------------------------------------------------------------------
        # Simulated LLM Call
        # ---------------------------------------------------------------------
        # In production: 
        # plan = self._llm.generate(system_prompt, user_prompt, response_model=TeachingPlan)
        # 
        # For this architectural implementation, we stub the deterministic response
        # to prove the pipeline wiring.
        plan = TeachingPlan(
            learning_objectives=[
                "Understand the naive O(N^2) brute force approach.",
                "Recognize the space-time tradeoff of using a Hash Map.",
                "Implement the optimal O(N) solution in Python."
            ],
            target_audience="Beginner",
            difficulty_level="Easy",
            prerequisites=["Arrays", "Hash Maps"],
            teaching_order=[
                "Introduce the problem visually with a simple array.",
                "Explain the Brute Force double-for-loop trap.",
                "Use the 'Library Book' analogy to introduce Hash Maps.",
                "Walk through the optimal Python code line-by-line."
            ],
            common_misconceptions=[
                "Thinking you need to sort the array first (destroys original indices).",
                "Using two passes when one pass is sufficient."
            ],
            core_analogy="Looking for a matching puzzle piece in a messy room vs checking a categorized drawer.",
            visual_opportunities=[
                "Highlight the two pointers in the brute force array.",
                "Show a physical 'dictionary' being populated in memory as we iterate."
            ],
            examples=["[2, 7, 11, 15], target = 9"]
        )
        
        self._logger.info("Successfully generated deterministic TeachingPlan.")
        return plan

    def compile_storyboard_seed(self, plan: TeachingPlan) -> List[Dict[str, Any]]:
        """
        Translates the abstract pedagogical plan into chronological 'Scenes' 
        that the downstream Storyboard Generator will populate.
        """
        seed = []
        for index, topic in enumerate(plan.teaching_order):
            scene = {
                "sequence": index + 1,
                "focus": topic,
                "animation_hint": "TBD by Animation Planner",
                "misconception_warning": None
            }
            
            # Dynamically map misconceptions to the scenes to warn the script writer
            # not to make the mistake when generating the actual English prose.
            if "Brute Force" in topic and plan.common_misconceptions:
                scene["misconception_warning"] = plan.common_misconceptions[0]
                
            seed.append(scene)
            
        return seed
