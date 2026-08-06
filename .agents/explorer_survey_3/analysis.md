# Explorer 3 Analysis Report: Test Harness, Audio (Kokoro TTS) & Video (Manim) Subsystem Integration

## 1. Executive Summary & Problem Diagnosis

This investigation maps the test harness, project structure, and subsystem implementations to diagnose and provide test specifications for requirements **R1** (Audio Generation Isolation Tests) and **R2** (Video Generation Isolation Tests).

### Key Findings & Root Cause Analysis

1. **Audio Generation (Kokoro TTS) Fallback to Beep**:
   - **Observed Behavior**: In `src/core/media/voice.py` line 123-125, `KokoroVoiceProvider._synthesize_pcm_wave()` hardcodes model paths to `Path.cwd() / "models" / "kokoro" / "kokoro-v0_19.onnx"` and `voices.json`.
   - **Root Cause**: `kokoro-onnx` executes `self.voices: np.ndarray = np.load(voices_path)`. When passed `voices.json`, NumPy 2.5 raises `ValueError: Failed to interpret file as a pickle` or `ValueError: This file contains pickled (object) data`. The `try...except` block in `_synthesize_pcm_wave()` catches this failure and silently falls back to generating a 440 Hz pure sine wave synthetic beep.
   - **Verified Fix Location**: Valid model files exist at `/home/adarsh/Documents/Youtube-Channel/models/kokoro-v1.0.onnx` and `/home/adarsh/Documents/Youtube-Channel/models/voices-v1.0.bin`. Calling `Kokoro('models/kokoro-v1.0.onnx', 'models/voices-v1.0.bin')` generates true speech audio (24,000 Hz, mono) without falling back to a beep.

2. **Video Generation (Manim) Animation & Motion Verification**:
   - **Observed Behavior**: `tests/test_animation/` currently contains no isolation tests. `tests/pipeline/test_animation_node.py` uses mock scripts (`mock_manim.py`) that generate static dummy byte strings, without rendering real Manim scenes or verifying video frame motion.
   - **Root Cause**: Absence of isolated tests verifying that real Manim CLI subprocess renders generate moving frames (`mean pixel difference > 0.05`) rather than frozen single-frame outputs.
   - **Verified Solution**: Use `ffmpeg` to extract frames from rendered `.mp4` clips and compute the frame-to-frame pixel delta (Mean Absolute Difference via `Pillow` and `numpy`).

---

## 2. Codebase Structure & Test Harness Mapping

### Project Layout
```
/home/adarsh/Documents/Youtube-Channel/
├── pyproject.toml               # Python 3.10+, pytest >= 8.0.0, pytest-cov
├── pytest.ini                   # Options: --strict-markers --cov=src -v
├── requirements.txt             # kokoro-onnx>=0.5.0, soundfile>=0.14.0, pytest
├── models/
│   ├── kokoro-v1.0.onnx         # Kokoro ONNX model weights (325 MB)
│   └── voices-v1.0.bin          # Kokoro voice embeddings NPZ binary (28.2 MB)
├── src/
│   ├── animation/               # Manim renderer & scene templates
│   │   ├── renderer.py          # ManimRenderer subprocess wrapper
│   │   └── scenes/              # BaseDSAScene, ArrayScene, TreeScene, CodeScene, etc.
│   ├── core/media/
│   │   └── voice.py             # KokoroVoiceProvider, AudioSegment, VoiceConfig
│   └── pipeline/nodes/          # AnimationGeneratorNode, VoiceGeneratorNode
└── tests/
    ├── conftest.py              # Global fixtures (temp_data_dir, test_config, mock_logger)
    ├── test_voice/              # Dedicated directory for R1 (currently empty __init__.py)
    └── test_animation/          # Dedicated directory for R2 (currently empty __init__.py)
```

### System Dependencies Available
- **Python**: 3.13 / 3.10+ virtualenv
- **Pytest**: 9.1.1 (`pytest-cov` installed)
- **Audio Libraries**: `kokoro-onnx`, `soundfile`, standard `wave`, `struct`
- **Video/Graphics Tools**: `manim` CLI (v0.20.1), `ffmpeg`, `PIL` (Pillow 12.3.0), `numpy` (2.5.1)

---

## 3. Requirement R1: Audio Generation (Kokoro TTS) Isolation Test Strategy

### Target File
`tests/test_voice/test_kokoro_voice.py`

### Test Verification Methodology (Real Speech vs. Synthetic Beep)
A 440 Hz synthetic beep is a pure sine wave with:
1. Constant peak amplitude ($1000$) across every single audio frame.
2. Zero silence or pauses between words.
3. Single spectral peak at 440 Hz (harmonic purity = 1.0).

