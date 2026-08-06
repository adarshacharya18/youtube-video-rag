# Detailed Technical Analysis: Kokoro TTS Audio Subsystem & Beep Fallback Root Cause

**Author**: Explorer 1 (Audio Subsystem Specialist)  
**Date**: 2026-08-06  
**Target Repository**: `/home/adarsh/Documents/Youtube-Channel`

---

## 1. Executive Summary

Audio generation in the pipeline falls back to a continuous synthetic beep (440 Hz sine wave) because `KokoroVoiceProvider` attempts to load `voices.json` using `numpy.load()` inside the `kokoro_onnx` library. 

`models/kokoro/voices.json` is a plain text JSON file containing vector arrays, whereas `kokoro_onnx` requires a `.bin` (numpy `.npz` archive) voice file. When `np.load("voices.json")` is called, numpy raises a `ValueError` (`Failed to interpret file ... as a pickle`). `KokoroVoiceProvider` catches this exception and falls back to generating a synthetic PCM sine wave (440 Hz beep).

Furthermore, a valid model file (`models/kokoro-v1.0.onnx` / `models/kokoro/kokoro-v0_19.onnx`) and voice binary file (`models/voices-v1.0.bin`) **do exist** on the filesystem. When `kokoro_onnx.Kokoro` is configured with `models/voices-v1.0.bin`, voice synthesis executes **100% successfully on CPU** with 24 kHz mono output.

---

## 2. Codebase Investigation & Architecture Findings

### 2.1 Audio Subsystem Components

1. **`src/core/media/voice.py`**:
   - `AudioSegment`: Immutable dataclass for audio metadata (`file_path`, `duration_sec`, `voice_id`, `checksum`).
   - `VoiceConfig`: Dataclass specifying default voice settings (`voice_id="af_sky"`, `sample_rate=24000`, `speed=1.0`).
   - `VoiceProviderProtocol`: Strategy interface defining `generate_segment(text, voice_id, speed, output_path)`.
   - `KokoroVoiceProvider`: Concrete strategy class implementing pronunciation dictionary fixes (`_apply_pronunciation_fixes`), attempt retries (up to 3 times), and PCM wave synthesis (`_synthesize_pcm_wave`).
   - `ManualVoiceProvider`: Fallback strategy expecting human-recorded audio files.

2. **`src/voice/synthesizer.py`**:
   - Backward-compatibility re-export module exposing `KokoroVoiceProvider`, `AudioSegment`, `VoiceConfig`, etc.

3. **`src/pipeline/nodes/voice_generator_node.py`**:
   - Workflow node (`VoiceGeneratorNode`) that receives script narration segments from `StateLedger`, calls `provider.generate_segment(...)`, and outputs `master_audio.wav` and `subtitles.srt`.

4. **`models/` Directory Structure**:
   - `models/kokoro-v1.0.onnx` (311 MB) — Full Kokoro ONNX model v1.0.
   - `models/voices-v1.0.bin` (28.2 MB) — Valid NumPy `.npz` voice embedding archive containing 54 voices (including `af_sky`, `af_bella`, `am_adam`, `bm_george`, etc.).
   - `models/kokoro/kokoro-v0_19.onnx` (311 MB) — Kokoro ONNX model v0.19.
   - `models/kokoro/voices.json` (30.7 MB) — JSON formatted text file containing raw voice vector arrays.
   - `models/kokoro-82m-openvino/` — Empty directory (OpenVINO IR weights absent; `openvino` Python package not installed).

---

## 3. Deep-Dive: Fallback Mechanism & Root Cause Analysis

### 3.1 Synthesis Execution Trace in `src/core/media/voice.py`

In `KokoroVoiceProvider._synthesize_pcm_wave` (lines 120–145):

```python
try:
    from kokoro_onnx import Kokoro
    import soundfile as sf
    
    base_dir = Path.cwd() / "models" / "kokoro"
    model_path = base_dir / "kokoro-v0_19.onnx"
    voices_path = base_dir / "voices.json"
    
    if model_path.exists() and voices_path.exists():
        self._logger.info(f"Using Kokoro ONNX CPU inference for TTS with voice: {voice_id}")
        kokoro = Kokoro(str(model_path), str(voices_path))
        ...
```

### 3.2 Evidence Chain of Failure

1. **Existence Check Passes**:
   - `model_path` (`models/kokoro/kokoro-v0_19.onnx`) exists (`True`).
   - `voices_path` (`models/kokoro/voices.json`) exists (`True`).
   - `model_path.exists() and voices_path.exists()` evaluates to `True`.

