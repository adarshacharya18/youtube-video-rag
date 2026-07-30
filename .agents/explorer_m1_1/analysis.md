# Technical Specification & Design Analysis: FFmpeg Command Generator (`src/assembly/ffmpeg_commands.py`)

## Executive Summary

This document presents the detailed design specification and exact implementation logic for `src/assembly/ffmpeg_commands.py`. As part of Phase 13 (Media Production: Video Assembly), this module provides a set of pure helper functions that construct FFmpeg Command Line Interface (CLI) argument arrays (`List[str]`) for 4K video rendering, multi-segment video/audio concatenation, audio resampling, and hard-coded (burned-in) subtitle overlay.

By maintaining strict separation of concerns, `src/assembly/ffmpeg_commands.py` contains **zero side effects** (no I/O, no subprocess execution). Subprocess execution, timeout management, and file sanitation are delegated to `VideoAssembler` (`src/assembly/assembler.py`).

---

## 1. Design Requirements & Architectural Objectives

### 1.1 Non-Shell List Format (`List[str]`)
- All command builders MUST return Python lists of strings (`List[str]`).
- Commands are passed to `subprocess.run(cmd, shell=False, close_fds=True)` without shell invocation.
- Shell interpolation vulnerabilities, space-splitting issues, and shell quote injection risks are eliminated by design.

### 1.2 Video & Audio Parameter Baselines
| Parameter | Default Value | Flag / FFmpeg Argument | Description / Rationale |
|---|---|---|---|
| **Target Resolution** | `3840x2160` | Filter graph `scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,setsar=1` | YouTube 4K UHD standard |
| **Frame Rate** | `30` | `-r 30` | 30 FPS standard framerate |
| **Video Codec** | `libx264` | `-c:v libx264` | H.264 High Profile 5.1 |
| **Preset** | `medium` | `-preset medium` | Optimal balance between render speed and file size |
| **Rate Control (CRF)** | `18` | `-crf 18` | Visually lossless quality for 4K video |
| **Pixel Format** | `yuv420p` | `-pix_fmt yuv420p` | 8-bit 4:2:0 subsampling required for browser playback |
| **Audio Codec** | `aac` | `-c:a aac` | Universal YouTube stereo audio standard |
| **Audio Bitrate** | `384k` | `-b:a 384k` | High fidelity audio bitrate |
| **Audio Sample Rate** | `48000` Hz | `-ar 48000` / `aresample=48000` | Standard video production sample rate |
| **Audio Channels** | `2` (Stereo) | `-ac 2` | 2-channel stereo output |