Real Kokoro TTS speech output features:
1. Dynamic amplitude envelope with silence/near-zero amplitude during pauses between words.
2. Dynamic RMS energy variation across phonemes.
3. Spectral energy spread across 100 Hz – 8000 Hz.

#### Practical Audio Assertion Strategy
```python
import wave
import numpy as np

def verify_real_speech_not_beep(wav_path: str):
    """Asserts that WAV file is real TTS speech audio and NOT a synthetic sine beep."""
    with wave.open(wav_path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    assert n_channels == 1, "Expected mono audio"
    assert sampwidth == 2, "Expected 16-bit PCM"
    assert rate == 24000, "Expected 24kHz sample rate"

    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    assert len(samples) > 0, "Audio samples must not be empty"

    # 1. Beep detection via Amplitude Envelope Variance & Zero-count
    # Real speech contains quiet frames/pauses (abs sample < 100)
    quiet_samples = np.sum(np.abs(samples) < 100)
    quiet_ratio = quiet_samples / len(samples)
    assert quiet_ratio > 0.05, f"Audio lacks natural speech pauses (quiet_ratio={quiet_ratio:.4f}), likely synthetic beep"

    # 2. Beep detection via standard deviation of frame energies
    frame_size = 2400 # 100ms frames
    num_frames = len(samples) // frame_size
    if num_frames > 2:
        frame_rms = [
            np.sqrt(np.mean(samples[i * frame_size:(i + 1) * frame_size] ** 2))
            for i in range(num_frames)
        ]
        rms_std = np.std(frame_rms)
        assert rms_std > 50.0, f"Audio energy is too uniform (rms_std={rms_std:.2f}), likely synthetic beep"
```

---

## 4. Requirement R2: Video Generation (Manim) Isolation Test Strategy

### Target File
`tests/test_animation/test_manim_animation.py`

### Test Verification Methodology (Moving Frames vs. Frozen Frame)
If an animation freezes on the first frame, all extracted video frames are identical (pixel delta = 0).
To verify moving frames:
1. Render scene via `ManimRenderer` or Manim CLI (`-ql` quality for fast test execution).
2. Use `ffmpeg` subprocess to extract frames at 5 fps into `tmp_path`.
3. Read frame images using `PIL` (Pillow) and convert to `numpy` arrays.
4. Calculate Mean Absolute Difference (MAD) between Frame 0 and Mid/Final Frame.

#### Practical Video Assertion Strategy
```python
import subprocess
import numpy as np
from PIL import Image
from pathlib import Path

def verify_video_has_moving_frames(mp4_path: Path, tmp_path: Path):
    """Extracts frames from MP4 and asserts that animation renders moving frames."""
    assert mp4_path.exists() and mp4_path.stat().st_size > 100

    frames_dir = tmp_path / "extracted_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Extract 5 frames per second using ffmpeg
    subprocess.run([
        "ffmpeg", "-y", "-i", str(mp4_path),
        "-vf", "fps=5", str(frames_dir / "frame_%03d.png")
    ], capture_output=True, check=True)

    frame_files = sorted(list(frames_dir.glob("frame_*.png")))
    assert len(frame_files) >= 2, f"Expected at least 2 frames, found {len(frame_files)}"

    img_start = np.array(Image.open(frame_files[0]), dtype=np.float32)
    img_mid = np.array(Image.open(frame_files[len(frame_files) // 2]), dtype=np.float32)

    mean_diff = np.mean(np.abs(img_start - img_mid))
    assert mean_diff > 0.05, f"Animation is frozen on first frame! Pixel mean diff={mean_diff:.4f}"
```

---

## 5. Summary of Recommended Test Files Structure

1. `tests/test_voice/test_kokoro_voice.py`:
   - `test_kokoro_voice_provider_cpu_inference`: Verifies KokoroVoiceProvider generates speech without fallback beep using CPU ONNX.
   - `test_kokoro_speech_waveform_non_beep_properties`: Checks RMS variance and silence pauses to confirm speech vs sine wave.
   - `test_kokoro_voice_id_and_speed`: Tests custom voices (`af_sky`, `af_bella`) and speech speed settings.
   - `test_kokoro_technical_pronunciation`: Tests technical jargon replacements (Dijkstra -> dike-struh).

2. `tests/test_animation/test_manim_animation.py`:
   - `test_manim_renderer_array_scene_moving_frames`: Renders ArrayScene and verifies moving frames via frame extraction & pixel delta.
   - `test_manim_renderer_tree_scene_moving_frames`: Renders TreeScene and verifies moving frames.
   - `test_manim_renderer_code_scene_moving_frames`: Renders CodeScene.
   - `test_manim_renderer_quality_flags`: Tests `-ql`, `-qm`, `-qh` flag passed to Manim CLI.
   - `test_manim_renderer_parameters_json_injection`: Verifies custom parameters passed to scenes render correctly.
