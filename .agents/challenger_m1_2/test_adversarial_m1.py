"""Adversarial Verification Script for Milestone 1: AnimationGeneratorNode."""

import json
import os
from pathlib import Path
import shutil
import tempfile
import sys

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.core.exceptions import AnimationError, PipelineStageError
from src.core.models.assets import RenderSegment
from src.core.orchestrator.state_ledger import StateLedger
from src.pipeline.nodes.animation_generator_node import (
    AnimationGeneratorNode,
    ANIMATION_TYPE_MAP,
    DEFAULT_SCENE,
)

def run_tests():
    results = {}
    
    # -------------------------------------------------------------
    # Test 1: Visual Cue Mapping Variants
    # -------------------------------------------------------------
    test_types = [
        "array_highlight",
        "tree_traversal",
        "code_highlight",
        "graph_animation",
        "hashmap_operation",
        "linkedlist_operation",
        "stack_queue_operation",
        "complexity_chart",
        "unknown_type",
    ]
    
    mapping_results = {}
    for anim_type in test_types:
        mapped = ANIMATION_TYPE_MAP.get(anim_type, DEFAULT_SCENE)
        mapping_results[anim_type] = mapped
        print(f"Mapping for '{anim_type}': {mapped}")
    
    # Check if linkedlist_operation is mapped correctly to LinkedListScene
    linkedlist_op_mapped = mapping_results.get("linkedlist_operation")
    if linkedlist_op_mapped and "linkedlist_scene.py" in linkedlist_op_mapped[0]:
        results["linkedlist_operation_mapping"] = "PASS"
    else:
        results["linkedlist_operation_mapping"] = f"FAIL (Got {linkedlist_op_mapped}, expected linkedlist_scene.py)"

    # -------------------------------------------------------------
    # Test 2: Full Node Execution & Payload Validation
    # -------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "ledger.db"
        ledger = StateLedger(db_path=db_path)
        run_id = ledger.create_run(slug="test-slug")
        
        # Create mock manim script
        mock_manim = tmp_path / "mock_manim.py"
        mock_manim.write_text(
            "import sys, os\n"
            "media_dir = None\n"
            "for i, arg in enumerate(sys.argv):\n"
            "    if arg == '--media_dir' and i+1 < len(sys.argv):\n"
            "        media_dir = sys.argv[i+1]\n"
            "if media_dir:\n"
            "    os.makedirs(media_dir, exist_ok=True)\n"
            "    with open(os.path.join(media_dir, 'out.mp4'), 'wb') as f:\n"
            "        f.write(b'MOCK_MP4_DATA')\n"
            "sys.exit(0)\n"
        )
        
        cues_to_test = [
            {"cue_id": "cue_array", "animation_type": "array_highlight", "description": "desc", "timestamp_seconds": 0.0, "parameters": {"duration": 4.0}},
            {"cue_id": "cue_tree", "animation_type": "tree_traversal", "description": "desc", "timestamp_seconds": 4.0, "parameters": {"duration": 5.0}},
            {"cue_id": "cue_code", "animation_type": "code_highlight", "description": "desc", "timestamp_seconds": 9.0, "parameters": {"duration": 3.0}},
            {"cue_id": "cue_graph", "animation_type": "graph_animation", "description": "desc", "timestamp_seconds": 12.0, "parameters": {"duration": 4.0}},
            {"cue_id": "cue_hashmap", "animation_type": "hashmap_operation", "description": "desc", "timestamp_seconds": 16.0, "parameters": {"duration": 2.0}},
            {"cue_id": "cue_ll", "animation_type": "linkedlist_operation", "description": "desc", "timestamp_seconds": 18.0, "parameters": {"duration": 5.0}},
            {"cue_id": "cue_sq", "animation_type": "stack_queue_operation", "description": "desc", "timestamp_seconds": 23.0, "parameters": {"duration": 3.0}},
            {"cue_id": "cue_comp", "animation_type": "complexity_chart", "description": "desc", "timestamp_seconds": 26.0, "parameters": {"duration": 4.0}},
            {"cue_id": "cue_unk", "animation_type": "unknown_type", "description": "desc", "timestamp_seconds": 30.0, "parameters": {"duration": 5.0}},
        ]
        
        script_payload = {
            "slug": "test-slug",
            "script": {
                "topic": "Test Topic",
                "slug": "test-slug",
                "difficulty": "Easy",
                "total_duration": 35.0,
                "hook": {"title": "Hook", "narration": "Hook narration", "estimated_duration": 4.0, "visual_cues": [cues_to_test[0]]},
                "context": {"title": "Context", "narration": "Context narration", "estimated_duration": 5.0, "visual_cues": [cues_to_test[1]]},
                "solution": {"title": "Solution", "narration": "Solution narration", "estimated_duration": 21.0, "visual_cues": cues_to_test[2:7]},
                "complexity": {"title": "Complexity", "narration": "Complexity narration", "estimated_duration": 5.0, "visual_cues": cues_to_test[7:]},
            }
        }
        
        step_id = ledger.record_step_start(run_id, step_name="script_generator")
        ledger.record_step_completion(step_id, output_payload=script_payload)
        
        node = AnimationGeneratorNode(
            manim_binary=str(mock_manim),
            quality="medium",
            output_dir=tmp_path / "renders",
            cache_dir=tmp_path / "cache",
        )
        
        exec_output = node.execute(run_id=run_id, ledger=ledger)
        
        # Validate payload format
        segments = exec_output.get("segments", [])
        validated_segments = []
        validation_failed = False
        
        for seg_dict in segments:
            try:
                validated_seg = RenderSegment.model_validate(seg_dict)
                validated_segments.append(validated_seg)
            except Exception as e:
                print(f"Validation error for segment {seg_dict.get('segment_id')}: {e}")
                validation_failed = True
        
        if len(segments) == len(cues_to_test) and not validation_failed:
            results["payload_validation"] = "PASS"
        else:
            results["payload_validation"] = f"FAIL (Validated {len(validated_segments)}/{len(cues_to_test)})"

        # -------------------------------------------------------------
        # Test 3: SHA-256 Caching Verification (Hit & Miss)
        # -------------------------------------------------------------
        # Check cache directory contains generated cached files
        cache_files = list((tmp_path / "cache").glob("*.mp4"))
        print(f"Cache file count: {len(cache_files)}")
        
        # Test Cache Hit: Run again with broken binary
        run_id_2 = ledger.create_run(slug="test-slug")
        step_id_2 = ledger.record_step_start(run_id_2, step_name="script_generator")
        ledger.record_step_completion(step_id_2, output_payload=script_payload)

        broken_node = AnimationGeneratorNode(
            manim_binary="/nonexistent/binary",
            quality="medium",
            output_dir=tmp_path / "renders_hit",
            cache_dir=tmp_path / "cache",
        )
        
        try:
            hit_output = broken_node.execute(run_id=run_id_2, ledger=ledger)
            if hit_output.get("render_count") == len(cues_to_test):
                results["caching_hit_miss"] = "PASS"
            else:
                results["caching_hit_miss"] = "FAIL (Render count mismatch on cache hit)"
        except Exception as e:
            results["caching_hit_miss"] = f"FAIL (Raised exception on cache hit: {e})"
            
        # Test Cache Hash Determinism (Parameter Order Insensitivity)
        hash1 = node._compute_cache_hash("array_highlight", {"a": 1, "b": 2})
        hash2 = node._compute_cache_hash("array_highlight", {"b": 2, "a": 1})
        if hash1 == hash2:
            results["cache_hash_determinism"] = "PASS"
        else:
            results["cache_hash_determinism"] = f"FAIL ({hash1} != {hash2})"

        # -------------------------------------------------------------
        # Test 4: Temp Dir Cleanup on Success and Failure
        # -------------------------------------------------------------
        temp_parent = tmp_path / "custom_temp"
        temp_parent.mkdir()
        
        # Success cleanup test
        clean_node = AnimationGeneratorNode(
            manim_binary=str(mock_manim),
            quality="medium",
            output_dir=tmp_path / "renders_clean",
            cache_dir=tmp_path / "cache_clean",
            temp_dir=temp_parent,
        )
        clean_node.execute(run_id=run_id, ledger=ledger)
        leftovers_success = list(temp_parent.iterdir())
        
        # Failure cleanup test
        fail_manim = tmp_path / "fail_manim.py"
        fail_manim.write_text("import sys\nsys.stderr.write('Fail')\nsys.exit(1)\n")
        
        fail_node = AnimationGeneratorNode(
            manim_binary=str(fail_manim),
            quality="medium",
            output_dir=tmp_path / "renders_fail",
            cache_dir=tmp_path / "cache_fail",
            temp_dir=temp_parent,
        )
        
        # Reset script generator output with uncached cues
        fail_run_id = ledger.create_run(slug="fail-slug")
        fail_script_payload = {
            "slug": "fail-slug",
            "script": {
                "visual_cues": [
                    {"cue_id": "cue_fail", "animation_type": "array_highlight", "description": "desc", "timestamp_seconds": 0.0, "parameters": {"fail": True, "dur": 1}}
                ]
            }
        }
        fail_step_id = ledger.record_step_start(fail_run_id, step_name="script_generator")
        ledger.record_step_completion(fail_step_id, output_payload=fail_script_payload)
        
        try:
            fail_node.execute(run_id=fail_run_id, ledger=ledger)
        except AnimationError:
            pass # Expected
            
        leftovers_fail = list(temp_parent.iterdir())
        
        if len(leftovers_success) == 0 and len(leftovers_fail) == 0:
            results["tempdir_cleanup"] = "PASS"
        else:
            results["tempdir_cleanup"] = f"FAIL (Leftovers: success={len(leftovers_success)}, fail={len(leftovers_fail)})"

    print("\n=== SUMMARY OF VERIFICATION RESULTS ===")
    for k, v in results.items():
        print(f"  - {k}: {v}")
        
    return results

if __name__ == "__main__":
    run_tests()
