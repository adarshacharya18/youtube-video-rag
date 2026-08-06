# Project: Video & Audio Subsystems Isolation, Diagnosis, Fix & Testing

## Architecture
- Audio Subsystem: `KokoroVoiceProvider` in `src/core/media/voice.py`, loading ONNX models (`models/kokoro-v1.0.onnx` or `kokoro-v0_19.onnx`) and voice binary archive (`models/voices-v1.0.bin`), generating 24kHz mono PCM voice audio on CPU without 440 Hz beep fallback. [FIXED & VERIFIED]
- Video Subsystem: Manim animation rendering pipeline (`src/animation/scenes/`), ffmpeg filtergraph (`src/assembly/ffmpeg_commands.py`), video validation (`src/pipeline/nodes/animation_generator_node.py` & `src/assembly/assembler.py`), rendering multi-frame moving animations matching visual cue durations. [FIXED & VERIFIED]
- Test Suite: Pytest isolation test files in `tests/test_voice/test_kokoro_voice.py` (R1 - PASSED) and `tests/test_animation/test_manim_animation.py` (R2 - PASSED).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Kokoro TTS Voice Path Fix | Fix `KokoroVoiceProvider` path resolution in `src/core/media/voice.py` to resolve `voices-v1.0.bin` and `kokoro-v1.0.onnx` on CPU | M1 | DONE |
| 2 | Kokoro TTS Isolation Test (R1) | Pytest test file in `tests/test_voice/test_kokoro_voice.py` verifying KokoroVoiceProvider output voice audio on CPU (not synthetic beep) with acoustic analysis | M1 | DONE |
| 3 | Manim Scene Runtime & Motion Fix | Update Manim scene templates in `src/animation/scenes/` to read `duration`, budget keyframe steps, and add continuous motion / updaters | M2 | DONE |
| 4 | FFmpeg Filtergraph & Timestamp Fix | Update `build_4k_scale_filter()` in `src/assembly/ffmpeg_commands.py` to include `fps=fps,setpts=PTS-STARTPTS` and fix `tpad` freeze | M2 | DONE |
| 5 | Deep Video Validation | Upgrade `_is_valid_video_file` in `src/pipeline/nodes/animation_generator_node.py` and `src/assembly/assembler.py` using `ffprobe` to verify `nb_frames > 1` | M2 | DONE |
| 6 | Manim Moving Frame Isolation Test (R2) | Pytest test file in `tests/test_animation/test_manim_animation.py` verifying Manim animation renders moving frames (not single frozen frame) via frame delta MAD analysis | M2 | DONE |
| 7 | E2E Dual Track Testing & Hardening | Comprehensive E2E test suite covering full video and audio subsystems integration | M3 | DONE |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Kokoro TTS Isolation & Fix (R1) | KokoroVoiceProvider path resolution fix + Pytest test file in `tests/test_voice/test_kokoro_voice.py` verifying CPU voice audio | none | DONE |
| 2 | Manim Animation Isolation & Fix (R2) | Manim scene duration/updaters fix, FFmpeg timestamp fix, deep video validation + Pytest test file in `tests/test_animation/test_manim_animation.py` verifying moving frames | none | DONE |
| 3 | E2E Test Suite & Final Hardening | Dual track E2E testing, coverage hardening, and final verification | M1, M2 | DONE |

## Interface Contracts
### Voice ↔ Video / Core Pipeline
- `KokoroVoiceProvider.generate_segment(text, voice, output_path)` -> returns `AudioSegment` with valid 24kHz speech waveform (pause ratio > 5%, RMS energy variance > 50).
- `AnimationGeneratorNode.process(visual_cues)` -> renders MP4 files where `nb_frames > 1` and inter-frame mean absolute difference `mean_diff > 0.05` across rendered frames for requested duration.

## Code Layout
- `tests/test_voice/`: Kokoro TTS isolation test suite (`test_kokoro_voice.py`)
- `tests/test_animation/`: Manim animation isolation test suite (`test_manim_animation.py`)
- `src/core/media/voice.py`: KokoroVoiceProvider implementation
- `src/animation/scenes/`: Manim scene templates
- `src/assembly/ffmpeg_commands.py`: FFmpeg filtergraph construction
- `src/pipeline/nodes/animation_generator_node.py`: Animation generator node & video validation
- `src/assembly/assembler.py`: Video assembler & video validation
