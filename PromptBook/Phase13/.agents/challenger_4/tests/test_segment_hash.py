"""
Empirical test harness for SegmentHash cache key determinism and resolution/fps/provider sensitivity.
"""

import sys
import unittest
import hashlib
import json
from typing import Any

# Copy of compute_segment_hash from 01_Media_Production_Architecture.md Section 4.3
def compute_segment_hash(
    provider_id: str,
    section_id: str,
    narration_text: str,
    visual_params: dict[str, Any],
    audio_duration_seconds: float,
    resolution: tuple[int, int] = (1920, 1080),
    fps: int = 60,
) -> str:
    """Computes deterministic SHA-256 SegmentHash for animation caching."""
    visual_params_json = json.dumps(visual_params, sort_keys=True)
    duration_str = f"{audio_duration_seconds:.4f}"
    res_str = f"{resolution[0]}x{resolution[1]}"
    payload = f"{provider_id}:{section_id}:{narration_text}:{visual_params_json}:{duration_str}:{res_str}:{fps}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class TestSegmentHash(unittest.TestCase):

    def test_determinism(self):
        h1 = compute_segment_hash(
            provider_id="manim",
            section_id="sec_01",
            narration_text="Hello world",
            visual_params={"array": [1, 2, 3], "highlight": 2},
            audio_duration_seconds=12.45,
            resolution=(1920, 1080),
            fps=60,
        )
        h2 = compute_segment_hash(
            provider_id="manim",
            section_id="sec_01",
            narration_text="Hello world",
            visual_params={"array": [1, 2, 3], "highlight": 2},
            audio_duration_seconds=12.45,
            resolution=(1920, 1080),
            fps=60,
        )
        self.assertEqual(h1, h2)

    def test_json_key_order_independence(self):
        v1 = {"b": 2, "a": 1, "nested": {"y": 20, "x": 10}}
        v2 = {"a": 1, "b": 2, "nested": {"x": 10, "y": 20}}

        h1 = compute_segment_hash("manim", "sec_01", "Hello", v1, 10.0)
        h2 = compute_segment_hash("manim", "sec_01", "Hello", v2, 10.0)
        self.assertEqual(h1, h2, "JSON key reordering must produce identical hash (sort_keys=True)")

    def test_float_precision_drift_stability(self):
        h1 = compute_segment_hash("manim", "sec_01", "Hello", {}, 12.450000000000001)
        h2 = compute_segment_hash("manim", "sec_01", "Hello", {}, 12.45)
        self.assertEqual(h1, h2, "Float precision drift must be rounded cleanly via f'{duration:.4f}'")

    def test_provider_sensitivity(self):
        h_manim = compute_segment_hash("manim", "sec_01", "Hello", {}, 10.0)
        h_remotion = compute_segment_hash("remotion", "sec_01", "Hello", {}, 10.0)
        self.assertNotEqual(h_manim, h_remotion, "Changing provider must change SegmentHash")

    def test_resolution_sensitivity(self):
        h_1080p = compute_segment_hash("manim", "sec_01", "Hello", {}, 10.0, resolution=(1920, 1080))
        h_4k = compute_segment_hash("manim", "sec_01", "Hello", {}, 10.0, resolution=(3840, 2160))
        self.assertNotEqual(h_1080p, h_4k, "Changing resolution must change SegmentHash")

    def test_fps_sensitivity(self):
        h_60fps = compute_segment_hash("manim", "sec_01", "Hello", {}, 10.0, fps=60)
        h_30fps = compute_segment_hash("manim", "sec_01", "Hello", {}, 10.0, fps=30)
        self.assertNotEqual(h_60fps, h_30fps, "Changing FPS must change SegmentHash")


if __name__ == "__main__":
    unittest.main()
