## 2026-08-06T05:12:20Z

Develop isolated, step-by-step tests for the video generation (Manim) and audio generation (Kokoro TTS) subsystems to diagnose and fix the issue where animations freeze on the first frame and audio falls back to a continuous beep.

Requirements:
- R1. Audio Generation (Kokoro TTS) Isolation Tests: Pytest test file in tests/test_voice/ verifying KokoroVoiceProvider output voice audio on CPU (not synthetic beep).
- R2. Video Generation (Manim) Isolation Tests: Pytest test file in tests/test_animation/ verifying Manim animation renders moving frames (not single frozen frame).
