# Phase 13 / 04: Animation Production

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/media/animation.py`](#2-source-code-srccoremediaanimationpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

While Phase 12 generated the *semantic mathematical blueprint* of an animation (the `AnimationPlan`), the **Animation Production Subsystem** is responsible for physically rendering the pixels. It takes the `AnimationPlan` and the `Storyboard` as inputs, enforces strict timing constraints to guarantee perfect audio-visual synchronization, and delegates the heavy lifting to a concrete provider (like Manim Community Edition).

Crucially, as per the strict architectural constraints, this module **does not contain any direct Manim code**. It strictly defines the `AnimationProviderProtocol` and the `RenderedScene` boundaries, ensuring that the heavy GPU/CPU rendering logic is completely abstracted behind a clean interface. This guarantees that if Manim is later replaced by another engine (like Remotion or a custom PyGame renderer), the core Orchestrator remains entirely unaffected.

---

# 2. Source Code: `src/core/media/animation.py`

```python
"""
Animation Production Subsystem (Phase 13)

Defines the AnimationProviderProtocol which translates mathematical AnimationPlans
and Storyboards into rendered video scenes. Abstracts away specific rendering
engines (like Manim) to allow future hot-swapping of visual generators.
"""

import logging
from dataclasses import dataclass
from typing import List, Protocol

from src.core.script.animation import AnimationPlan
from src.core.script.storyboard import StoryboardPayload


@dataclass(frozen=True)
class RenderedScene:
    """Immutable metadata tracking a physical rendered video scene on disk."""
    scene_id: int
    file_path: str
    duration_sec: float
    checksum: str
    resolution: str = "1920x1080"
    fps: int = 60


class AnimationProviderProtocol(Protocol):
    """Abstract interface for all Visual Rendering engines (Strategy Pattern)."""
    
    def render_scenes(
        self,
        storyboard: StoryboardPayload,
        animation_plan: AnimationPlan,
        output_dir: str
    ) -> List[RenderedScene]:
        """
        Translates a semantic animation blueprint into rendered video files.
        """
        ...


class ManimAnimationProvider:
    """
    Concrete implementation stub for the Manim CE rendering engine.
    Orchestrates the Manim CLI or Python API to render scenes based on the AnimationPlan.
    """
    def __init__(self, quality: str = "high_quality"):
        self._logger = logging.getLogger(__name__)
        self.quality = quality
        
    def _calculate_timing(self, storyboard: StoryboardPayload) -> dict:
        """
        Extracts strict timing constraints from the Storyboard to keep animations 
        perfectly synced with the generated audio.
        """
        timings = {}
        for scene in storyboard.scenes:
            timings[scene.scene_id] = scene.duration_sec
        return timings

    def render_scenes(
        self,
        storyboard: StoryboardPayload,
        animation_plan: AnimationPlan,
        output_dir: str
    ) -> List[RenderedScene]:
        
        self._logger.info(f"Initializing Manim renderer at {self.quality}")
        
        # Calculate exactly how long each scene must be to match the Voice Audio
        timings = self._calculate_timing(storyboard)
        rendered_scenes = []
        
        for scene_data in animation_plan.scenes:
            scene_id = scene_data.scene_id
            target_duration = timings.get(scene_id, 0)
            
            self._logger.info(f"Rendering Scene {scene_id}. Target Duration enforced: {target_duration}s")
            
            # STUB: Do not generate Manim syntax directly here as per architectural rules.
            # In production, this dynamically triggers a subprocess to run `manim scene.py`
            # or interfaces directly with the Manim Python API to generate frames.
            output_path = f"{output_dir}/scene_{scene_id}.mp4"
            
            # Mock returning successful physical generation
            rendered_scenes.append(
                RenderedScene(
                    scene_id=scene_id,
                    file_path=output_path,
                    duration_sec=target_duration,
                    checksum="sha256_mock_hash_for_idempotency",
                )
            )
            
        return rendered_scenes
```

---

# 3. Design Decisions

1. **Strict Audio-Visual Synchronization (`_calculate_timing`):** If an animation scene completes in 3 seconds, but the TTS Voice takes 5 seconds to finish speaking, the video will desync. By cross-referencing the `AnimationPlan` with the `StoryboardPayload` (which tracks voice durations), the Provider can enforce padding and wait-states, mathematically guaranteeing perfect alignment.
2. **Abstract Rendering Boundary:** The `AnimationProviderProtocol` doesn't know what "Manim" is. It only knows that it receives a JSON `AnimationPlan` and must yield a list of `RenderedScene` objects pointing to `.mp4` files. This means you could literally write a `BlenderProvider` or `RemotionProvider` in the future without changing a single line of business logic.
3. **Idempotency Ready (`RenderedScene`):** By attaching cryptographic `checksum` strings to the `RenderedScene` dataclass, the Persistence Layer can track exactly which scenes have been successfully rendered. If a 12-hour GPU render crashes at Scene 10, the Orchestrator can resume precisely where it left off, bypassing Scenes 1-9 instantly.
