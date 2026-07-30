"""Empirical Verification Script for Challenger 2 (Milestone 1 Iteration 2)."""

import json
import os
from pathlib import Path
import shutil
import tempfile
import sys

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
from src.animation.scenes.base_scene import BaseDSAScene
from src.animation.renderer import ManimRenderer

def test_visual_cue_mapping():
    print("--- Testing Visual Cue Mapping ---")
    linkedlist_op = ANIMATION_TYPE_MAP.get("linkedlist_operation")
    assert linkedlist_op is not None, "linkedlist_operation key missing from ANIMATION_TYPE_MAP"
    assert linkedlist_op[1] == "LinkedListScene", f"Expected LinkedListScene, got {linkedlist_op[1]}"
    assert "linkedlist_scene.py" in linkedlist_op[0], f"Expected linkedlist_scene.py in path, got {linkedlist_op[0]}"
    
    # Check other linked list keys
    for key in ["linkedlist_pointer", "linked_list", "linkedlist", "linkedlist_operation"]:
        mapping = ANIMATION_TYPE_MAP.get(key)
        assert mapping == ("src/animation/scenes/linkedlist_scene.py", "LinkedListScene"), f"Key {key} mapped incorrectly: {mapping}"
    
    print("Visual cue mapping test PASSED.")

def test_fallback_visual_cue_extraction():
    print("--- Testing Fallback Visual Cue Extraction ---")
    node = AnimationGeneratorNode()
    
    # Scenario A: Payload fails YouTubeScript Pydantic validation and has section-nested visual cues
    malformed_script_payload = {
        "slug": "malformed-slug",
        "script": {
            "topic": "Malformed Test",
            "slug": "malformed-slug",
            # Invalid fields / missing duration/difficulty so model_validate fails
            "hook": {
                "title": "Hook Title",
                "visual_cues": [
                    {"cue_id": "cue_hook_1", "animation_type": "array_highlight", "parameters": {"duration": 3.0}}
                ]
            },
            "context": {
                "title": "Context Title",
                "visual_cues": [
                    {"cue_id": "cue_ctx_1", "animation_type": "linkedlist_operation", "parameters": {"duration": 4.0}}
                ]
            },
            "solution": {
                "title": "Solution Title",
                "visual_cues": [
                    {"cue_id": "cue_sol_1", "animation_type": "tree_traversal", "parameters": {"duration": 5.0}},
                    {"cue_id": "cue_sol_2", "animation_type": "code_highlight", "parameters": {"duration": 2.0}}
                ]
            },
            "complexity": {
                "title": "Complexity Title",
                "visual_cues": [
                    {"cue_id": "cue_comp_1", "animation_type": "complexity_chart", "parameters": {"duration": 3.0}}
                ]
            }
        }
    }
    
    extracted = node._extract_visual_cues(malformed_script_payload)
    assert len(extracted) == 5, f"Expected 5 cues extracted from section dicts, got {len(extracted)}"
    extracted_ids = [c["cue_id"] for c in extracted]
    expected_ids = ["cue_hook_1", "cue_ctx_1", "cue_sol_1", "cue_sol_2", "cue_comp_1"]
    assert extracted_ids == expected_ids, f"Extracted cue IDs mismatch: {extracted_ids} vs {expected_ids}"
    
    print("Fallback visual cue extraction test PASSED.")

