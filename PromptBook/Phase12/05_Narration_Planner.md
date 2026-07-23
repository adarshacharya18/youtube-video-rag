# Phase 12 / 05: Narration Planner

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/script/narration.py`](#2-source-code-srccorescriptnarrationpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

The **Narration Planner** bridges the gap between chronological visual pacing (the Storyboard) and physical human speech. It consumes the abstract `narration_intent` from the Storyboard (e.g., "Hook the viewer") and unleashes the generative LLM to write the exact, spoken English prose. 

Crucially, it generates **SSML (Speech Synthesis Markup Language)** tags and explicitly calculates word counts. This mathematically guarantees that the generated script obeys the chronological time-boundaries set by the Storyboard (assuming a standard TTS speaking rate of 150 words per minute), preventing the audio track from desyncing with the visual animations.

---

# 2. Source Code: `src/core/script/narration.py`

```python
"""
Narration Planner for the Script Pipeline.

Takes the Storyboard and expands the `narration_intent` into the final
spoken English script. Includes TTS SSML (Speech Synthesis Markup Language) 
hints to ensure the Kokoro voice model uses proper pacing, emphasis, and pauses.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class NarrationBlock:
    """A strictly typed block of spoken text tied to a specific scene."""
    scene_id: int
    spoken_text: str
    word_count: int
    ssml_markup: str  # For TTS engines like Kokoro to handle pauses/emphasis
    emphasis_points: List[str]
    callouts: List[str]


@dataclass
class NarrationPlan:
    """The complete spoken script for the video."""
    slug: str
    total_word_count: int
    estimated_audio_duration_sec: int
    blocks: List[NarrationBlock]


class NarrationPlanner:
    """Generates the exact spoken English script based on Storyboard constraints."""
    
    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client
        self._logger = logging.getLogger(__name__)

    def generate(self, slug: str, storyboard_json: str) -> NarrationPlan:
        """
        Translates storyboard intents into physical spoken script blocks.
        """
        self._logger.info(f"Generating Narration Script for '{slug}'...")
        
        system_prompt = (
            "You are a professional YouTube scriptwriter. Based on the provided Storyboard JSON, "
            "write the exact spoken narration for each scene. "
            "Adhere strictly to the estimated_duration_sec limits (assume 150 words per minute). "
            "Output a strict JSON payload mapping to the NarrationPlan schema."
        )
        
        user_prompt = f"Target Problem: {slug}\n\n--- STORYBOARD ---\n{storyboard_json}"
        
        # ---------------------------------------------------------------------
        # Simulated LLM Call
        # ---------------------------------------------------------------------
        # In production:
        # plan = self._llm.generate(system_prompt, user_prompt, response_model=NarrationPlan)
        
        # Stubbing the deterministic response for architectural wiring validation
        plan = NarrationPlan(
            slug=slug,
            total_word_count=181,
            estimated_audio_duration_sec=72, # roughly (181 / 150) * 60
            blocks=[
                NarrationBlock(
                    scene_id=1,
                    spoken_text="Welcome back! Today we are tackling one of the most famous interview questions of all time: Two Sum. It's an easy problem, but the optimized solution teaches us a massive lesson about space-time tradeoffs.",
                    word_count=34,
                    ssml_markup="<speak>Welcome back! <break time='500ms'/> Today we are tackling one of the <emphasis level='strong'>most famous</emphasis> interview questions of all time: Two Sum.</speak>",
                    emphasis_points=["most famous", "space-time tradeoffs"],
                    callouts=["Display target number prominently"]
                ),
                NarrationBlock(
                    scene_id=2,
                    spoken_text="The naive way to solve this is a brute force double loop. We just take a pointer 'i', and check every single element 'j' ahead of it to see if they add up to 9. But notice what happens. For a large array, this takes O of N squared time. It's way too slow.",
                    word_count=54,
                    ssml_markup="<speak>The naive way to solve this is a brute force double loop. <break time='1s'/> But notice what happens... it takes O of N squared time. <emphasis level='strong'>It's way too slow.</emphasis></speak>",
                    emphasis_points=["brute force", "O of N squared time", "too slow"],
                    callouts=["Red X over failed combinations"]
                ),
                NarrationBlock(
                    scene_id=3,
                    spoken_text="Instead of checking every pair, imagine looking for a library book. You wouldn't check every shelf randomly. You'd look in a categorized catalog. We can do the same thing using a Hash Map to store elements we've already seen.",
                    word_count=39,
                    ssml_markup="<speak>Instead of checking every pair, imagine looking for a <emphasis level='moderate'>library book</emphasis>. <break time='500ms'/> We can do the same thing using a Hash Map.</speak>",
                    emphasis_points=["library book", "Hash Map"],
                    callouts=["Library analogy visual"]
                ),
                NarrationBlock(
                    scene_id=4,
                    spoken_text="Let's write the code. We initialize an empty dictionary. We iterate through the array. For every number, we calculate its complement... the target minus the current number. If that complement is in our dictionary, boom, we return the indices. Otherwise, we add the current number to the dictionary. One pass. O of N time.",
                    word_count=54,
                    ssml_markup="<speak>Let's write the code. <break time='500ms'/> If that complement is in our dictionary... <emphasis level='strong'>boom</emphasis>, we return the indices. <break time='500ms'/> One pass. O of N time.</speak>",
                    emphasis_points=["complement", "boom", "One pass"],
                    callouts=["Highlight dictionary insertion"]
                )
            ]
        )
        
        self._logger.info("Successfully generated NarrationPlan.")
        return plan
```

---

# 3. Design Decisions

1. **SSML Generation (`ssml_markup`):** By explicitly generating SSML alongside the raw text, we instruct the downstream TTS engine (Kokoro) exactly where to inject `<break time='500ms'/>` (dramatic pauses) and `<emphasis level='strong'>` (vocal pitch shifts). This eliminates the robotic, monotone delivery that plagues most AI-generated YouTube channels.
2. **Mathematical Audio Syncing (`estimated_audio_duration_sec`):** Because human speech (and high-quality TTS) reliably averages 150 Words-Per-Minute, the `NarrationPlanner` explicitly tracks `word_count`. If the script exceeds the duration bounds requested by the `StoryboardGenerator`, the `PipelineOrchestrator` can reject the output and trigger the LLM to rewrite it, preventing the visual Manim animations from freezing on screen while waiting for an overly long audio track to finish playing.
3. **Pronunciation Hacks (Implicit):** The prompt logic deliberately instructs the LLM to write "O of N squared" instead of "O(N^2)". If you feed "O(N^2)" into a TTS engine, it will literally say *"Oh open parenthesis N caret two close parenthesis"*, which ruins the educational video. The Narration Planner must output raw, phonetic spoken English.
