"""Empirical Stress Test Harness for Animation Generator Node, Caching, and Cue Mapping."""

import json
import hashlib
from pathlib import Path
import pytest

from src.pipeline.nodes.animation_generator_node import (
    AnimationGeneratorNode,
    ANIMATION_TYPE_MAP,
    DEFAULT_SCENE,
)
from src.core.orchestrator.state_ledger import StateLedger
from src.core.exceptions import AnimationError, PipelineStageError


def test_cue_mapping_case_and_all_types():
    print("--- 1. Testing Cue Mapping ---")
    # Test all mapped types in ANIMATION_TYPE_MAP
    missing_scene_files = []
    missing_classes = []

    for anim_type, (rel_path, class_name) in ANIMATION_TYPE_MAP.items():
        p = Path(rel_path)
        if not p.exists():
            missing_scene_files.append((anim_type, rel_path))
        else:
            code = p.read_text(encoding="utf-8")
            if f"class {class_name}" not in code:
                missing_classes.append((anim_type, rel_path, class_name))

    print(f"Total mapped types: {len(ANIMATION_TYPE_MAP)}")
    print(f"Missing scene files: {missing_scene_files}")
    print(f"Missing classes in files: {missing_classes}")

    # Case sensitivity check
    uppercase_type = "ARRAY_HIGHLIGHT"
    mapped_upper = ANIMATION_TYPE_MAP.get(uppercase_type)
    print(f"Lookup for '{uppercase_type}': {mapped_upper} (Default fallback: {mapped_upper is None})")

    mixed_type = "Array_Highlight"
    mapped_mixed = ANIMATION_TYPE_MAP.get(mixed_type)
    print(f"Lookup for '{mixed_type}': {mapped_mixed} (Default fallback: {mapped_mixed is None})")

    return len(missing_scene_files) == 0 and len(missing_classes) == 0


def test_cache_invalidation_and_hashing():
    print("\n--- 2. Testing Cache Key Generation & Invalidation ---")
    node = AnimationGeneratorNode(quality="medium")

    # Hash 1
    h1 = node._compute_cache_hash("array_highlight", {"array": [1, 2, 3], "target": 5})
    # Hash 2 (different key order)
    h2 = node._compute_cache_hash("array_highlight", {"target": 5, "array": [1, 2, 3]})
    print(f"Sort keys verification (h1 == h2): {h1 == h2} (h1={h1[:8]}, h2={h2[:8]})")

    # Hash 3 (parameter change)
    h3 = node._compute_cache_hash("array_highlight", {"array": [1, 2, 4], "target": 5})
    print(f"Parameter change invalidates cache (h1 != h3): {h1 != h3}")

    # Hash 4 (type change float vs int)
    h4 = node._compute_cache_hash("array_highlight", {"array": [1, 2, 3], "target": 5.0})
    print(f"Float vs int parameter change (h1 != h4): {h1 != h4} (h1={h1[:8]}, h4={h4[:8]})")

    # Hash 5 (quality change)
    node_low = AnimationGeneratorNode(quality="low")
    h5 = node_low._compute_cache_hash("array_highlight", {"array": [1, 2, 3], "target": 5})
    print(f"Quality change invalidates cache (h1 != h5): {h1 != h5}")

    # Hash 6 (anim_type casing change)
    h6 = node._compute_cache_hash("ARRAY_HIGHLIGHT", {"array": [1, 2, 3], "target": 5})
    print(f"Casing change in anim_type produces different hash (h1 != h6): {h1 != h6}")


