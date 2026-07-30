# Phase 13: Media Production — Video Assembly Specification Analysis

## Executive Overview

Phase 13 (Media Production: Video Assembly) is responsible for assembling intermediate media assets — specifically `.wav` narration audio artifacts (generated in Phase 11 / Voice subsystem) and `.mp4` Manim animation clips (rendered in Phase 12) — into a final high-resolution 4K YouTube video with hard-coded (burned-in) subtitles.

This subsystem operates as a core node (`VideoAssemblyNode`) within the Synchronous Batch Pipeline architecture, inheriting from `Node` (`src/core/workflow/node.py`). It reads prior step outputs from the SQLite `StateLedger`, builds secure FFmpeg commands, executes rendering via `subprocess.run()`, manages temporary filesystem cleanup, and registers the final `AssembledVideo` manifest into the `StateLedger`.

---

## 1. Requirements Breakdown (R1 – R4)

### R1. Implement Video Assembly Node
* **Target Location**: `src/pipeline/nodes/video_assembly_node.py`
* **Node Class**: `VideoAssemblyNode(Node)` with `name = "video_assembly"`.
* **Primary Responsibility**:
  - Retrieve `.wav` audio artifact paths and `.mp4` animation clip paths from `StateLedger` for a given `run_id`.
  - Perform 4K video rendering (3840x2160) at 30 FPS.
  - Mix audio tracks into AAC stereo.
  - Burn spoken narration subtitles into the video stream.
  - Persist an `AssembledVideo` schema payload into `StateLedger` under step `video_assembly`.

### R2. Secure FFmpeg Execution & Resource Management
* **Subprocess Security**:
  - Non-shell execution (`shell=False`, argument list `List[str]`).
  - Strict file descriptor control (`close_fds=True`).
  - Configurable wall-clock timeout (`timeout=300.0` seconds default).
  - Explicit output capture (`capture_output=True`, `text=True`).
  - Strict exception mapping (`subprocess.CalledProcessError`, `TimeoutExpired` mapped to `AssemblyError`).
* **Resource Sanitation**:
  - Context-managed temporary directories (`tempfile.TemporaryDirectory()`).
  - Mandatory cleanup of intermediate concat text lists, temporary `.wav` files, and `.srt`/`.ass` subtitle files upon both success and error paths.
  - Corrupt output invalidation: Deletion of output files smaller than 100 bytes.

### R3. Draft FFmpeg Architecture Documentation
* **Target File**: `PromptBook/Phase13/01_Video_Assembly.md`.
* **Documentation Scope**: Complete architectural specification covering filter graphs, 4K scaling, subtitle styling/escaping, subprocess constraints, memory management, and unit test verification suite.

### R4. Command Restrictions & Automation
* Standard command execution rules apply (subagents may run shell commands for build/test verification without explicit manual prompt permissions).

---

## 2. Technical FFmpeg & Assembly Parameter Specification

### 2.1 Video & Audio Format Requirements
| Parameter | Specification / Value | Rationale / Standard |
|---|---|---|
| **Target Resolution** | `3840x2160` (4K UHD) | YouTube recommended 4K standard (16:9 aspect ratio) |
| **Frame Rate (FPS)** | `30` (or `60` configurable) | YouTube standard framerate (`-r 30`) |
| **Video Codec** | `libx264` (H.264 High Profile 5.1) | Universal compatibility across players and web |
| **Pixel Format** | `yuv420p` | 8-bit 4:2:0 subsampling required for browser playback |
| **Encoder Preset** | `medium` | Optimal balance between render speed and file compression |
| **Rate Control (CRF)** | `18` | Visually lossless quality for 4K video |
| **Audio Codec** | `aac` | Standard YouTube stereo audio format |
| **Audio Bitrate** | `384k` | High fidelity audio bitrate |
| **Audio Sample Rate**| `48000` Hz (48 kHz) | Standard video production sample rate |
| **Audio Channels** | `2` (Stereo) | Standard YouTube audio layout |

### 2.2 FFmpeg Command Strategies

#### Strategy A: Single-Pass Complex Filter Graph (Recommended for Variable Inputs)
Combines scaling, padding, video concatenation, audio concatenation, and subtitle burning in one invocation:

```bash
ffmpeg -y \
  -i input_seg01.mp4 -i input_seg02.mp4 \
  -i input_audio01.wav -i input_audio02.wav \
  -filter_complex \
  "[0:v]scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,setsar=1[v0]; \
   [1:v]scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,setsar=1[v1]; \
   [v0][v1]concat=n=2:v=1:a=0[v_concat]; \
   [2:a][3:a]concat=n=2:v=0:a=1,aresample=48000[a_concat]; \
   [v_concat]subtitles=temp_subtitles.srt:force_style='FontName=Sans,FontSize=28,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2'[v_out]" \
  -map "[v_out]" -map "[a_concat]" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 384k -r 30 \
  output_4k.mp4
```

