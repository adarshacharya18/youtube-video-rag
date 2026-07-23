# Phase 12 / 04: Storyboard Generator

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/script/storyboard.py`](#2-source-code-srccorescriptstoryboardpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

Now that we possess the `TeachingPlan` (the pedagogical blueprint) and the `LearningObjectivesPayload` (the formal educational goals), the pipeline must translate these abstract academic concepts into a concrete **YouTube video timeline**.

The **Storyboard Generator** maps the educational prerequisites to physical `Scenes`. It establishes strict pacing by forcing `estimated_duration_sec` calculations, prevents visual whiplash by dictating `visual_transition_in`, and guides the future downstream Manim renderer by setting `animation_requirements` and `camera_guidance`. This ensures the ultimate English narration perfectly syncs with what the viewer is seeing on screen.

---

# 2. Source Code: `src/core/script/storyboard.py`

```python
"""
Storyboard Generator for the Script Pipeline.

Takes the chronological Teaching Plan (Seeds) and the formal Learning Objectives,
and expands them into a precise, time-estimated sequence of Scenes (Storyboard).
This maps the abstract pedagogical goals directly to the YouTube timeline.
"""

import logging
from dataclasses import dataclass
from typing import Any, List


@dataclass
class StoryboardScene:
    """A strictly typed individual scene representing a continuous visual cut in the video."""
    scene_id: int
    focus_topic: str
    estimated_duration_sec: int
    scene_description: str
    visual_transition_in: str
    animation_requirements: str
    camera_guidance: str
    narration_intent: str


@dataclass
class StoryboardPayload:
    """The complete video timeline."""
    slug: str
    total_estimated_duration_sec: int
    scenes: List[StoryboardScene]


class StoryboardGenerator:
    """Expands educational blueprints into a strict timeline of visual scenes."""
    
    def __init__(self, llm_client: Any) -> None:
        # In a real environment, this is an injected Gemini or OpenAI client
        # that specifically supports Structured JSON Outputs.
        self._llm = llm_client
        self._logger = logging.getLogger(__name__)

    def generate(self, slug: str, teaching_plan_json: str, objectives_json: str) -> StoryboardPayload:
        """
        Synthesizes the Teaching Plan and Objectives into a chronological Video Storyboard.
        """
        self._logger.info(f"Generating Storyboard timeline for '{slug}'...")
        
        system_prompt = (
            "You are a YouTube Video Director specializing in Manim animations. "
            "Convert the provided Teaching Plan and Learning Objectives into a sequence of scenes. "
            "Output a strict JSON payload mapping to the StoryboardPayload schema. "
            "Ensure total duration is under 8 minutes."
        )
        
        user_prompt = (
            f"Problem: {slug}\n\n"
            f"--- TEACHING PLAN ---\n{teaching_plan_json}\n\n"
            f"--- OBJECTIVES ---\n{objectives_json}"
        )
        
        # ---------------------------------------------------------------------
        # Simulated LLM Call
        # ---------------------------------------------------------------------
        # In production: 
        # payload = self._llm.generate(system_prompt, user_prompt, response_model=StoryboardPayload)
        
        # Stubbing the deterministic response for architecture validation
        payload = StoryboardPayload(
            slug=slug,
            total_estimated_duration_sec=300,
            scenes=[
                StoryboardScene(
                    scene_id=1,
                    focus_topic="Introduce the problem visually with a simple array.",
                    estimated_duration_sec=45,
                    scene_description="Show an array [2,7,11,15] and a target 9. Visually search for the answer.",
                    visual_transition_in="Fade in from black to a clean code editor window.",
                    animation_requirements="Array elements need to be distinct blocks. Target 9 should pulse.",
                    camera_guidance="Static wide shot showing the whole array.",
                    narration_intent="Hook the viewer. Explain what Two Sum is and why it's asked in every interview."
                ),
                StoryboardScene(
                    scene_id=2,
                    focus_topic="Explain the Brute Force double-for-loop trap.",
                    estimated_duration_sec=90,
                    scene_description="Highlight two pointers (i and j) comparing every single combination.",
                    visual_transition_in="Slide left from the intro text to the expanded array.",
                    animation_requirements="Red 'X' animations when elements don't sum to 9. Nested loop tracker.",
                    camera_guidance="Zoom in slightly on the active (i, j) pair.",
                    narration_intent="Show how slow this is. Fulfill the Objective to identify O(N^2) inefficiency."
                ),
                StoryboardScene(
                    scene_id=3,
                    focus_topic="Use the 'Library Book' analogy to introduce Hash Maps.",
                    estimated_duration_sec=75,
                    scene_description="Visual metaphor of looking for a book on a shelf vs checking a sorted database.",
                    visual_transition_in="Crossfade to the abstract visual metaphor.",
                    animation_requirements="Iconography of a book/dictionary being populated.",
                    camera_guidance="Static center.",
                    narration_intent="Introduce the core analogy to explain the O(N) memory tradeoff."
                ),
                StoryboardScene(
                    scene_id=4,
                    focus_topic="Walk through the optimal Python code line-by-line.",
                    estimated_duration_sec=90,
                    scene_description="Display Python code. Trace it against the [2,7,11,15] array.",
                    visual_transition_in="Wipe down to reveal the split screen: Code on left, Array on right.",
                    animation_requirements="Syntax highlighting. Line-by-line yellow highlight. Populate dictionary map.",
                    camera_guidance="Split screen wide shot.",
                    narration_intent="Deliver the final solution. Ensure the knowledge checkpoint about Hash Collisions is mentioned."
                )
            ]
        )
        
        self._logger.info("Successfully generated StoryboardPayload.")
        return payload
```

---

# 3. Design Decisions

1. **Forced Pacing (`estimated_duration_sec`):** If an LLM is asked to write a script without constraints, it will write a 30-minute monologue for a single slide of Python code. By forcing the Storyboard Generator to explicitly calculate the number of seconds each scene should last, the downstream `NarrationPlanner` can mathematically constrain the English word count (since standard TTS reads at ~150 words per minute).
2. **Decoupling Intent from English (`narration_intent`):** Notice that the Storyboard does *not* write the English script. It only writes the *intent* (e.g., "Hook the viewer"). This adheres to the Single Responsibility Principle, ensuring the Storyboard LLM focuses entirely on visual pacing without getting distracted by trying to write funny YouTube jokes.
3. **Camera & Visual Guardrails:** Manim animations require strict geometric positioning. By having the LLM explicitly state `camera_guidance="Zoom in slightly on the active (i, j) pair."`, the downstream `AnimationPlanner` can accurately translate this into deterministic Python code (`self.play(self.camera.frame.animate.scale(0.5).move_to(i_ptr))`).