def test_parameter_json_loading_in_base_dsa_scene():
    print("--- Testing Parameter JSON Loading in BaseDSAScene ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        old_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            
            # Write a sample parameters.json
            params_file = tmp_path / "parameters.json"
            sample_params = {
                "title": "Linked List Inversion",
                "nodes": [1, 2, 3, 4],
                "highlight_index": 2
            }
            params_file.write_text(json.dumps(sample_params, indent=2))
            
            # Instantiate BaseDSAScene
            scene = BaseDSAScene()
            assert scene.params == sample_params, f"BaseDSAScene failed to auto-load params from parameters.json: {scene.params}"
            
            # Test explicit path load
            custom_file = tmp_path / "custom_params.json"
            custom_params = {"title": "Custom Test", "data": [9, 8]}
            custom_file.write_text(json.dumps(custom_params, indent=2))
            
            loaded = scene.load_params_from_json(str(custom_file))
            assert loaded == custom_params, f"load_params_from_json failed for explicit path: {loaded}"
            assert scene.params == custom_params
        finally:
            os.chdir(old_cwd)
            
    print("Parameter JSON loading in BaseDSAScene test PASSED.")

def test_manim_renderer_and_fake_bytes_absence():
    print("--- Testing ManimRenderer and Absence of Fake MP4 Bytes ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Script that exits non-zero without creating file
        failing_script = tmp_path / "failing_manim.py"
        failing_script.write_text("import sys\nsys.stderr.write('Render crash')\nsys.exit(1)\n")
        
        renderer = ManimRenderer(manim_binary=str(failing_script))
        scene_script = repo_root / "src" / "animation" / "scenes" / "array_scene.py"
        
        # Should raise AnimationError
        raised = False
        try:
            renderer.render(
                scene_script=scene_script,
                class_name="ArrayScene",
                output_dir=tmp_path / "out",
                output_filename="fail.mp4",
                parameters={"test": True}
            )
        except AnimationError as e:
            raised = True
            assert "Render crash" in str(e) or "exit code 1" in str(e)
            
        assert raised, "Expected AnimationError on subprocess exit code 1, but none raised"
        
        # Verify no fake mp4 file was written in output dir
        output_file = tmp_path / "out" / "fail.mp4"
        assert not output_file.exists(), "Output mp4 file exists after failed render!"
        
        # Test script that exits 0 but creates NO mp4 file
        nop_script = tmp_path / "nop_manim.py"
        nop_script.write_text("import sys\nsys.exit(0)\n")
        
        renderer_nop = ManimRenderer(manim_binary=str(nop_script))
        raised_nop = False
        try:
            renderer_nop.render(
                scene_script=scene_script,
                class_name="ArrayScene",
                output_dir=tmp_path / "out_nop",
                output_filename="nop.mp4",
                parameters={"test": True}
            )
        except AnimationError as e:
            raised_nop = True
            assert "produced no valid video artifact" in str(e)
            
        assert raised_nop, "Expected AnimationError when 0 exit code produces no file, but none raised"
        assert not (tmp_path / "out_nop" / "nop.mp4").exists(), "Fake mp4 file was written!"

    print("ManimRenderer and fake bytes absence test PASSED.")

def test_partial_output_cleanup_on_midway_failure():
    print("--- Testing Partial Output Cleanup on Midway Failure ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "ledger.db"
        ledger = StateLedger(db_path=db_path)
        run_id = ledger.create_run(slug="partial-fail-slug")
        
        # Mock manim that succeeds for cue 0, but fails for cue 1
        script_file = tmp_path / "conditional_manim.py"
        script_file.write_text(
            "import sys, os\n"
            "media_dir = None\n"
            "out_name = 'out.mp4'\n"
            "for i, arg in enumerate(sys.argv):\n"
            "    if arg == '--media_dir' and i+1 < len(sys.argv):\n"
            "        media_dir = sys.argv[i+1]\n"
            "    if arg == '-o' and i+1 < len(sys.argv):\n"
            "        out_name = sys.argv[i+1]\n"
            "if 'cue_fail' in out_name:\n"
            "    sys.stderr.write('Intentional cue failure')\n"
            "    sys.exit(1)\n"
            "if media_dir:\n"
            "    os.makedirs(media_dir, exist_ok=True)\n"
            "    with open(os.path.join(media_dir, out_name), 'wb') as f:\n"
            "        f.write(b'VALID_MP4_DATA_MOCK')\n"
            "sys.exit(0)\n"
        )
        
        cues = [
            {"cue_id": "cue_success", "animation_type": "array_highlight", "parameters": {"duration": 3.0}},
            {"cue_id": "cue_fail", "animation_type": "linkedlist_operation", "parameters": {"duration": 4.0}}
        ]
        
        payload = {
            "slug": "partial-fail-slug",
            "script": {
                "visual_cues": cues
            }
        }
        
        step_id = ledger.record_step_start(run_id, step_name="script_generator")
        ledger.record_step_completion(step_id, output_payload=payload)
        
        out_dir = tmp_path / "renders"
        node = AnimationGeneratorNode(
            manim_binary=str(script_file),
            output_dir=out_dir,
            cache_dir=tmp_path / "cache"
        )
        
        try:
            node.execute(run_id=run_id, ledger=ledger)
            assert False, "Expected AnimationError during execution, but node succeeded"
        except AnimationError:
            pass
            
        run_out_dir = out_dir / run_id
        # Verify cue_success segment file was deleted by cleanup logic in node.execute
        success_file = run_out_dir / "segment_cue_success.mp4"
        assert not success_file.exists(), f"Partial output file {success_file} was NOT cleaned up on midway failure!"
        assert not run_out_dir.exists(), f"Empty run output directory {run_out_dir} was NOT removed after cleanup!"

    print("Partial output cleanup test PASSED.")

def main():
    test_visual_cue_mapping()
    test_fallback_visual_cue_extraction()
    test_parameter_json_loading_in_base_dsa_scene()
    test_manim_renderer_and_fake_bytes_absence()
    test_partial_output_cleanup_on_midway_failure()
    print("\nALL EMPIRICAL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