#### Strategy B: Multi-Stage Concat Demuxer + Subtitle Burn (Recommended for Uniform Inputs)
1. **Stage 1 (Concat Manifest Generation)**:
   Create `concat_video.txt`:
   ```
   file '/abs/path/to/segment_01.mp4'
   file '/abs/path/to/segment_02.mp4'
   ```
   Create `concat_audio.txt`:
   ```
   file '/abs/path/to/narration_01.wav'
   file '/abs/path/to/narration_02.wav'
   ```

2. **Stage 2 (FFmpeg Execution)**:
   ```bash
   ffmpeg -y \
     -f concat -safe 0 -i concat_video.txt \
     -f concat -safe 0 -i concat_audio.txt \
     -vf "scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,subtitles=temp_subtitles.srt:force_style='FontName=Sans,FontSize=28,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2'" \
     -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
     -c:a aac -b:a 384k -r 30 \
     output_4k.mp4
   ```

### 2.3 Subtitle Filter Syntax & Escaping Rules
* **Filter String**: `-vf "subtitles=file.srt:force_style='...'"`
* **Path Escaping**: In FFmpeg filter graph strings, file paths containing colons `:` must be escaped as `\\:`, single quotes `'` as `\\'`, and backslashes `\` as `\\\\`.
* **Style Parameters**:
  - `FontName=Sans` or `Arial`
  - `FontSize=28` (scaled appropriately for 4K resolution)
  - `PrimaryColour=&H00FFFFFF` (White text)
  - `OutlineColour=&H00000000` (Black outline)
  - `BorderStyle=1` (Outline + drop shadow)
  - `Outline=2`, `Shadow=1`
  - `Alignment=2` (Bottom-center aligned)

---

## 3. Features Discovered

## Features Discovered
| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | State Ledger | Prior Step Input Retrieval | Retrieve `.mp4` segments from `animation_generator` and `.wav` audio / narration from `script_generator` / `voice_generator` | `run_id: str`, `ledger: StateLedger` | Dictionary of segment payloads & file paths | Missing ledger or missing step raises `PipelineStageError` | `ORIGINAL_REQUEST.md` (R1), `node.py` |
| 2 | State Ledger | Assembled Video Registration | Persist final output dictionary matching `AssembledVideo` schema into `StateLedger` under step `video_assembly` | `AssembledVideo` attributes | Stored JSON record in SQLite ledger | Validation failure raises `ValidationError`, caught as `AssemblyError` | `src/core/models/assets.py` |
| 3 | FFmpeg Engine | 4K H.264 Video Encoding | Encode merged visual stream to 3840x2160 30fps H.264 video with `yuv420p`, `-preset medium`, `-crf 18` | Segment video paths, resolution `3840x2160`, fps `30` | 4K UHD `.mp4` file | Non-zero exit code raises `AssemblyError` | `ORIGINAL_REQUEST.md` (R1), `VideoMetadata` |
| 4 | FFmpeg Engine | Audio Track Merging & Resampling | Merge segment `.wav` narration files into a single 48kHz stereo AAC audio track (`-c:a aac -b:a 384k`) | Segment audio paths | AAC stereo stream multiplexed in `.mp4` | Mismatched sample rates resampled; corrupt audio raises `AssemblyError` | `ORIGINAL_REQUEST.md` (R1) |
| 5 | FFmpeg Engine | Subtitle Generation & Burning | Generate `.srt`/`.ass` subtitle file from spoken narration and burn into video via `-vf subtitles=...` | Subtitle text, timing, font styling parameters | Hard-subbed video stream | Escaping errors or missing fonts raise `AssemblyError` | `ORIGINAL_REQUEST.md` (R1, R3) |
| 6 | Subprocess | Non-Shell Subprocess Sandboxing | Execute FFmpeg CLI via `subprocess.run(cmd, shell=False, close_fds=True)` passing argument array | `cmd: List[str]`, `timeout: float` | Executed subprocess result | Shell injection prevented; non-zero exit raises `AssemblyError` | `ORIGINAL_REQUEST.md` (R2), `renderer.py` |
| 7 | Subprocess | Wall-Clock Timeout Enforcement | Enforce `timeout` limit on FFmpeg execution to prevent infinite loops / stuck encodes | `timeout: float = 300.0` | Process completion | Raises `subprocess.TimeoutExpired`, killed process, raises `AssemblyError` | `ORIGINAL_REQUEST.md` (R2) |
| 8 | Subprocess | Mock Binary CLI Support | Accept `ffmpeg_binary` parameter in constructor to allow mock Python script testing without real FFmpeg binary | `ffmpeg_binary: Optional[str]` | Execution of mock script in test suite | Invalid binary path raises `FileNotFoundError` / `AssemblyError` | `tests/pipeline/test_animation_node.py` |
| 9 | Resource Mgt | Context-Managed Temp File Sanitation | Create temporary working directory via `tempfile.TemporaryDirectory()` and guarantee cleanup upon completion | Transient manifests, temp audio, temp srt | Clean filesystem post-execution | Cleanup runs in `finally` block even if process crashes | `ORIGINAL_REQUEST.md` (R2, AC) |
| 10 | Resource Mgt | Corrupt Output Invalidation | Check output file existence and size (`st_size > 100` bytes). Delete corrupt zero-byte output file before raising error | Target `final_video_path` | Validated MP4 file on disk | Sub-100-byte output file deleted and `AssemblyError` raised | `src/animation/renderer.py` |
| 11 | Documentation | Architectural Documentation | Comprehensive documentation draft in `PromptBook/Phase13/01_Video_Assembly.md` | Phase 13 specs & filter graphs | Markdown architecture guide | Missing sections fail acceptance criteria | `ORIGINAL_REQUEST.md` (R3, AC) |

---

## 4. Edge Cases Inventory

## Edge Cases
| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | Audio/Video Duration Mismatch | Segment visual duration (5.0s) != narration audio duration (7.2s) | Video finishes before voiceover ends. Handler must pad visual frame using `tpad`/`loop` or adjust segment timing. |
| 2 | Subtitle Path Special Characters | Path contains colons/quotes (e.g. `/tmp/run:1/sub's.srt`) or narration contains `[O(N)]` | Filter graph string parser fails. Filter argument string must escape colons as `\\:`, quotes as `\\'`, and special characters. |
| 3 | Missing / Corrupt Input Assets | Ledger points to non-existent `/path/to/missing.mp4` or zero-byte `.wav` | Precondition check in node verifies file existence and non-zero size, raising `AssemblyError` before invoking FFmpeg. |
| 4 | Empty Narration Subtitles | Segment contains empty narration text `""` | Subtitle generator produces empty `.srt` file or omits `-vf subtitles` filter clause cleanly to prevent FFmpeg syntax error. |
| 5 | FFmpeg Timeout Exceeded | Rendering 4K video exceeds `timeout` limit (e.g. > 300 seconds) | `subprocess.TimeoutExpired` caught, process killed, temporary directory deleted, `AssemblyError` raised. |
| 6 | Sub-100-Byte Truncated MP4 | FFmpeg fails due to full disk space or partial write, leaving 48-byte header | File size validation detects `st_size < 100`, deletes corrupted output file, and raises `AssemblyError`. |
| 7 | Mixed Resolution Input Clips | Manim clips rendered at 720p/1080p combined into 4K pipeline | Direct concat demuxing produces corrupted aspect ratio. Scale/pad filter graph normalizes all inputs to 3840x2160 before concatenation. |
| 8 | Missing State Ledger Output | `get_step_output(run_id, ledger, "animation_generator")` returns `None` | Node verifies step presence, raising `PipelineStageError` with explicit error detailing missing prerequisite step. |
| 9 | Unit Test Execution without Real FFmpeg | Unit tests run in CI/CD environment without system `ffmpeg` binary installed | `VideoAssemblyNode(ffmpeg_binary=str(mock_script))` runs Python mock script, recording CLI flags and verifying string structure. |

---

## 5. Proposed Architecture & Structure for `PromptBook/Phase13/01_Video_Assembly.md`

### Outline & Content Breakdown

```markdown
# Phase 13 Media Production: Video Assembly Architecture & Engineering Specification

