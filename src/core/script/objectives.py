"""
Learning Objective Generator for the Script Pipeline.

Uses RAG context to extract rigorous, pedagogically sound learning goals 
classified by Bloom's Taxonomy, setting the mathematical boundaries for the video.
"""

import logging
from dataclasses import dataclass
from typing import Any, List


@dataclass
class LearningObjective:
    """A strictly typed individual educational goal."""
    description: str
    blooms_level: str  # e.g., "Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"
    success_criteria: str
    knowledge_checkpoint: str


@dataclass
class LearningObjectivesPayload:
    """The aggregate blueprint of educational goals for the entire video."""
    primary_objectives: List[LearningObjective]
    secondary_objectives: List[LearningObjective]
    expected_outcomes: List[str]


class LearningObjectiveGenerator:
    """Extracts formal educational objectives from raw RAG context."""
    
    def __init__(self, llm_client: Any) -> None:
        # In a real environment, this is an injected Gemini or OpenAI client
        # that specifically supports Structured JSON Outputs (e.g., via instructor).
        self._llm = llm_client
        self._logger = logging.getLogger(__name__)

    def generate(self, slug: str, rag_context: str) -> LearningObjectivesPayload:
        """
        Synthesizes the physical DB RAG context into a strict array of 
        Bloom's Taxonomy-classified objectives.
        """
        self._logger.info(f"Generating Formal Learning Objectives for '{slug}'...")
        
        system_prompt = (
            "You are an expert Computer Science Curriculum Designer. "
            "Analyze the RAG Context for this LeetCode problem. "
            "Output a strict JSON payload mapping to the LearningObjectivesPayload schema. "
            "Every objective must be explicitly classified under Bloom's Taxonomy."
        )
        
        user_prompt = f"Target Problem: {slug}\n\n--- RAG CONTEXT ---\n{rag_context}\n--- END CONTEXT ---"
        
        # ---------------------------------------------------------------------
        # Simulated LLM Call
        # ---------------------------------------------------------------------
        # In production: 
        # payload = self._llm.generate(system_prompt, user_prompt, response_model=LearningObjectivesPayload)
        # 
        # For this architectural implementation, we stub the deterministic response
        # to validate downstream pipeline wiring.
        payload = LearningObjectivesPayload(
            primary_objectives=[
                LearningObjective(
                    description="Identify the inefficiencies of a brute-force O(N^2) double loop.",
                    blooms_level="Analyze",
                    success_criteria="Viewer can mathematically explain why checking every pair is computationally expensive.",
                    knowledge_checkpoint="Can the viewer spot the redundant work being done in the inner loop?"
                ),
                LearningObjective(
                    description="Implement an O(N) Hash Map solution.",
                    blooms_level="Apply",
                    success_criteria="Viewer can write the one-pass dictionary logic in Python.",
                    knowledge_checkpoint="Does the viewer know what to store as the key vs value?"
                )
            ],
            secondary_objectives=[
                LearningObjective(
                    description="Recall the average time complexity of Dictionary insertions.",
                    blooms_level="Remember",
                    success_criteria="Viewer states O(1) insertion time.",
                    knowledge_checkpoint="What happens to performance during a Hash Collision?"
                )
            ],
            expected_outcomes=[
                "Viewer can solve 'Two Sum' in an interview setting without hints.",
                "Viewer understands the memory tradeoff of storing seen elements."
            ]
        )
        
        self._logger.info("Successfully generated LearningObjectivesPayload.")
        return payload
