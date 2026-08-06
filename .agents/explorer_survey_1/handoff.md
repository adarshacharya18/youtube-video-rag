# Handoff Report — Explorer 1 (Audio Subsystem Specialist)

## 1. Observation

1. **Failure Observation in `src/core/media/voice.py`**:
   - File: `/home/adarsh/Documents/Youtube-Channel/src/core/media/voice.py`
   - Line numbers 123–125:
     ```python
     base_dir = Path.cwd() / "models" / "kokoro"
     model_path = base_dir / "kokoro-v0_19.onnx"
     voices_path = base_dir / "voices.json"
     ```
   - Verbatim exception log when attempting `Kokoro(str(model_path), str(voices_path))` via `.venv/bin/python`:
     ```
     ValueError: Failed to interpret file 'models/kokoro/voices.json' as a pickle
     ```
   - Verbatim code lines 143–167 in `src/core/media/voice.py`:
     ```python
     except Exception as e:
         self._logger.error(f"Kokoro ONNX inference failed: {e}. Falling back to beep.")
     
     # Fallback Beep Synthesis
     sample_rate = 24000
     ...
     frequency = 440.0
     ...
     ```

2. **Filesystem Observations in `models/`**:
   - `models/kokoro/voices.json` (size: 30,789,387 bytes) header starts with `b'{"af": [[[-0.2652...` — a JSON text file.
   - `models/voices-v1.0.bin` (size: 28,214,398 bytes) is a valid NumPy `.npz` archive loaded by `np.load(allow_pickle=True)`.
   - `models/kokoro-v1.0.onnx` (size: 326,128,103 bytes) and `models/kokoro/kokoro-v0_19.onnx` (size: 326,128,103 bytes) exist locally.
   - `models/kokoro-82m-openvino/` is empty and `openvino` package is not installed in `.venv`.

3. **Empirical CPU Execution Result**:
   - Running `.venv/bin/python`:
     ```python
     from kokoro_onnx import Kokoro
     kokoro = Kokoro("models/kokoro-v1.0.onnx", "models/voices-v1.0.bin")
     samples, sample_rate = kokoro.create("Hello world! Voice synthesis working on CPU.", voice="af_sky", speed=1.0)
     ```
   - Command Output: `Kokoro initialized successfully! Audio generated! Samples shape: (71168,) Sample rate: 24000`.

4. **Test Suite Behavior**:
   - Running `.venv/bin/pytest tests/media/test_voice_core.py tests/media/test_voice_stress.py` results in `33 PASSED, 3 FAILED`.
   - The 33 passing tests check basic WAV header attributes (mono, 16-bit, 24kHz), which the fallback 440 Hz sine wave synthesis satisfies.
   - The 3 failing tests in `test_voice_stress.py` failed due to a mock signature mismatch (`mock_synthesize` takes 3 args instead of 4).

---

## 2. Logic Chain

1. **Observation 1 & 2** show that `KokoroVoiceProvider` targets `models/kokoro/voices.json` for ONNX voice inference.
2. `kokoro_onnx.Kokoro.__init__` executes `np.load(voices_path)`. Passing a JSON file to `np.load()` triggers a `ValueError`.
3. **Observation 1** shows that `KokoroVoiceProvider` catches all exceptions during ONNX model initialization and executes fallback sine wave synthesis generating a 440 Hz beep.
4. **Observation 3** proves that when `voices-v1.0.bin` is passed to `kokoro_onnx.Kokoro`, CPU voice generation succeeds without errors.
5. **Observation 4** explains why unit tests pass: tests check basic PCM WAV format properties that both real speech and synthetic beeps satisfy.
6. **Conclusion**: To ensure `KokoroVoiceProvider` outputs voice audio on CPU, `KokoroVoiceProvider` must point to `models/voices-v1.0.bin` (or search for `.bin` voice archives relative to project root) instead of `voices.json`. Additionally, an isolated test file (`tests/test_voice/test_kokoro_voice_isolation.py`) must be added to verify real CPU voice output (R1 requirement).

---

## 3. Caveats

- **OpenVINO vs ONNX Runtime**: Documentation mentions OpenVINO targeting NPU/CPU, but OpenVINO models/packages are not installed. `onnxruntime` CPU execution via `kokoro-onnx` is fully functional and takes ~0.3s per sentence on CPU.
- **Path Resolution**: `Path.cwd()` assumes execution from project root. Robust resolution should include `Path(__file__).resolve().parents[...}`.

---

## 4. Conclusion

The audio fallback to a synthetic beep is caused by passing `voices.json` instead of `voices-v1.0.bin` to `kokoro_onnx.Kokoro`, causing `np.load()` to fail and trigger the 440 Hz fallback generator.

To resolve:
1. Update `KokoroVoiceProvider` in `src/core/media/voice.py` to resolve voice model paths using `voices-v1.0.bin` and `kokoro-v1.0.onnx` (or `kokoro-v0_19.onnx`).
2. Update mock signature in `tests/media/test_voice_stress.py` to accept 4 arguments (`text, speed, output_path, voice_id`).
3. Add `tests/test_voice/test_kokoro_voice_isolation.py` (or similar Pytest file) ensuring Kokoro outputs real speech on CPU.

---

## 5. Verification Method

1. **Inspect Code**:
   - Check `src/core/media/voice.py` lines 120–145 to verify path resolution for `voices-v1.0.bin` and `kokoro-v1.0.onnx`.
2. **Run Python Inference**:
   ```bash
   .venv/bin/python -c "from src.core.media.voice import KokoroVoiceProvider; p = KokoroVoiceProvider(); seg = p.generate_segment('Testing real voice synthesis', 'af_sky', output_path='/tmp/test_voice.wav'); print(seg)"
   ```
3. **Run Isolation Test**:
   ```bash
   .venv/bin/pytest tests/test_voice/
   ```
4. **Invalidation Condition**: If `generate_segment` produces a file containing constant 440 Hz frequency or if `np.load` fails, verification fails.