## Executive Summary
Overview of Phase 13 positioning in the Synchronous Batch Pipeline architecture, role of VideoAssemblyNode, and media integration goals (4K video + AAC stereo audio + burned-in subtitles).

## Section 1: Executive Overview & Pipeline Architecture
- Synchronous Batch Pipeline positioning.
- State Ledger boundary contract:
  - Input contract: Retrieving `animation_generator` (.mp4 visual clips) & `script_generator`/`voice_generator` (.wav audio clips).
  - Output contract: Registering `AssembledVideo` model payload under step `video_assembly`.

## Section 2: FFmpeg Command Architecture & Filter Graphs
- Video parameters: 4K UHD (3840x2160), 30 fps, H.264 (`libx264`), `yuv420p`, CRF 18, `preset medium`.
- Audio parameters: AAC (`aac`), 384k bitrate, 48 kHz sample rate, stereo.
- Filter Graph specifications:
  - Multi-input video scaling & padding (`scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160...`).
  - Stream concatenation filter (`concat=n=N:v=1:a=0`).
  - Subtitle burn-in filter (`subtitles=...:force_style=...`) and path/character escaping rules.

## Section 3: Secure Subprocess Execution & Resource Management
- `subprocess.run()` security rules (`shell=False`, array list `cmd`, `close_fds=True`).
- Timeout handling & process tree termination.
- Resource sanitation: `tempfile.TemporaryDirectory()`, atomic cleanup of concat manifests & temp `.srt`/`.wav` files.
- Truncated file invalidation (`st_size > 100` bytes check).

## Section 4: Codebase Module Architecture
- `src/assembly/ffmpeg_commands.py`: Pure helper functions for constructing FFmpeg CLI command argument lists.
- `src/assembly/assembler.py`: `VideoAssembler` class encapsulating subprocess invocation & error parsing.
- `src/pipeline/nodes/video_assembly_node.py`: `VideoAssemblyNode` inheriting from `Node`, handling StateLedger IO & executing `VideoAssembler`.

## Section 5: Verification & Unit Testing Strategy
- Matrix of unit tests in `tests/pipeline/test_assembly_node.py`.
- Mock FFmpeg script pattern for isolated CLI string verification.
```
