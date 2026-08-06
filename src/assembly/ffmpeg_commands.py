"""FFmpeg CLI Command Builders for 4K Video Assembly.

This module provides pure helper functions to construct non-shell FFmpeg command
argument lists (List[str]) for 4K UHD video rendering (3840x2160, 30fps, libx264,
yuv420p, crf 18, aac 384k), multi-stream concatenation, audio mixing/resampling,
and hard-coded subtitle burning.

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


def write_concat_file(
    file_paths: List[Union[str, Path]],
    output_manifest_path: Union[str, Path],
) -> Path:
    """Writes an FFmpeg concat demuxer text manifest file.

    Args:
        file_paths: List of video or audio file paths to concatenate.
        output_manifest_path: Target path for text manifest file (e.g., concat_list.txt).

    Returns:
        Path: Resolved absolute path to created manifest file.
    """
    manifest_p = Path(output_manifest_path).resolve()
    manifest_p.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for fp in file_paths:
        abs_p = str(Path(fp).resolve()).replace("'", "'\\''")
        lines.append(f"file '{abs_p}'")
    manifest_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_p


def build_4k_scale_filter(
    input_label: str = "0:v",
    output_label: str = "v_scaled",
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> str:
    """Generates a video scaling and padding filter graph clause for 4K UHD output.

    Args:
        input_label: Input stream label (e.g. "0:v" or "v0").
        output_label: Output stream label (e.g. "v_scaled").
        width: Target video width in pixels. Default 3840 (4K).
        height: Target video height in pixels. Default 2160 (4K).
        fps: Target framerate. Default 30.

    Returns:
        Filter graph string clause.
    """
    return (
        f"[{input_label}]"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,"
        f"fps={fps},"
        f"setpts=PTS-STARTPTS"
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
    width: int = 1920,
    height: int = 1080,
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
        clauses.append(build_4k_scale_filter(f"{i}:v", f"v{i}", width, height, fps=fps))

    # 2. Concat video streams
    if num_video_inputs > 1:
        v_inputs = "".join(f"[v{i}]" for i in range(num_video_inputs))
        clauses.append(f"{v_inputs}concat=n={num_video_inputs}:v=1:a=0[v_concat]")
        current_v_label = "v_concat"
    else:
        current_v_label = "v0"

    # Pad video infinitely if audio is present
    if num_audio_inputs > 0:
        clauses.append(f"[{current_v_label}]tpad=stop_mode=clone:stop=-1,settb=1/{fps},setpts=N/{fps}/TB[v_padded]")
        current_v_label = "v_padded"

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
    video_inputs: Optional[List[Union[str, Path]]] = None,
    audio_inputs: Optional[Union[List[Union[str, Path]], Union[str, Path]]] = None,
    output_path: Optional[Union[str, Path]] = None,
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
    width: int = 1920,
    height: int = 1080,
    ffmpeg_binary: str = "ffmpeg",
    video_segments: Optional[List[Union[str, Path]]] = None,
    audio_path: Optional[Union[str, Path]] = None,
    concat_list_path: Optional[Union[str, Path]] = None,
    resolution: Optional[str] = None,
    output_duration: Optional[float] = None,
) -> List[str]:
    """Builds a complete non-shell FFmpeg CLI command argument list for 4K video assembly.

    Args:
        video_inputs: List of input video file paths (.mp4).
        audio_inputs: Input audio file path(s) (.wav/.mp3).
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
        video_segments: Alias for video_inputs.
        audio_path: Alias for single audio_inputs path.
        concat_list_path: Optional path to demuxer manifest file.
        resolution: Optional resolution string (e.g. "3840x2160").

    Returns:
        List[str] representing exact subprocess argument array.

    Raises:
        ValueError: If video inputs list is empty and no concat list path is provided.
    """
    v_inputs = video_inputs if video_inputs is not None else video_segments
    a_inputs: List[Union[str, Path]] = []
    if audio_inputs is not None:
        if isinstance(audio_inputs, (str, Path)):
            a_inputs = [audio_inputs]
        else:
            a_inputs = list(audio_inputs)
    elif audio_path is not None:
        a_inputs = [audio_path]

    if resolution and "x" in resolution:
        try:
            w_str, h_str = resolution.split("x")
            width = int(w_str)
            height = int(h_str)
        except ValueError:
            pass

    # If demuxer concat manifest file is used directly
    if concat_list_path is not None:
        return build_demuxer_assembly_command(
            video_manifest_path=concat_list_path,
            audio_manifest_path=a_inputs[0] if a_inputs else None,
            output_path=output_path or "output.mp4",
            subtitle_path=subtitle_path,
            subtitle_style=subtitle_style,
            fps=fps,
            video_codec=video_codec,
            preset=preset,
            crf=crf,
            pixel_format=pixel_format,
            audio_codec=audio_codec,
            audio_bitrate=audio_bitrate,
            audio_sample_rate=audio_sample_rate,
            width=width,
            height=height,
            ffmpeg_binary=ffmpeg_binary,
            output_duration=output_duration,
        )

    if not v_inputs:
        raise ValueError("video_inputs (or video_segments) list cannot be empty")

    if output_path is None:
        output_path = "output.mp4"

    cmd: List[str] = [ffmpeg_binary, "-y"]

    # Append video input files
    for vp in v_inputs:
        cmd.extend(["-i", str(vp)])

    # Append audio input files
    for ap in a_inputs:
        cmd.extend(["-i", str(ap)])

    # Build filter complex graph
    filter_graph, v_map, a_map = build_concat_filter_graph(
        num_video_inputs=len(v_inputs),
        num_audio_inputs=len(a_inputs),
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
        if output_duration is not None:
            cmd.extend(["-t", str(output_duration)])
        else:
            cmd.append("-shortest")

    cmd.append(str(output_path))
    return cmd


def build_demuxer_assembly_command(
    video_manifest_path: Union[str, Path],
    audio_manifest_path: Optional[Union[str, Path]] = None,
    output_path: Union[str, Path] = "output.mp4",
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
    width: int = 1920,
    height: int = 1080,
    ffmpeg_binary: str = "ffmpeg",
    output_duration: Optional[float] = None,
) -> List[str]:
    """Builds an FFmpeg CLI command using concat demuxer text manifest files.

    Args:
        video_manifest_path: Path to concat_video.txt demuxer manifest.
        audio_manifest_path: Optional path to audio file or concat_audio.txt manifest.
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
    ]

    has_audio = False
    if audio_manifest_path is not None:
        has_audio = True
        audio_p = Path(audio_manifest_path)
        if audio_p.name.endswith(".txt"):
            cmd.extend(["-f", "concat", "-safe", "0", "-i", str(audio_manifest_path)])
        else:
            cmd.extend(["-i", str(audio_manifest_path)])

    vf_filters: List[str] = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "setsar=1",
        f"fps={fps}",
        "setpts=PTS-STARTPTS",
    ]

    if has_audio:
        vf_filters.append("tpad=stop_mode=clone:stop=-1")

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
    ])

    if has_audio:
        cmd.extend([
            "-c:a", audio_codec,
            "-b:a", audio_bitrate,
            "-ar", str(audio_sample_rate),
            "-ac", "2",
        ])
        if output_duration is not None:
            cmd.extend(["-t", str(output_duration)])
        else:
            cmd.append("-shortest")

    cmd.append(str(output_path))
    return cmd
