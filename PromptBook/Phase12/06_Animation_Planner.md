# Phase 12 / 06: Animation Planner

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/script/animation.py`](#2-source-code-srccorescriptanimationpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

Generative LLMs are notoriously terrible at writing raw Manim Python code. If you ask an LLM to "animate an array," it will frequently invent nonexistent Manim classes (`ManimArray`), misuse coordinate systems, and fail to compile, destroying the entire pipeline.

The **Animation Planner** solves this by strictly forbidding the LLM from writing Python code. Instead, it acts as a semantic compiler. It reads the `animation_requirements` from the Storyboard and outputs a strictly typed JSON payload of abstract `VisualObjects` and `AnimationActions` bound to a chronological `timestamp_sec`. 

This mathematical JSON blueprint is safely passed downstream to Phase 14, where a deterministic, hardcoded Python Manim factory will parse it and render the physical MP4.

---

# 2. Source Code: `src/core/script/animation.py`

```python
"""
Animation Planner for the Script Pipeline.

Takes the Storyboard and expands the `animation_requirements` into a 
strictly typed JSON schema that defines the visual state of the screen at
every millisecond of the scene. It does NOT generate Manim Python code; 
it generates the semantic blueprint that the Manim Engine will parse.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class VisualObject:
    """A semantic definition of an object on screen (e.g., Array, CodeBlock)."""
    object_id: str
    object_type: str  # "Array", "Pointer", "Text", "CodeBlock", "HashMap"
    initial_position: str # "CENTER", "LEFT", "UP"
    color_annotation: str


@dataclass
class AnimationAction:
    """A specific animation event triggered at a specific timestamp."""
    timestamp_sec: float
    target_object_id: str
    action_type: str  # "FadeIn", "MoveTo", "Highlight", "Transform"
    action_parameters: Dict[str, Any]


@dataclass
class AnimationScene:
    """The complete visual state and timeline for a single scene cut."""
    scene_id: int
    objects: List[VisualObject]
    timeline: List[AnimationAction]
    camera_guidance: str


@dataclass
class AnimationPlan:
    """The aggregate visual blueprint for the entire video."""
    slug: str
    scenes: List[AnimationScene]


class AnimationPlanner:
    """Generates the formal visual blueprint from Storyboard constraints."""
    
    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client
        self._logger = logging.getLogger(__name__)

    def generate(self, slug: str, storyboard_json: str) -> AnimationPlan:
        """
        Translates storyboard intents into a physical timeline of visual actions.
        """
        self._logger.info(f"Generating Animation Plan for '{slug}'...")
        
        system_prompt = (
            "You are a YouTube Visual Effects Director. Based on the provided Storyboard JSON, "
            "write the exact sequence of visual actions for each scene. "
            "Output a strict JSON payload mapping to the AnimationPlan schema. "
            "Do NOT write Manim Python code. Only write the semantic JSON actions."
        )
        
        user_prompt = f"Target Problem: {slug}\n\n--- STORYBOARD ---\n{storyboard_json}"
        
        # ---------------------------------------------------------------------
        # Simulated LLM Call
        # ---------------------------------------------------------------------
        # In production:
        # plan = self._llm.generate(system_prompt, user_prompt, response_model=AnimationPlan)
        
        # Stubbing the deterministic response for architecture validation
        plan = AnimationPlan(
            slug=slug,
            scenes=[
                AnimationScene(
                    scene_id=1,
                    objects=[
                        VisualObject("title_text", "Text", "UP", "WHITE"),
                        VisualObject("main_array", "Array", "CENTER", "BLUE")
                    ],
                    timeline=[
                        AnimationAction(0.0, "title_text", "Write", {"text": "Two Sum"}),
                        AnimationAction(1.5, "main_array", "FadeIn", {"elements": [2, 7, 11, 15]}),
                        AnimationAction(3.0, "main_array", "Highlight", {"index": 0, "color": "YELLOW"}),
                        AnimationAction(3.5, "main_array", "Highlight", {"index": 1, "color": "YELLOW"})
                    ],
                    camera_guidance="Static wide shot."
                ),
                AnimationScene(
                    scene_id=2,
                    objects=[
                        VisualObject("main_array", "Array", "CENTER", "BLUE"),
                        VisualObject("ptr_i", "Pointer", "BELOW_ARRAY", "RED"),
                        VisualObject("ptr_j", "Pointer", "BELOW_ARRAY", "GREEN")
                    ],
                    timeline=[
                        AnimationAction(0.0, "ptr_i", "FadeIn", {"target_index": 0}),
                        AnimationAction(0.5, "ptr_j", "FadeIn", {"target_index": 1}),
                        AnimationAction(2.0, "ptr_j", "MoveTo", {"target_index": 2}),
                        AnimationAction(3.5, "ptr_j", "MoveTo", {"target_index": 3}),
                        AnimationAction(5.0, "ptr_i", "MoveTo", {"target_index": 1})
                    ],
                    camera_guidance="Zoom in to scale 1.5 on main_array."
                )
            ]
        )
        
        self._logger.info("Successfully generated AnimationPlan.")
        return plan
```

---

# 3. Design Decisions

1. **Anti-Hallucination via Indirection (`action_type`):** If an LLM writes `self.play(Create(Square()))`, it might hallucinate the import or syntax. By forcing it to output `action_type: "FadeIn"`, we remove Python syntax from the LLM's responsibilities entirely. The downstream Manim engine will simply map the string `"FadeIn"` to its own safe, hardcoded Python implementation.
2. **Explicit Timestamps (`timestamp_sec`):** The LLM is forced to define the exact second an animation triggers (e.g., `3.5`). This allows the downstream Assembly Engine to take the generated TTS audio (from the Narration Planner) and perfectly sync the visual pointer moving with the exact moment the Kokoro TTS voice says "Pointer J moves to the right".
3. **State Management (`object_id`):** By requiring the LLM to define `objects` before acting on them, we ensure the downstream Manim engine can instantiate the objects in memory before the `timeline` tries to manipulate them, completely eliminating `NameError: object not defined` crashes during video rendering.
