# Phase 12 / 02: Educational Planner

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/script/planner.py`](#2-source-code-srccorescriptplannerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

If you tell an LLM to "Write a YouTube video about Dijkstra's Algorithm," it will immediately start generating `[Upbeat Intro Music]` and immediately dump unreadable Python code onto the screen. It lacks pacing, pedagogical structure, and visual awareness.

The **Educational Planner** acts as the crucial "brake pedal" for the Generative LLM. It intercepts the raw Markdown context from the RAG Runtime (Phase 11) and strictly refuses to write the video script. Instead, it forces the LLM to output a purely structural `TeachingPlan`—a JSON blueprint defining prerequisites, analogies, common misconceptions, and the chronological teaching order. This blueprint physically constrains the downstream generative phases.

---

# 2. Source Code: `src/core/script/planner.py`

```python
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
```

---

# 3. Design Decisions

1. **Strictly Typed Outputs (`TeachingPlan` Dataclass):** Rather than letting the LLM output a generic string like *"Here is my teaching plan..."*, we force it into a strict JSON payload that perfectly maps to the `TeachingPlan` dataclass. This allows downstream python code (`compile_storyboard_seed`) to iterate over the data deterministically, extracting `plan.teaching_order` without relying on messy Regex parsing.
2. **Forced Analogies (`core_analogy`):** Educational videos fail when they only talk about arrays and pointers. By forcing the LLM to fill out a `core_analogy` field based on the RAG context *before* it writes any narration, we guarantee that the final script will include a real-world metaphor (e.g., "Library Book"), drastically improving viewer retention.
3. **Storyboard Seeding (`compile_storyboard_seed`):** The final output of the Planner is a physical array of chronological "Seeds". This physically prevents the downstream Script Generator from rambling or messing up the pacing, as it will be forced to generate exactly one paragraph of text per Seed, adhering strictly to the `teaching_order`.
