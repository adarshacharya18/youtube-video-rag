"""
Global pytest fixtures and configuration.

Provides temporary environments, data factories, and test utilities 
across the test suite.
"""

import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, List, Tuple
from unittest.mock import MagicMock

from PIL import Image, ImageChops
import pytest

from src.animation.renderer import ManimRenderer
from src.core.config import PipelineConfig, load_config

# Force testing environment so .env.testing is loaded automatically
os.environ["ENVIRONMENT"] = "testing"


# ==========================================
# 1. Environment & Configuration
# ==========================================

@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Isolated temporary directory for test data generation."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def test_config(temp_data_dir: Path) -> PipelineConfig:
    """
    Returns a deterministic PipelineConfig where all file I/O 
    is safely re-routed to the pytest tmp_path.
    """
    return load_config(overrides={
        "data_dir": temp_data_dir,
        "scraper": {"max_retries": 1},  # Fail fast in tests
        "log_level": "DEBUG"
    })


# ==========================================
# 2. Mock Services & Utilities
# ==========================================

@pytest.fixture
def mock_logger(mocker: Any) -> MagicMock:
    """
    Mocks the structlog logger to prevent terminal spam during tests.
    Uses pytest-mock (mocker).
    """
    return mocker.patch("src.core.logger.get_logger")


# ==========================================
# 3. Data Factories
# ==========================================

@pytest.fixture
def mock_problem_factory() -> Callable[..., dict[str, Any]]:
    """Returns a factory function to generate dummy ScrapedProblem payload dicts."""
    def _create_problem(slug: str = "two-sum", difficulty: str = "Easy") -> dict[str, Any]:
        return {
            "slug": slug,
            "title": slug.replace("-", " ").title(),
            "difficulty": difficulty,
            "tags": ["Array", "Hash Table"],
            "cpp_code": "class Solution { public: vector<int> twoSum() {} };"
        }
    return _create_problem


# ==========================================
# 4. Async Test Runner Compatibility
# ==========================================

import asyncio
import inspect


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Automatically mark async test functions with anyio marker for execution."""
    for item in items:
        if inspect.iscoroutinefunction(getattr(item, "obj", None)) or item.get_closest_marker("asyncio"):
            item.add_marker(pytest.mark.anyio)


# ==========================================
# 5. Video Validation & Rendering Fixtures
# ==========================================

def extract_frames(video_path: Path, output_dir: Path, fps: int = 5) -> List[Path]:
    """Extracts PNG frames from a video file using FFmpeg CLI."""
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_pattern = output_dir / "frame_%03d.png"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps}",
        str(frame_pattern),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    frames = sorted(list(output_dir.glob("frame_*.png")))
    return frames


def compute_frame_motion_delta(img_path1: Path, img_path2: Path) -> float:
    """Computes normalized mean absolute difference (MAD) between two PNG frames."""
    im1 = Image.open(img_path1).convert("L")
    im2 = Image.open(img_path2).convert("L")
    diff = ImageChops.difference(im1, im2)
    diff_bytes = diff.tobytes()
    if not diff_bytes:
        return 0.0
    return float(sum(diff_bytes) / (len(diff_bytes) * 255.0))


def probe_video(video_path: Path) -> Tuple[int, float]:
    """Extracts (nb_frames, duration) from video using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-count_packets",
        "-show_entries",
        "stream=nb_read_packets,nb_frames,duration",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    nb_frames = 0
    duration = 0.0

    if streams:
        s = streams[0]
        frames_str = s.get("nb_read_packets") or s.get("nb_frames") or "0"
        nb_frames = int(frames_str)
        dur_str = s.get("duration") or fmt.get("duration") or "0"
        duration = float(dur_str)
    elif fmt:
        dur_str = fmt.get("duration") or "0"
        duration = float(dur_str)

    return nb_frames, duration


@pytest.fixture
def video_prober() -> Callable[[Path], Tuple[int, float]]:
    """Fixture returning the probe_video callable to extract (nb_frames, duration) via ffprobe."""
    return probe_video


@pytest.fixture
def motion_analyzer() -> Callable[[Path, Path], float]:
    """Fixture returning the compute_frame_motion_delta callable using PIL ImageChops MAD."""
    return compute_frame_motion_delta


@pytest.fixture
def frame_extractor() -> Callable[..., List[Path]]:
    """Fixture returning the extract_frames callable using FFmpeg CLI."""
    return extract_frames


@pytest.fixture
def manim_renderer(tmp_path: Path) -> ManimRenderer:
    """
    Returns a ManimRenderer instance configured with quality="low" and timeout=60.0
    targeting pytest's tmp_path.
    """
    return ManimRenderer(quality="low", timeout=60.0)


@pytest.fixture
def mock_binaries(tmp_path: Path) -> Tuple[str, str]:
    """Global fixture providing mock python scripts for manim and ffmpeg CLI binaries."""
    manim_script = tmp_path / "mock_manim.py"
    manim_script.write_text(
        """import sys, os
media_dir = None
out_arg = "output.mp4"
for i, arg in enumerate(sys.argv):
    if arg == "--media_dir" and i + 1 < len(sys.argv):
        media_dir = sys.argv[i + 1]
    if arg == "-o" and i + 1 < len(sys.argv):
        out_arg = sys.argv[i + 1]
if media_dir:
    os.makedirs(media_dir, exist_ok=True)
    out_file = os.path.join(media_dir, out_arg)
    with open(out_file, "wb") as f:
        f.write(b"MOCK_MANIM_VIDEO_SEGMENT_DATA_" * 10)
sys.exit(0)
""",
        encoding="utf-8",
    )

    ffmpeg_script = tmp_path / "mock_ffmpeg.py"
    ffmpeg_script.write_text(
        """import sys, os
out_file = sys.argv[-1]
os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
with open(out_file, "wb") as f:
    f.write(b"MOCK_ASSEMBLED_4K_VIDEO_STREAM_DATA_" * 10)
sys.exit(0)
""",
        encoding="utf-8",
    )

    return str(manim_script), str(ffmpeg_script)
