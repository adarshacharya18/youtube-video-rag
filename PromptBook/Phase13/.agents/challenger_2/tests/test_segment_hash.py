"""
Empirical test suite for Challenge Focus 3: Segment-Level Checkpointing & SegmentHash Non-Determinism
"""
import sys
import unittest
import hashlib
import json
from typing import Any

# SegmentHash formula from Section 4.3:
# SegmentHash = SHA256(section_id + narration_text + visual_params_json + audio_duration_seconds + manim_theme_version)

def compute_spec_segment_hash(
    section_id: str,
    narration_text: str,
    visual_params: dict[str, Any],
    audio_duration_seconds: float,
    manim_theme_version: str = "v1.0"
) -> str:
    # Spec does not enforce sort_keys=True on json.dumps or fixed float formatting on audio_duration_seconds
    visual_params_json = json.dumps(visual_params)
    raw = f"{section_id}{narration_text}{visual_params_json}{audio_duration_seconds}{manim_theme_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TestSegmentHashEdgeCases(unittest.TestCase):

    def test_json_key_order_nondeterminism_invalidates_cache(self):
        """
        EMPIRICAL BUG PROOF:
        If `visual_params_json` is produced via `json.dumps(visual_params)` without `sort_keys=True`,
        dictionaries with identical key-value pairs but different insertion order produce DIFFERENT SegmentHashes!
        This causes unnecessary cache misses and full re-renders of identical scenes.
        """
        dict_a = {"array": [2, 7, 11], "target": 9, "color": "#FF0000"}
        dict_b = {"color": "#FF0000", "target": 9, "array": [2, 7, 11]}

        hash_a = compute_spec_segment_hash("sec_01", "Hook text", dict_a, 12.45)
        hash_b = compute_spec_segment_hash("sec_01", "Hook text", dict_b, 12.45)

        self.assertNotEqual(hash_a, hash_b, "BUG PROVEN: Key order difference invalidates cache without sort_keys=True!")

    def test_float_precision_drift_invalidates_cache(self):
        """
        EMPIRICAL BUG PROOF:
        Audio duration floats (e.g. 12.450000000000001 vs 12.45) produced by TTS timing manifests across runs/platforms
        produce DIFFERENT SegmentHashes when formatted via raw str(float).
        """
        hash_exact = compute_spec_segment_hash("sec_01", "Hook text", {"a": 1}, 12.45)
        hash_drift = compute_spec_segment_hash("sec_01", "Hook text", {"a": 1}, 12.450000000000002)

        self.assertNotEqual(hash_exact, hash_drift, "BUG PROVEN: Minor float precision drift invalidates SegmentHash!")

    def test_missing_provider_and_resolution_in_segment_hash(self):
        """
        EMPIRICAL BUG PROOF:
        SegmentHash formula DOES NOT include resolution, fps, or provider_id.
        If a developer swaps provider from Manim (1080p60) to Remotion (4K30) in media_production.yaml,
        the SegmentHash will match the old Manim 1080p60 MP4 and return a FALSE CACHE HIT!
        """
        # SegmentHash computation does not include resolution or provider
        hash_1080p_manim = compute_spec_segment_hash("sec_01", "Hook text", {"a": 1}, 12.45)
        
        # Suppose configuration changed to 4K Remotion render
        hash_4k_remotion = compute_spec_segment_hash("sec_01", "Hook text", {"a": 1}, 12.45)

        self.assertEqual(hash_1080p_manim, hash_4k_remotion,
                         "BUG PROVEN: SegmentHash returns FALSE POSITIVE CACHE HIT when resolution or provider changes!")


if __name__ == "__main__":
    unittest.main()
