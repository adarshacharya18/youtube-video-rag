"""
Script Generator for the Script Pipeline.

Consolidates the Teaching Plan, Storyboard, Narration Plan, and Animation Plan
into the final, versioned Artifacts. Emits both a strict JSON payload for 
downstream renderers and a human-readable Markdown artifact.
"""

import datetime
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict

# Assuming these are imported from the respective architectural modules
from src.core.script.animation import AnimationPlan
from src.core.script.narration import NarrationPlan
from src.core.script.planner import TeachingPlan
from src.core.script.storyboard import StoryboardPayload


@dataclass
class FinalScriptPayload:
    """The master compiler output containing all video data."""
    version: str
    generated_at: str
    slug: str
    teaching_plan: Dict[str, Any]
    storyboard: Dict[str, Any]
    narration: Dict[str, Any]
    animation: Dict[str, Any]


class ScriptGenerator:
    """Compiles individual plans into the final artifact payload."""
    
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def compile(self, 
                slug: str, 
                teaching_plan: TeachingPlan, 
                storyboard: StoryboardPayload, 
                narration: NarrationPlan, 
                animation: AnimationPlan) -> FinalScriptPayload:
        """
        Merges the 4 distinct architectural plans into a single versioned JSON payload.
        """
        self._logger.info(f"Compiling Final Script Payload for '{slug}'...")
        
        # The ultimate payload embeds the individual dataclasses by converting them to dicts
        payload = FinalScriptPayload(
            version="1.0.0",
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            slug=slug,
            teaching_plan=asdict(teaching_plan),
            storyboard=asdict(storyboard),
            narration=asdict(narration),
            animation=asdict(animation)
        )
        
        self._logger.info("Successfully compiled FinalScriptPayload.")
        return payload

    def generate_markdown(self, payload: FinalScriptPayload) -> str:
        """
        Converts the strict JSON payload into a human-readable Markdown format
        for peer-review or manual editing.
        """
        md = [
            f"# Video Script: {payload.slug}",
            f"**Version:** {payload.version} | **Generated:** {payload.generated_at}",
            "",
            "## 1. Learning Objectives",
            # The structure below parses the previously generated LLM plans
            *[f"- {obj}" for obj in payload.teaching_plan['learning_objectives']],
            "",
            "## 2. Chronological Script",
        ]
        
        for scene in payload.storyboard['scenes']:
            scene_id = scene['scene_id']
            md.append(f"### Scene {scene_id}: {scene['focus_topic']}")
            
            # Link Narration
            narr_block = next((b for b in payload.narration['blocks'] if b['scene_id'] == scene_id), None)
            if narr_block:
                md.append("**🗣️ Narration:**")
                md.append(f"> {narr_block['spoken_text']}")
                md.append("")
                
            # Link Animation
            anim_scene = next((s for s in payload.animation['scenes'] if s['scene_id'] == scene_id), None)
            if anim_scene:
                md.append("**🎬 Visual Actions:**")
                for action in anim_scene['timeline']:
                    md.append(f"- [{action['timestamp_sec']}s] {action['target_object_id']} -> {action['action_type']}")
            
            md.append("\n---\n")
            
        return "\n".join(md)