def test_fallback_cue_extraction():
    print("\n--- 3. Testing Fallback Cue Extraction Logic ---")
    node = AnimationGeneratorNode()

    # Test Case 3A: Model validation succeeds
    payload_valid = {
        "script": {
            "topic": "Test Topic",
            "slug": "test-slug",
            "difficulty": "Easy",
            "total_duration": 20.0,
            "hook": {"narration": "Hook narration", "estimated_duration": 5.0, "visual_cues": [{"cue_id": "c1", "animation_type": "array_highlight", "description": "d1"}]},
            "context": {"narration": "Ctx narration", "estimated_duration": 5.0, "visual_cues": [{"cue_id": "c2", "animation_type": "tree_traversal", "description": "d2"}]},
            "solution": {"narration": "Sol narration", "estimated_duration": 5.0, "visual_cues": [{"cue_id": "c3", "animation_type": "code_highlight", "description": "d3"}]},
            "complexity": {"narration": "Comp narration", "estimated_duration": 5.0, "visual_cues": [{"cue_id": "c4", "animation_type": "complexity_chart", "description": "d4"}]},
        }
    }
    cues_valid = node._extract_visual_cues(payload_valid)
    print(f"Valid YouTubeScript extraction count: {len(cues_valid)}")

    # Test Case 3B: Model validation FAILS (invalid total_duration type), but has top-level visual_cues
    payload_invalid_model_with_top_cues = {
        "script": {
            "topic": "Test Topic",
            "slug": "test-slug",
            "total_duration": "INVALID_DURATION",
            "visual_cues": [
                {"cue_id": "c_top_1", "animation_type": "array_highlight", "description": "top 1"},
            ],
            "hook": {"narration": "Hook narration", "estimated_duration": 5.0, "visual_cues": [{"cue_id": "c_sec_1", "animation_type": "array_highlight", "description": "sec 1"}]},
            "context": {"narration": "Ctx narration", "estimated_duration": 5.0, "visual_cues": [{"cue_id": "c_sec_2", "animation_type": "tree_traversal", "description": "sec 2"}]},
            "solution": {"narration": "Sol narration", "estimated_duration": 5.0, "visual_cues": []},
            "complexity": {"narration": "Comp narration", "estimated_duration": 5.0, "visual_cues": []},
        }
    }
    cues_fallback_top = node._extract_visual_cues(payload_invalid_model_with_top_cues)
    print(f"Fallback with top-level cues count: {len(cues_fallback_top)}, cue_ids: {[c['cue_id'] for c in cues_fallback_top]}")

    # Test Case 3C: Model validation FAILS, NO top-level visual_cues, has section visual_cues
    payload_invalid_model_sec_cues = {
        "script": {
            "topic": "Test Topic",
            "slug": "test-slug",
            "total_duration": "INVALID_DURATION",
            "hook": {"narration": "Hook narration", "estimated_duration": 5.0, "visual_cues": [{"cue_id": "c_sec_1", "animation_type": "array_highlight", "description": "sec 1"}]},
            "context": {"narration": "Ctx narration", "estimated_duration": 5.0, "visual_cues": [{"cue_id": "c_sec_2", "animation_type": "tree_traversal", "description": "sec 2"}]},
            "solution": {"narration": "Sol narration", "estimated_duration": 5.0, "visual_cues": []},
            "complexity": {"narration": "Comp narration", "estimated_duration": 5.0, "visual_cues": [{"cue_id": "c_sec_4", "animation_type": "complexity_chart", "description": "sec 4"}]},
        }
    }
    cues_fallback_sec = node._extract_visual_cues(payload_invalid_model_sec_cues)
    print(f"Fallback with section cues count: {len(cues_fallback_sec)}, cue_ids: {[c['cue_id'] for c in cues_fallback_sec]}")

    # Test Case 3D: Payload is not wrapped in "script", directly has "visual_cues"
    payload_direct = {
        "slug": "direct-test",
        "visual_cues": [
            {"cue_id": "c_dir_1", "animation_type": "linkedlist_operation", "description": "direct 1"}
        ]
    }
    cues_direct = node._extract_visual_cues(payload_direct)
    print(f"Direct payload extraction count: {len(cues_direct)}, cue_ids: {[c['cue_id'] for c in cues_direct]}")

    # Test Case 3E: Payload script object is already a YouTubeScript model instance
    from src.models.script import YouTubeScript
    yt_model = YouTubeScript.model_validate(payload_valid["script"])
    payload_model_obj = {"script": yt_model}
    cues_model_obj = node._extract_visual_cues(payload_model_obj)
    print(f"Model instance payload extraction count: {len(cues_model_obj)}")


if __name__ == "__main__":
    test_cue_mapping_case_and_all_types()
    test_cache_invalidation_and_hashing()
    test_fallback_cue_extraction()