### 1.3 Subtitle Burning & Filter Graph Escaping
- Subtitles are burned directly into the video stream via the FFmpeg `subtitles` filter graph.
- Filter string syntax: `subtitles='<escaped_path>':force_style='<force_style_string>'`.
- Special characters in paths (`:`, `'`, `\`, `[`, `]`) MUST be escaped using `escape_ffmpeg_filter_path` to prevent FFmpeg filter graph parser errors.

---

## 2. API Design & Helper Function Specifications

`src/assembly/ffmpeg_commands.py` exposes 6 pure functions:

### 2.1 `escape_ffmpeg_filter_path(path: Union[str, Path]) -> str`
Escapes file paths for inclusion inside FFmpeg filter graph strings.

**Escaping Rules**:
1. Converts input `path` to absolute resolved string path (`Path(path).resolve()`).
2. Escapes backslashes: `\` -> `\\\\`.
3. Escapes colons: `:` -> `\\:`. (Crucial: FFmpeg filter graphs use `:` as key-value parameter delimiters; unescaped colons in paths like `/tmp/run:1/sub.srt` crash the filter parser).
4. Escapes single quotes: `'` -> `\\'`.
5. Escapes square brackets: `[` -> `\\[`, `]` -> `\\]`.

### 2.2 `build_4k_scale_filter(...)`
Generates an FFmpeg video filter graph segment that scales and pads any input video stream to 4K resolution (3840x2160) while maintaining aspect ratio and enforcing 1:1 Sample Aspect Ratio (SAR).

**Signature**:
```python
def build_4k_scale_filter(
    input_label: str = "0:v",
    output_label: str = "v_scaled",
    width: int = 3840,
    height: int = 2160,
) -> str
```

**Output Syntax**:
`"[{input_label}]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[{output_label}]"`

### 2.3 `build_subtitle_filter(...)`
Generates the FFmpeg `subtitles` filter graph string fragment with custom ASS/SSA typography styling.

**Signature**:
```python
def build_subtitle_filter(
    subtitle_path: Union[str, Path],
    force_style: Optional[Dict[str, str]] = None,
    input_label: str = "v_concat",
    output_label: str = "v_out",
) -> str
```

**Default Typography Style**:
```python
DEFAULT_SUBTITLE_STYLE = {
    "FontName": "Sans",
    "FontSize": "28",
    "PrimaryColour": "&H00FFFFFF",  # White
    "OutlineColour": "&H00000000",  # Black outline
    "BorderStyle": "1",             # Outline + shadow
    "Outline": "2",
    "Shadow": "1",
    "Alignment": "2",               # Bottom-center
}
```

**Output Syntax**:
`"[{input_label}]subtitles='{escaped_path}':force_style='{force_style_str}'[{output_label}]"`

### 2.4 `build_concat_filter_graph(...)`
Constructs a complete complex filter graph string (`-filter_complex`) that:
1. Scales each input video stream to 4K using `build_4k_scale_filter`.
2. Concatenates video streams into a single video track.
3. Concatenates and resamples audio streams to 48kHz.
4. Applies subtitle burning via `build_subtitle_filter` if a subtitle path is provided.

**Signature**:
```python
def build_concat_filter_graph(
    num_video_inputs: int,
    num_audio_inputs: int,
    subtitle_path: Optional[Union[str, Path]] = None,
    subtitle_style: Optional[Dict[str, str]] = None,
    width: int = 3840,
    height: int = 2160,
    fps: int = 30,
) -> Tuple[str, str, Optional[str]]
```
Returns a 3-tuple `(filter_graph_str, final_video_label, final_audio_label)`.

### 2.5 `build_assembly_command(...)`
Constructs the full FFmpeg command list (`List[str]`) using single-pass `-filter_complex`.

**Signature**:
```python
def build_assembly_command(
    video_inputs: List[Union[str, Path]],
    audio_inputs: List[Union[str, Path]],
    output_path: Union[str, Path],
    subtitle_path: Optional[Union[str, Path]] = None,
    subtitle_style: Optional[Dict[str, str]] = None,
    fps: int = 30,
    video_codec: str = "libx264",
    preset: str = "medium",
    crf: int = 18,
    pixel_format: str = "yuv420p",
    audio_codec: str = "aac",
    audio_bitrate: str = "384k",
    audio_sample_rate: int = 48000,
    width: int = 3840,
    height: int = 2160,
    ffmpeg_binary: str = "ffmpeg",
) -> List[str]
```

### 2.6 `build_demuxer_assembly_command(...)`
Constructs an alternate FFmpeg command list (`List[str]`) for demuxer mode when using pre-generated `concat_video.txt` and `concat_audio.txt` text manifest files.

**Signature**:
```python
def build_demuxer_assembly_command(
    video_manifest_path: Union[str, Path],
    audio_manifest_path: Union[str, Path],
    output_path: Union[str, Path],
    subtitle_path: Optional[Union[str, Path]] = None,
    subtitle_style: Optional[Dict[str, str]] = None,
    fps: int = 30,
    video_codec: str = "libx264",
    preset: str = "medium",
    crf: int = 18,
    pixel_format: str = "yuv420p",
    audio_codec: str = "aac",
    audio_bitrate: str = "384k",
    audio_sample_rate: int = 48000,
    width: int = 3840,
    height: int = 2160,
    ffmpeg_binary: str = "ffmpeg",
) -> List[str]
```

---

## 3. Proposed Source Code Implementation for `src/assembly/ffmpeg_commands.py`

Below is the complete, proposed implementation code for `src/assembly/ffmpeg_commands.py`:

```python
"""FFmpeg CLI Command Builders for 4K Video Assembly.

This module provides pure functions to construct non-shell FFmpeg command argument
lists (List[str]) for 4K UHD video rendering, multi-stream concatenation, audio
mixing/resampling, and hard-coded subtitle burning.

All functions are pure and have zero side effects (no file I/O or process execution).
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

DEFAULT_SUBTITLE_STYLE: Dict[str, str] = {
    "FontName": "Sans",
    "FontSize": "28",
    "PrimaryColour": "&H00FFFFFF",  # White text (ASS/SSA format)
    "OutlineColour": "&H00000000",  # Black outline
    "BorderStyle": "1",             # 1 = Outline + drop shadow
    "Outline": "2",                 # Outline thickness
    "Shadow": "1",                  # Shadow depth
    "Alignment": "2",               # 2 = Bottom-center aligned
}


def escape_ffmpeg_filter_path(path: Union[str, Path]) -> str:
    """Escapes special characters in file paths for FFmpeg filter graph syntax.

    FFmpeg's filter graph parser treats colons as parameter delimiters, single quotes
    as string enclosures, backslashes as escape characters, and square brackets
    as stream labels.

    Args:
        path: Absolute or relative file path.

    Returns:
        Escaped path string safe for insertion into FFmpeg filter graph strings.
    """
    path_str = str(Path(path).resolve()) if isinstance(path, Path) else str(path)
    # Order matters: backslashes must be escaped first
    path_str = path_str.replace("\\", "\\\\")
    path_str = path_str.replace(":", "\\:")
    path_str = path_str.replace("'", "\\'")
    path_str = path_str.replace("[", "\\[").replace("]", "\\]")
    return path_str


def build_4k_scale_filter(
    input_label: str = "0:v",
    output_label: str = "v_scaled",
    width: int = 3840,
    height: int = 2160,
) -> str:
    """Generates a video scaling and padding filter graph clause for 4K UHD output.

    Args:
        input_label: Input stream label (e.g. "0:v" or "v0").
        output_label: Output stream label (e.g. "v_scaled").
        width: Target video width in pixels. Default 3840 (4K).
        height: Target video height in pixels. Default 2160 (4K).

    Returns:
        Filter graph string clause.
    """
    return (
        f"[{input_label}]"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1"
        f"[{output_label}]"
    )


def build_subtitle_filter(
    subtitle_path: Union[str, Path],
    force_style: Optional[Dict[str, str]] = None,
    input_label: str = "v_concat",
    output_label: str = "v_out",
) -> str:
    """Generates the subtitles filter graph clause with custom ASS/SSA typography.

    Args:
        subtitle_path: Path to the .srt or .ass subtitle file.
        force_style: Optional dict overriding default subtitle style attributes.
        input_label: Input video stream label. Default "v_concat".
        output_label: Output video stream label. Default "v_out".

    Returns:
        Subtitles filter graph clause string.
    """
    escaped_path = escape_ffmpeg_filter_path(subtitle_path)
    style_dict = dict(DEFAULT_SUBTITLE_STYLE)
    if force_style:
        style_dict.update(force_style)

    style_str = ",".join(f"{k}={v}" for k, v in style_dict.items())
    return f"[{input_label}]subtitles='{escaped_path}':force_style='{style_str}'[{output_label}]"


def build_concat_filter_graph(
    num_video_inputs: int,
    num_audio_inputs: int,
    subtitle_path: Optional[Union[str, Path]] = None,
    subtitle_style: Optional[Dict[str, str]] = None,
    width: int = 3840,
    height: int = 2160,
    fps: int = 30,
) -> Tuple[str, str, Optional[str]]:
    """Constructs a complex filter graph string for multi-input video/audio assembly.

    Args:
        num_video_inputs: Number of video input files (-i options).
        num_audio_inputs: Number of audio input files (-i options).
        subtitle_path: Optional path to .srt subtitle file to burn in.
        subtitle_style: Optional custom subtitle styling override dict.
        width: Target width in pixels (3840 for 4K).
        height: Target height in pixels (2160 for 4K).
        fps: Target framerate.

    Returns:
        Tuple of (filter_complex_string, video_output_label, audio_output_label).

    Raises:
        ValueError: If num_video_inputs < 1.
    """
    if num_video_inputs < 1:
        raise ValueError("num_video_inputs must be at least 1")

    clauses: List[str] = []

    # 1. Scale all video inputs to 4K
    for i in range(num_video_inputs):
        clauses.append(build_4k_scale_filter(f"{i}:v", f"v{i}", width, height))

    # 2. Concat video streams
    if num_video_inputs > 1:
        v_inputs = "".join(f"[v{i}]" for i in range(num_video_inputs))
        clauses.append(f"{v_inputs}concat=n={num_video_inputs}:v=1:a=0[v_concat]")
        current_v_label = "v_concat"
    else:
        current_v_label = "v0"

    # 3. Burn subtitles if provided
    if subtitle_path is not None:
        sub_clause = build_subtitle_filter(
            subtitle_path,
            force_style=subtitle_style,
            input_label=current_v_label,
            output_label="v_out",
        )
        clauses.append(sub_clause)
        final_v_label = "v_out"
    else:
        final_v_label = current_v_label

    # 4. Concat and resample audio streams if present
    final_a_label: Optional[str] = None
    if num_audio_inputs > 1:
        audio_offset = num_video_inputs
        a_inputs = "".join(f"[{audio_offset + j}:a]" for j in range(num_audio_inputs))
        clauses.append(f"{a_inputs}concat=n={num_audio_inputs}:v=0:a=1,aresample=48000[a_out]")
        final_a_label = "a_out"
    elif num_audio_inputs == 1:
        audio_offset = num_video_inputs
        clauses.append(f"[{audio_offset}:a]aresample=48000[a_out]")
        final_a_label = "a_out"

    filter_complex_str = "; ".join(clauses)
    return filter_complex_str, final_v_label, final_a_label


def build_assembly_command(
    video_inputs: List[Union[str, Path]],
    audio_inputs: List[Union[str, Path]],
    output_path: Union[str, Path],
    subtitle_path: Optional[Union[str, Path]] = None,
    subtitle_style: Optional[Dict[str, str]] = None,
    fps: int = 30,
    video_codec: str = "libx264",
    preset: str = "medium",
    crf: int = 18,
    pixel_format: str = "yuv420p",
    audio_codec: str = "aac",
    audio_bitrate: str = "384k",
    audio_sample_rate: int = 48000,
    width: int = 3840,
    height: int = 2160,
    ffmpeg_binary: str = "ffmpeg",
) -> List[str]:
    """Builds a complete non-shell FFmpeg CLI command argument list for 4K video assembly.

    Args:
        video_inputs: List of input video file paths (.mp4).
        audio_inputs: List of input audio file paths (.wav).
        output_path: Target output video file path (.mp4).
        subtitle_path: Optional path to subtitle file (.srt) to burn in.
        subtitle_style: Optional subtitle style overrides.
        fps: Target framerate (default 30).
        video_codec: Encoder name (default "libx264").
        preset: Encoding speed preset (default "medium").
        crf: Quality setting (default 18 for visually lossless).
        pixel_format: Pixel format (default "yuv420p").
        audio_codec: Audio encoder (default "aac").
        audio_bitrate: Audio bitrate (default "384k").
        audio_sample_rate: Audio sampling frequency in Hz (default 48000).
        width: Target width (default 3840).
        height: Target height (default 2160).
        ffmpeg_binary: Path or binary name for FFmpeg executable (default "ffmpeg").

    Returns:
        List[str] representing exact subprocess argument array.

    Raises:
        ValueError: If video_inputs is empty.
    """
    if not video_inputs:
        raise ValueError("video_inputs list cannot be empty")

    cmd: List[str] = [ffmpeg_binary, "-y"]

    # Append video input files
    for vp in video_inputs:
        cmd.extend(["-i", str(vp)])

    # Append audio input files
    for ap in audio_inputs:
        cmd.extend(["-i", str(ap)])

    # Build filter complex graph
    filter_graph, v_map, a_map = build_concat_filter_graph(
        num_video_inputs=len(video_inputs),
        num_audio_inputs=len(audio_inputs),
        subtitle_path=subtitle_path,
        subtitle_style=subtitle_style,
        width=width,
        height=height,
        fps=fps,
    )

    cmd.extend(["-filter_complex", filter_graph])
    cmd.extend(["-map", f"[{v_map}]"])

    if a_map is not None:
        cmd.extend(["-map", f"[{a_map}]"])

    # Add video encoding flags
    cmd.extend([
        "-c:v", video_codec,
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", pixel_format,
        "-r", str(fps),
    ])

    # Add audio encoding flags if audio is present
    if a_map is not None:
        cmd.extend([
            "-c:a", audio_codec,
            "-b:a", audio_bitrate,
            "-ar", str(audio_sample_rate),
            "-ac", "2",
        ])

    cmd.append(str(output_path))
    return cmd


def build_demuxer_assembly_command(
    video_manifest_path: Union[str, Path],
    audio_manifest_path: Union[str, Path],
    output_path: Union[str, Path],
    subtitle_path: Optional[Union[str, Path]] = None,
    subtitle_style: Optional[Dict[str, str]] = None,
    fps: int = 30,
    video_codec: str = "libx264",
    preset: str = "medium",
    crf: int = 18,
    pixel_format: str = "yuv420p",
    audio_codec: str = "aac",
    audio_bitrate: str = "384k",
    audio_sample_rate: int = 48000,
    width: int = 3840,
    height: int = 2160,
    ffmpeg_binary: str = "ffmpeg",
) -> List[str]:
    """Builds an FFmpeg CLI command using concat demuxer text manifest files.

    Args:
        video_manifest_path: Path to concat_video.txt demuxer manifest.
        audio_manifest_path: Path to concat_audio.txt demuxer manifest.
        output_path: Target output video file path.
        subtitle_path: Optional path to .srt subtitle file.
        subtitle_style: Optional custom subtitle style dict.
        fps: Target framerate (default 30).
        video_codec: Video encoder (default "libx264").
        preset: Encoder preset (default "medium").
        crf: Quality setting (default 18).
        pixel_format: Pixel format (default "yuv420p").
        audio_codec: Audio encoder (default "aac").
        audio_bitrate: Audio bitrate (default "384k").
        audio_sample_rate: Sample rate (default 48000).
        width: Width (default 3840).
        height: Height (default 2160).
        ffmpeg_binary: FFmpeg executable binary (default "ffmpeg").

    Returns:
        List[str] representing exact subprocess argument array.
    """
    cmd: List[str] = [
        ffmpeg_binary, "-y",
        "-f", "concat", "-safe", "0", "-i", str(video_manifest_path),
        "-f", "concat", "-safe", "0", "-i", str(audio_manifest_path),
    ]

    vf_filters: List[str] = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "setsar=1",
    ]

    if subtitle_path is not None:
        escaped_path = escape_ffmpeg_filter_path(subtitle_path)
        style_dict = dict(DEFAULT_SUBTITLE_STYLE)
        if subtitle_style:
            style_dict.update(subtitle_style)
        style_str = ",".join(f"{k}={v}" for k, v in style_dict.items())
        vf_filters.append(f"subtitles='{escaped_path}':force_style='{style_str}'")

    cmd.extend(["-vf", ",".join(vf_filters)])

    cmd.extend([
        "-c:v", video_codec,
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", pixel_format,
        "-r", str(fps),
        "-c:a", audio_codec,
        "-b:a", audio_bitrate,
        "-ar", str(audio_sample_rate),
        "-ac", "2",
        str(output_path),
    ])

    return cmd
```

---

## 4. Analysis of Edge Cases & Vulnerabilities

| # | Edge Case / Scenario | Mitigation in Design |
|---|---|---|
| 1 | **Colons / Single Quotes in Subtitle Path** | `escape_ffmpeg_filter_path()` replaces `:` with `\\:`, `'` with `\\'`, `\` with `\\\\`, and `[`/`]` with `\\[`/`\\]`. |
| 2 | **Input Video Aspect Ratio Mismatch** | `build_4k_scale_filter()` uses `force_original_aspect_ratio=decrease` and `pad=3840:2160:(ow-iw)/2:(oh-ih)/2` to letterbox/pillarbox without distorting geometry. |
| 3 | **Empty Video Inputs List** | `build_assembly_command()` checks `if not video_inputs:` and raises `ValueError("video_inputs list cannot be empty")`. |
| 4 | **No Audio Inputs Provided** | `build_concat_filter_graph()` returns `final_a_label = None`. `build_assembly_command()` omits `-map [a_out]` and `-c:a`/`-b:a` audio parameters cleanly. |
| 5 | **Sub-100 Byte Output / Render Failure** | Command builders strictly produce pure command arrays; output file size validation (`st_size > 100`) is handled in `VideoAssembler` (`src/assembly/assembler.py`). |
| 6 | **Mock Subprocess Execution in Unit Tests** | Binary name can be overridden via `ffmpeg_binary="python_mock.py"`, allowing tests to inspect returned `List[str]` command arguments without calling real `ffmpeg`. |

---

## 5. Verification Method

Unit tests in `tests/pipeline/test_assembly_node.py` will verify:
1. `test_escape_ffmpeg_filter_path()`: Validates that paths containing colons (`/tmp/run:1/sub's.srt`) escape to `/tmp/run\:1/sub\'s.srt`.
2. `test_build_4k_scale_filter()`: Asserts that output contains `scale=3840:2160`, `pad=3840:2160`, and `setsar=1`.
3. `test_build_subtitle_filter()`: Asserts subtitle string syntax and style parameter format (`force_style='FontName=Sans...'`).
4. `test_build_assembly_command_list_format()`: Verifies that returned value is a `list`, contains `libx264`, `yuv420p`, `384k`, `-crf`, `18`, `-r`, `30`, `-filter_complex`, and does NOT contain shell strings.
5. `test_empty_video_inputs_raises_value_error()`: Asserts `ValueError` raised when empty list is passed.
