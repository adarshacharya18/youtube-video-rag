# Design Specification: VideoAssembler (`src/assembly/assembler.py`)

## Executive Summary
This document provides the complete architectural design, method signatures, error handling mapping, security specifications, temporary directory management, and full code implementation for `VideoAssembler` in `src/assembly/assembler.py`. `VideoAssembler` is responsible for low-level secure FFmpeg execution in Phase 13 of the Automated DSA Educational YouTube Video Pipeline.

---

## 1. Requirements & Security Specifications

### 1.1 Key Objectives
1. Design `VideoAssembler` class with `assemble(...)` and `run_command(...)` methods.
2. Secure `subprocess.run(...)` invocation:
   - `shell=False` (explicitly enforced for parameter array isolation).
   - `close_fds=True` (prevents file descriptor leaks into child subprocesses).
   - `timeout=300.0` (configurable default wall-clock limit).
   - `capture_output=True` (captures stdout/stderr).
   - `text=True` (decodes output streams to UTF-8 strings).
3. Exception Mapping:
   - `subprocess.TimeoutExpired` -> `AssemblyError` (`src/core/exceptions.py:140`).
   - Non-zero exit code (`returncode != 0`) -> `AssemblyError` with captured `stderr`/`stdout`.
   - Output file missing or < 100 bytes -> `AssemblyError`.
4. Temporary File Management:
   - Use `tempfile.TemporaryDirectory(prefix="assembly_", dir=...)` for context-managed cleanup.
   - Write intermediate `concat_list.txt` and `subtitles.srt` files inside the temporary directory.
   - Atomic file creation via temporary output path (`tmp_dest`) and `os.replace()`.
   - `try...finally` / `try...except` explicit deletion of partial destination files on failure.

---

## 2. Class Architecture & Interface Contract

```
+-------------------------------------------------------------------+
|                          VideoAssembler                           |
+-------------------------------------------------------------------+
| - ffmpeg_binary: Optional[str]                                    |
| - timeout: float = 300.0                                          |
| - temp_dir: Optional[Path]                                        |
+-------------------------------------------------------------------+
| + __init__(ffmpeg_binary, timeout, temp_dir)                      |
| + run_command(args, timeout, cwd) -> CompletedProcess             |
| + assemble(video_segments, audio_path, subtitle_path, ...) -> Path|
| - _resolve_binary_command() -> List[str]                          |
| - _is_valid_video(file_path, min_bytes) -> bool                   |
+-------------------------------------------------------------------+
```

### 2.1 Method Signatures

#### `__init__`
```python
def __init__(
    self,
    ffmpeg_binary: Optional[str] = None,
    timeout: float = 300.0,
    temp_dir: Optional[Union[str, Path]] = None,
) -> None
```
- **`ffmpeg_binary`**: Optional custom path or binary name (e.g. `/usr/bin/ffmpeg` or mock python script ending in `.py`). If `None`, defaults to `"ffmpeg"`.
- **`timeout`**: Default execution timeout limit in seconds (default: `300.0`).
- **`temp_dir`**: Custom parent directory for temporary directory creation (useful for testing or dedicated scratch mounts).

#### `run_command`
```python
def run_command(
    self,
    args: List[str],
    timeout: Optional[float] = None,
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess
```
- Executes low-level non-shell FFmpeg command using `subprocess.run(..., close_fds=True, capture_output=True, text=True)`.
- Catches `subprocess.TimeoutExpired` and process returncode errors, mapping them to `AssemblyError`.

#### `assemble`
```python
def assemble(
    self,
    video_segments: List[Union[str, Path]],
    audio_path: Optional[Union[str, Path]] = None,
    subtitle_path: Optional[Union[str, Path]] = None,
    subtitle_text: Optional[str] = None,
    output_path: Union[str, Path] = None,
    resolution: str = "3840x2160",
    fps: int = 30,
    crf: int = 18,
    preset: str = "medium",
    timeout: Optional[float] = None,
) -> Path
```
- Main entry point for video assembly.
- Creates `tempfile.TemporaryDirectory()`, writes `concat_list.txt` and `subtitles.srt` (if string provided), builds FFmpeg command via `src.assembly.ffmpeg_commands`, executes `run_command(...)`, validates artifact size, performs atomic rename to `output_path`, and guarantees temp file cleanup.

---

## 3. Subprocess Execution & Error Mapping Matrix

| Failure Condition | Internal Exception / Event | Mapped Result Exception | Informative Details Captured |
|---|---|---|---|
| Timeout reached during render | `subprocess.TimeoutExpired` | `AssemblyError` | Wall-clock timeout duration, trailing 500 chars of stdout/stderr |
| FFmpeg exits with code != 0 | `result.returncode != 0` | `AssemblyError` | Exit code number, formatted stderr / stdout error output |
| Missing input segment clip | `not seg_path.exists()` | `AssemblyError` | Exact segment path missing on disk |
| Output file missing or < 100B | `_is_valid_video(...) == False` | `AssemblyError` | Target destination path, file size in bytes |
| Command binary execution failure | `FileNotFoundError` / `OSError` | `AssemblyError` | Binary path, underlying OS error message |

