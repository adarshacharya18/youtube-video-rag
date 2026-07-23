# Phase 12 / 03: Learning Objective Generator

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/script/objectives.py`](#2-source-code-srccorescriptobjectivespy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

Before the `EducationalPlanner` (Phase 12/02) can logically sequence a storyboard, the system must establish **why** the video exists in the first place. What exactly is the viewer supposed to learn?

The **Learning Objective Generator** is a specialized LLM wrapper that parses the raw RAG Context and constructs formal, pedagogically sound goals classified under **Bloom's Taxonomy** (Remember, Understand, Apply, Analyze, Evaluate, Create). By forcing the LLM to define strict `success_criteria` and `knowledge_checkpoints`, the pipeline ensures the final video script will inherently test the viewer's understanding rather than just passively reciting Python code.

---

# 2. Source Code: `src/core/script/objectives.py`

```python
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
```

---

# 3. Design Decisions

1. **Bloom's Taxonomy Integration (`blooms_level`):** By forcing the LLM to classify every objective, we prevent the generative engine from making "lazy" videos. If all objectives are classified as "Remember", the video will be boring. By forcing "Analyze" and "Apply" objectives, the LLM will naturally generate scripts that challenge the viewer with deep, mathematical reasoning.
2. **Actionable Success Criteria (`success_criteria`):** Abstract goals like "Understand Two Sum" are impossible to measure. By requiring the LLM to define *how* the user proves they understand it (e.g., "Viewer can mathematically explain why..."), the downstream `Reviewer` module has a rigid, physical metric to grade the final generated script against.
3. **Knowledge Checkpoints:** This specific field is passed directly to the `NarrationPlanner` later in the pipeline. It forces the final English script to actually pause the video and ask the viewer a direct rhetorical question (e.g., *"But wait... what happens if our Hash Map gets a collision?"*), drastically boosting viewer retention and engagement metrics on YouTube.
