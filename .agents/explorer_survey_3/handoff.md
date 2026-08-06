# Handoff Report: Explorer 3 — Test Harness & Integration Exploration

## 1. Observation

- **ORIGINAL_REQUEST Requirements**:
  - R1: Pytest test file under `tests/test_voice/` verifying `KokoroVoiceProvider` output voice audio on CPU (not synthetic beep).
  - R2: Pytest test file under `tests/test_animation/` verifying Manim animation renders moving frames (not single frozen frame).
- **Codebase Mapping**:
  - `src/core/media/voice.py` lines 123-125:
    ```python
    base_dir = Path.cwd() / "models" / "kokoro"
    model_path = base_dir / "kokoro-v0_19.onnx"
    voices_path = base_dir / "voices.json"
    ```
  - When running `Kokoro(str(model_path), str(voices_path))` with `models/kokoro/voices.json`, `kokoro-onnx` raises:
    `ValueError: Failed to interpret file PosixPath('models/kokoro/voices.json') as a pickle` or `ValueError: This file contains pickled (object) data.`
  - Valid models exist in repository root:
    - `/home/adarsh/Documents/Youtube-Channel/models/kokoro-v1.0.onnx` (325,525,180 bytes)
    - `/home/adarsh/Documents/Youtube-Channel/models/voices-v1.0.bin` (28,214,398 bytes)
  - Python execution command tested:
    `Kokoro('models/kokoro-v1.0.onnx', 'models/voices-v1.0.bin')` successfully synthesized 53,248 samples of speech at 24,000 Hz (mono) without falling back to a synthetic beep.
- **Existing Test Suite State**:
  - `tests/test_voice/__init__.py` and `tests/test_animation/__init__.py` exist, but contain no actual pytest test files (`test_*.py`).
  - `tests/media/test_voice_core.py` tests WAV headers and output existence, but does not distinguish real TTS speech from synthetic 440 Hz sine wave beeps.
  - Manim CLI v0.20.1 and `ffmpeg` CLI are both fully installed and functional in the environment. `python3 -m manim render -ql src/animation/scenes/array_scene.py ArrayScene` rendered `media/videos/array_scene/480p15/ArrayScene.mp4`.
  - Frame extraction via `ffmpeg` and pixel delta calculation (`Mean Absolute Difference`) on `ArrayScene.mp4` yielded `mean pixel diff = 1.9812` between Frame 0 and Frame 5, proving motion.

---

## 2. Logic Chain

1. **Observation**: `KokoroVoiceProvider._synthesize_pcm_wave()` hardcodes `models/kokoro/voices.json` which causes `np.load()` inside `kokoro-onnx` to fail with `ValueError`.
2. **Observation**: The `except Exception:` block in `_synthesize_pcm_wave()` catches this failure and silently falls back to generating a 440 Hz sine wave beep.
3. **Logic Step**: To satisfy R1, `KokoroVoiceProvider` should use valid model/voice files (`models/kokoro-v1.0.onnx` and `models/voices-v1.0.bin`), and `tests/test_voice/test_kokoro_voice.py` must include acoustic waveform assertions (pause ratio and energy variance) to guarantee output is real human speech and not a pure sine beep.
4. **Observation**: Existing animation tests (`tests/pipeline/test_animation_node.py`) use dummy file writer scripts (`mock_manim.py`) which bypass Manim rendering entirely.
5. **Observation**: Manim CLI and `ffmpeg` are available. Extracting frames with `ffmpeg` and comparing early frames vs mid/late frames using `numpy` and `PIL` yields a non-zero pixel difference (`diff > 0.05`) for moving animations vs `diff == 0` for frozen frames.
6. **Logic Step**: To satisfy R2, `tests/test_animation/test_manim_animation.py` must execute real Manim scene renders and run `ffmpeg` + `numpy` frame difference assertions to prove animations contain moving frames.

---

## 3. Caveats

- Real Kokoro TTS inference on CPU takes ~1-3 seconds per sentence. Isolation tests for R1 should use short phrases (e.g. 5-10 words) to keep pytest execution time under ~5 seconds.
- Real Manim scene rendering at high quality (`-qh`) takes 5-10 seconds per scene. Isolation tests for R2 should use low quality (`-ql` / 480p15) and short 1-2 second scene animations to optimize test run duration.

---

## 4. Conclusion

- **Audio Subsystem (R1)**: Root cause of synthetic beep fallback identified as invalid path / JSON voice file passed to `kokoro-onnx`. Tests in `tests/test_voice/test_kokoro_voice.py` can conclusively verify real voice audio on CPU using pause ratio (`quiet_ratio > 0.05`) and RMS energy variance (`rms_std > 50.0`).
- **Video Subsystem (R2)**: Test strategy for `tests/test_animation/test_manim_animation.py` verified using Manim CLI `-ql` renders and `ffmpeg` frame extraction + `numpy` mean pixel difference (`mean_diff > 0.05`) to verify moving frames.

---

## 5. Verification Method

To independently verify findings:

1. **Verify Kokoro TTS ONNX Model Execution**:
   ```bash
   python3 -c "
   from kokoro_onnx import Kokoro
   k = Kokoro('models/kokoro-v1.0.onnx', 'models/voices-v1.0.bin')
   samples, sr = k.create('Testing speech', voice='af_sky')
   print('Samples count:', len(samples), 'Sample rate:', sr)
   "
   ```
   *Expected result*: `Samples count: > 20000`, `Sample rate: 24000`.

2. **Verify Manim Rendering and Motion Analysis**:
   ```bash
   python3 -m manim render -ql src/animation/scenes/array_scene.py ArrayScene
   ```
   *Expected result*: Rendered MP4 output file created at `media/videos/array_scene/480p15/ArrayScene.mp4`.
