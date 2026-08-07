"""
Unit tests for shared global pytest fixtures defined in tests/conftest.py.
Verifies fixture loading, return types, callability, and proper execution.
"""

from pathlib import Path
from typing import Callable, List, Tuple
from src.animation.renderer import ManimRenderer


def test_video_prober_fixture(video_prober: Callable[[Path], Tuple[int, float]]):
    """Verifies that video_prober fixture exposes probe_video callable."""
    assert callable(video_prober)


def test_motion_analyzer_fixture(motion_analyzer: Callable[[Path, Path], float]):
    """Verifies that motion_analyzer fixture exposes compute_frame_motion_delta callable."""
    assert callable(motion_analyzer)


def test_frame_extractor_fixture(frame_extractor: Callable[..., List[Path]]):
    """Verifies that frame_extractor fixture exposes extract_frames callable."""
    assert callable(frame_extractor)


def test_manim_renderer_fixture(manim_renderer: ManimRenderer):
    """Verifies that manim_renderer fixture returns a low-quality ManimRenderer instance with timeout=60.0."""
    assert isinstance(manim_renderer, ManimRenderer)
    assert manim_renderer.quality == "low"
    assert manim_renderer.timeout == 60.0


def test_mock_binaries_fixture(mock_binaries: Tuple[str, str]):
    """Verifies that mock_binaries fixture generates executable mock scripts for manim and ffmpeg."""
    manim_bin, ffmpeg_bin = mock_binaries
    assert Path(manim_bin).exists()
    assert Path(ffmpeg_bin).exists()
    assert "mock_manim.py" in manim_bin
    assert "mock_ffmpeg.py" in ffmpeg_bin
