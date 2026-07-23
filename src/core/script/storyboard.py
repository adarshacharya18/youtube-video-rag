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