2. **Inference Engine Initialization Error**:
   - `Kokoro(str(model_path), str(voices_path))` is invoked.
   - Inside `kokoro_onnx/__init__.py` line 52:
     ```python
     self.voices: np.ndarray = np.load(voices_path)
     ```
   - `numpy.load()` tries to load `voices.json` as a binary `.npy` / `.npz` file.
   - `numpy` raises:
     ```
     ValueError: Failed to interpret file 'models/kokoro/voices.json' as a pickle
     ```

3. **Silent Exception Catching & Beep Fallback**:
   - Line 143 in `src/core/media/voice.py`:
     ```python
     except Exception as e:
         self._logger.error(f"Kokoro ONNX inference failed: {e}. Falling back to beep.")
     ```
   - The code proceeds directly to lines 146–168:
     ```python
     # Fallback Beep Synthesis
     sample_rate = 24000
     ...
     num_samples = int(sample_rate * duration_sec)
     frequency = 440.0
     ...
     for i in range(num_samples):
         sample = int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
         packed_data.extend(struct.pack("<h", sample))
     ```
   - A 440 Hz continuous sine wave is written to the output WAV file.

### 3.3 Why Existing Unit Tests Missed the Issue

Unit tests in `tests/media/test_voice_core.py` and `tests/media/test_voice_stress.py`:
- `test_generate_segment_creates_valid_wav` verifies:
  - File exists and size > 0
  - Duration > 0
  - WAV header channels == 1, sample width == 2, frame rate == 24000
- The fallback beep synthesis generates a valid 16-bit 24kHz mono PCM WAV header and data matching all of these assertions.
- Consequently, 33 out of 36 unit tests **PASS**, masking the fact that no actual voice audio is being generated.

### 3.4 Auxiliary Finding: `test_voice_stress.py` Signature Mismatch
In `tests/media/test_voice_stress.py`, 3 hardware retry stress tests failed because the mock function `mock_synthesize(text, speed, output_path)` accepted 3 arguments, whereas `KokoroVoiceProvider._synthesize_pcm_wave` passes 4 arguments (`text, speed, output_path, voice_id`). Updating `mock_synthesize` signature to accept `*args, **kwargs` or `voice_id` fixes the test suite.

---

## 4. Hardware & CPU Execution Analysis

- **OpenVINO vs ONNX Runtime**:
  - The project specification mentions OpenVINO targeting Intel NPU/CPU.
  - However, `models/kokoro-82m-openvino` is empty and `openvino` Python package is not installed in the environment.
  - `kokoro-onnx` and `onnxruntime` are installed.
  - When initialized with `models/voices-v1.0.bin`, `kokoro_onnx.Kokoro` uses `ONNXRuntime` with `CPUExecutionProvider`.
- **CPU Performance Verification**:
  - Empirical test execution in `.venv`:
    ```python
    kokoro = Kokoro("models/kokoro-v1.0.onnx", "models/voices-v1.0.bin")
    samples, sample_rate = kokoro.create("Hello world", voice="af_sky", speed=1.0)
    ```
  - Result: Audio generated in ~0.3 seconds on CPU. 71,168 samples (2.96 seconds duration) produced perfectly.
  - Available CPU voices: 54 voices available in `voices-v1.0.bin`.

---

## 5. Required Remedies to Ensure CPU Voice Output

1. **Fix Voice & Model File Path Resolution in `KokoroVoiceProvider`**:
   - Update `_synthesize_pcm_wave` path discovery to prioritize `.bin` voice archives:
     - Search path list for voices: `models/voices-v1.0.bin`, `models/kokoro/voices-v1.0.bin`, `models/kokoro/voices.bin`.
     - Search path list for ONNX model: `self.model_path`, `models/kokoro-v1.0.onnx`, `models/kokoro/kokoro-v0_19.onnx`.
   - Use robust absolute path resolution relative to project root (`Path(__file__).resolve().parents[3]`) in addition to `Path.cwd()`.

2. **Fix `test_voice_stress.py` Signature Mismatch**:
   - Update `mock_synthesize` signature in `tests/media/test_voice_stress.py` to `mock_synthesize(text, speed, output_path, voice_id="af_sky")`.

3. **Add Voice Audio Isolation Test File (Requirement R1)**:
   - Create `tests/test_voice/test_kokoro_voice_isolation.py` (or similar under `tests/test_voice/`).
   - Test that `KokoroVoiceProvider` generates voice audio on CPU without falling back to the 440 Hz beep.
   - Verification approach: Check that waveform samples are non-trivial and vary across frames (i.e. spectral energy is distributed rather than a single pure 440 Hz tone), or verify that `kokoro_onnx.Kokoro` model inference completes without exception.

---
