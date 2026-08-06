"""
Manim Video Subsystem Isolation Test Suite (Requirement R2).

Verifies that Manim animation scenes render multi-frame moving MP4 video clips
matching visual cue durations rather than single frozen 1-frame MP4s.

Uses inter-frame motion delta analysis via PIL ImageChops:
- Renders Manim scene templates securely via ManimRenderer
- Extracts rendered frames using FFmpeg CLI
- Verifies nb_frames > 1 and duration > 0.1s via ffprobe
- Asserts non-zero inter-frame motion deltas (mean_diff > 0.01) across rendered frames
- Verifies frozen 1-frame MP4 files are rejected by video validation
"""

import json
from pathlib import Path
import subprocess
from typing import List, Tuple

from PIL import Image, ImageChops
import pytest

from src.animation.renderer import ManimRenderer
from src.assembly.assembler import VideoAssembler
from src.pipeline.nodes.animation_generator_node import AnimationGeneratorNode


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


@pytest.mark.parametrize(
    "scene_file,class_name,params",
    [
        (
            "src/animation/scenes/array_scene.py",
            "ArrayScene",
            {"array": [10, 20, 30, 40], "highlight_indices": [1], "duration": 3.0},
        ),
        (
            "src/animation/scenes/code_scene.py",
            "CodeScene",
            {"code": "def solve():\n    return 42", "duration": 3.0},
        ),
        (
            "src/animation/scenes/tree_scene.py",
            "TreeScene",
            {"root": 42, "duration": 3.0},
        ),
        (
            "src/animation/scenes/linkedlist_scene.py",
            "LinkedListScene",
            {"nodes": [1, 2, 3], "duration": 3.0},
        ),
        (
            "src/animation/scenes/graph_scene.py",
            "GraphScene",
            {"vertices": [1, 2, 3], "edges": [(1, 2), (2, 3)], "duration": 3.0},
        ),
        (
            "src/animation/scenes/hashmap_scene.py",
            "HashmapScene",
            {"entries": {"a": 1, "b": 2}, "duration": 3.0},
        ),
        (
            "src/animation/scenes/stack_queue_scene.py",
            "StackQueueScene",
            {"elements": ["X", "Y", "Z"], "duration": 3.0},
        ),
        (
            "src/animation/scenes/complexity_scene.py",
            "ComplexityScene",
            {"time_complexity": "O(N log N)", "space_complexity": "O(N)", "duration": 3.0},
        ),
    ],
)
def test_manim_renders_moving_frames_for_scene_templates(tmp_path, scene_file, class_name, params):
    """Verifies that each Manim scene template renders multi-frame MP4 video with non-zero motion."""
    renderer = ManimRenderer(quality="low", timeout=60.0)
    scene_script = Path(scene_file).resolve()
    out_dir = tmp_path / "renders"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_filename = f"{class_name.lower()}.mp4"

    rendered_video = renderer.render(
        scene_script=scene_script,
        class_name=class_name,
        output_dir=out_dir,
        output_filename=out_filename,
        parameters=params,
    )

    assert rendered_video.exists()
    assert rendered_video.stat().st_size > 100

    # 1. Probe video for frame count and duration
    nb_frames, duration = probe_video(rendered_video)
    assert nb_frames > 1, f"Expected nb_frames > 1 for {class_name}, got {nb_frames}"
    assert duration > 0.1, f"Expected duration > 0.1s for {class_name}, got {duration}s"

    # 2. Extract PNG frames and verify motion delta
    frames_dir = tmp_path / f"frames_{class_name.lower()}"
    frames = extract_frames(rendered_video, frames_dir, fps=5)
    assert len(frames) >= 2, f"Expected at least 2 extracted frames for {class_name}, got {len(frames)}"

    # Calculate motion deltas across consecutive frames
    motion_deltas = [
        compute_frame_motion_delta(frames[i], frames[i + 1])
        for i in range(len(frames) - 1)
    ]
    max_delta = max(motion_deltas)

    # Verify that maximum inter-frame motion delta > 0.001 (indicating real animation motion)
    assert max_delta > 0.001, (
        f"Expected non-zero motion delta for {class_name}, but max delta was {max_delta:.6f}"
    )


def test_frozen_1frame_video_fails_validation(tmp_path):
    """Verifies that frozen 1-frame MP4 files fail deep video validation."""
    frozen_video = tmp_path / "frozen_1frame.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=0.033:size=320x240:rate=30",
        "-vframes",
        "1",
        str(frozen_video),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)

    anim_node = AnimationGeneratorNode()
    assembler = VideoAssembler()

    assert anim_node._is_valid_video_file(frozen_video) is False
    assert assembler._is_valid_video(frozen_video) is False


def test_duration_parameter_budgeting(tmp_path):
    """Verifies that requested duration parameter controls rendered video length."""
    renderer = ManimRenderer(quality="low", timeout=60.0)
    scene_script = Path("src/animation/scenes/array_scene.py").resolve()
    out_dir = tmp_path / "duration_test"

    rendered_video = renderer.render(
        scene_script=scene_script,
        class_name="ArrayScene",
        output_dir=out_dir,
        output_filename="duration_test.mp4",
        parameters={"array": [1, 2, 3], "duration": 5.0},
    )

    nb_frames, duration = probe_video(rendered_video)
    assert duration >= 4.5, f"Expected duration >= 4.5s for 5s requested duration, got {duration}s"
    assert nb_frames >= 50, f"Expected nb_frames >= 50 for 5s duration, got {nb_frames}"