---

## 4. Temporary File & Directory Lifecycle

```
[Start assemble()]
       |
       v
Validate Input Paths (segments, audio, subtitles)
       |
       v
Create tempfile.TemporaryDirectory(prefix="assembly_")
       |
       +---> Write concat_list.txt (escaping single quotes)
       |
       +---> Write subtitles.srt (if subtitle_text provided)
       |
       +---> Build FFmpeg command list via ffmpeg_commands
       |
       v
Execute subprocess.run(..., cwd=temp_dir, close_fds=True, timeout=300.0)
       |
  +----+----+
  |         |
[Success] [Failure]
  |         |
  v         v
Validate   Clean up tmp_dest file
Output     Raise AssemblyError
Artifact
  |
  v
Atomic Rename (os.replace)
  |
  v
Exit Context Manager (tempfile.TemporaryDirectory auto-deleted)
```

---

## 5. Complete Code Implementation Specification for `src/assembly/assembler.py`

Below is the exact code formulation to be written to `src/assembly/assembler.py`:

```python
"""FFmpeg Video Assembler for Phase 13 Media Production.

Executes FFmpeg commands securely via non-shell subprocess.run(), manages timeouts,
maps errors to AssemblyError, and enforces temporary file cleanup.
"""

import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Union

from src.assembly.ffmpeg_commands import (
    build_assembly_command,
    write_concat_file,
)
from src.core.exceptions import AssemblyError

logger = logging.getLogger(__name__)


class VideoAssembler:
    """Encapsulates secure low-level FFmpeg execution for video assembly."""

    def __init__(
        self,
        ffmpeg_binary: Optional[str] = None,
        timeout: float = 300.0,
        temp_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        """Initialize VideoAssembler.

        Args:
            ffmpeg_binary: Optional path or executable name for FFmpeg binary or mock script.
            timeout: Subprocess wall-clock timeout limit in seconds (default: 300.0).
            temp_dir: Optional custom directory for temporary file creation.
        """
        self.ffmpeg_binary = ffmpeg_binary
        self.timeout = timeout
        self.temp_dir = Path(temp_dir) if temp_dir else None

    def _resolve_binary_command(self) -> List[str]:
        """Resolve binary prefix for FFmpeg execution."""
        if self.ffmpeg_binary:
            if self.ffmpeg_binary.endswith(".py"):
                return [sys.executable, self.ffmpeg_binary]
            return [self.ffmpeg_binary]
        return ["ffmpeg"]

    def _is_valid_video(self, file_path: Path, min_bytes: int = 100) -> bool:
        """Validate that output video exists and is at least min_bytes."""
        if not file_path.exists():
            return False
        try:
            return file_path.stat().st_size >= min_bytes
        except Exception:
            return False

    def run_command(
        self,
        args: List[str],
        timeout: Optional[float] = None,
        cwd: Optional[Path] = None,
    ) -> subprocess.CompletedProcess:
        """Execute non-shell FFmpeg command with secure flags and error mapping.

        Args:
            args: Command arguments starting after binary name (or including full command).
            timeout: Optional custom timeout override (seconds).
            cwd: Optional working directory for execution.

        Returns:
            subprocess.CompletedProcess: Executed process result.

        Raises:
            AssemblyError: On non-zero exit code, process failure, or timeout.
        """
        binary_prefix = self._resolve_binary_command()
        
        # Check if args already starts with binary prefix
        if args and (args[0] == binary_prefix[0] or (len(binary_prefix) > 1 and args[:len(binary_prefix)] == binary_prefix)):
            full_cmd = list(args)
        else:
            full_cmd = binary_prefix + list(args)

        effective_timeout = timeout if timeout is not None else self.timeout
        work_dir = cwd or (self.temp_dir if self.temp_dir and self.temp_dir.exists() else Path.cwd())

        logger.debug("Running FFmpeg command: %s (cwd=%s)", " ".join(full_cmd), work_dir)

        try:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                close_fds=True,
                timeout=effective_timeout,
                cwd=str(work_dir),
            )
        except subprocess.TimeoutExpired as e:
            stdout_str = (e.stdout or "") if isinstance(e.stdout, str) else ""
            stderr_str = (e.stderr or "") if isinstance(e.stderr, str) else ""
            raise AssemblyError(
                f"FFmpeg process timed out after {effective_timeout}s. "
                f"Stdout: {stdout_str[-500:]} Stderr: {stderr_str[-500:]}"
            ) from e
        except Exception as e:
            raise AssemblyError(f"Failed to execute FFmpeg subprocess: {e}") from e

        if result.returncode != 0:
            error_output = result.stderr.strip() if result.stderr else result.stdout.strip()
            raise AssemblyError(
                f"FFmpeg assembly failed with exit code {result.returncode}:\n{error_output}"
            )

        return result

    def assemble(
        self,
        video_segments: List[Union[str, Path]],
        audio_path: Optional[Union[str, Path]] = None,
        subtitle_path: Optional[Union[str, Path]] = None,
        subtitle_text: Optional[str] = None,
        output_path: Union[str, Path] = None,
        resolution: str = "3840x2160",
        fps: int = 30,
        crf: int = 18,
        preset: str = "medium",
        timeout: Optional[float] = None,
    ) -> Path:
        """Assemble video clips, audio narration, and subtitles into final video artifact.

        Args:
            video_segments: List of input video segment file paths (.mp4).
            audio_path: Optional path to combined audio narration file (.wav / .mp3).
            subtitle_path: Optional path to SRT subtitle file (.srt).
            subtitle_text: Optional raw SRT content string.
            output_path: Target destination path for final assembled video artifact (.mp4).
            resolution: Output resolution string (e.g. '3840x2160' or '1080p').
            fps: Frame rate for final output (default: 30).
            crf: Constant Rate Factor quality parameter (default: 18).
            preset: H.264 encoding preset (default: 'medium').
            timeout: Wall-clock timeout override in seconds.

        Returns:
            Path: Absolute path to valid final assembled video file.

        Raises:
            AssemblyError: If input files are invalid, FFmpeg fails, or output generation fails.
        """
        if not video_segments:
            raise AssemblyError("Cannot assemble video: video_segments list is empty")

        if not output_path:
            raise AssemblyError("Cannot assemble video: output_path is required")

        dest_path = Path(output_path).resolve()
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Validate input segment files exist
        valid_segments: List[Path] = []
        for p in video_segments:
            seg_p = Path(p).resolve()
            if not seg_p.exists():
                raise AssemblyError(f"Input video segment does not exist: {seg_p}")
            valid_segments.append(seg_p)

        valid_audio = Path(audio_path).resolve() if audio_path else None
        if valid_audio and not valid_audio.exists():
            raise AssemblyError(f"Input audio file does not exist: {valid_audio}")

        valid_sub = Path(subtitle_path).resolve() if subtitle_path else None
        if valid_sub and not valid_sub.exists():
            raise AssemblyError(f"Input subtitle file does not exist: {valid_sub}")

        parent_temp = str(self.temp_dir) if self.temp_dir else None
        if self.temp_dir:
            self.temp_dir.mkdir(parents=True, exist_ok=True)

        tmp_dest = dest_path.parent / f"{dest_path.name}.tmp_{os.getpid()}"

        try:
            with tempfile.TemporaryDirectory(prefix="assembly_", dir=parent_temp) as temp_dir_str:
                temp_dir = Path(temp_dir_str)

                # 1. Write concat list file in temp_dir
                concat_list_file = temp_dir / "concat_list.txt"
                write_concat_file(valid_segments, concat_list_file)

                # 2. Handle subtitle path or string content
                effective_sub_path = valid_sub
                if not effective_sub_path and subtitle_text:
                    temp_srt_path = temp_dir / "subtitles.srt"
                    temp_srt_path.write_text(subtitle_text, encoding="utf-8")
                    effective_sub_path = temp_srt_path

                # 3. Build FFmpeg command
                cmd_args = build_assembly_command(
                    concat_list_path=concat_list_file,
                    audio_path=valid_audio,
                    subtitle_path=effective_sub_path,
                    output_path=tmp_dest,
                    resolution=resolution,
                    fps=fps,
                    crf=crf,
                    preset=preset,
                )

                # 4. Execute FFmpeg
                self.run_command(cmd_args, timeout=timeout, cwd=temp_dir)

                # 5. Validate output file
                if not self._is_valid_video(tmp_dest, min_bytes=100):
                    raise AssemblyError(
                        f"FFmpeg assembly execution completed but produced invalid or empty file at {tmp_dest}"
                    )

                # 6. Atomic rename to destination path
                os.replace(tmp_dest, dest_path)
                logger.info("Successfully assembled video artifact: %s", dest_path)
                return dest_path

        except Exception:
            # Clean up temporary output file on failure
            if tmp_dest.exists():
                try:
                    tmp_dest.unlink()
                except Exception as cleanup_err:
                    logger.warning("Failed to clean up temporary file %s: %s", tmp_dest, cleanup_err)
            raise
```

---

## 6. Verification & Test Guidance

To verify `VideoAssembler` implementation in unit tests (`tests/pipeline/test_assembly_node.py` or `tests/assembly/test_assembler.py`):
1. **Mock Execution**: Pass a mock python script as `ffmpeg_binary` that creates dummy MP4 outputs (or exits with code 1 / sleeps past timeout).
2. **Timeout Handling**: Assert `pytest.raises(AssemblyError)` when subprocess exceeds specified timeout.
3. **Non-Zero Exit Code**: Assert `AssemblyError` when subprocess returns exit code 1 with stderr.
4. **Temp Directory Cleanup**: Assert that `tempfile.TemporaryDirectory` paths and intermediate `.tmp` files are deleted after completion or failure.
5. **FD Leak Check**: Measure open file descriptors before and after execution using `len(os.listdir('/proc/self/fd'))`.
