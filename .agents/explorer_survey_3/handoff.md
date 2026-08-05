# Environment & Dependency Investigation Report: Voice Production Subsystem

**Author:** Environment & Dependency Explorer (`explorer_survey_3`)  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Working Directory:** `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_survey_3`  
**Date:** 2026-08-05  

---

## 1. Observation

### System Hardware & Environment
- **Host Architecture:** Linux `6.17.0-41-generic #41-Ubuntu SMP PREEMPT_DYNAMIC` (x86_64).
- **GPU Setup:** Integrated GPU (Intel / CPU-only execution without dedicated NVIDIA CUDA hardware).
- **Python Runtime:** Python `3.13.7` located at `/home/adarsh/Documents/Youtube-Channel/.venv/bin/python`.
- **Package Manager:** `uv` installed at `/home/adarsh/.local/bin/uv`.
- **System Binaries:**
  - FFmpeg: `/usr/bin/ffmpeg` version `7.1.1-1ubuntu4.2`.
  - eSpeak: System binary `/usr/bin/espeak` is not installed; phonemization is handled by the Python package `espeakng-loader` (v0.2.4).

### Dependency & Package Audit
- **Project Files Inspected:**
  - `requirements.txt`: Core dependencies (`pydantic`, `structlog`, `langchain`, `openai`, `anthropic`, `pytest`). No TTS dependencies were specified in `requirements.txt`.
  - `pyproject.toml`: Configured for `requires-python = ">=3.10"`.
  - `.env`: Contains `GEMINI_API_KEY`, `LEETCODE_SESSION`, and `YOUTUBE_CLIENT_SECRETS_PATH`. No TTS keys required.
- **Installed & Tested Python Packages (`.venv`):**
  - `kokoro-onnx` (v0.5.0): Installed and operational.
  - `onnxruntime` (v1.28.0): Installed and operational.
  - `soundfile` (v0.14.0): Installed and operational.
  - `pydub` (v0.25.1) + `audioop-lts` (v0.2.2): Installed and operational (resolves Python 3.13 standard `audioop` removal).
  - `scipy` (v1.18.0): Installed and operational.
  - `av` (v18.0.0): PyAV installed and operational.
  - `srt` (v3.5.3): Installed and operational.
  - `edge-tts` (v7.2.8): Installed and operational.
  - `pyttsx3` (v2.99): Installed and operational.
  - `gtts` (v2.5.4): Installed and operational.

### Model Weight Assets
- Model weights downloaded and stored under `/home/adarsh/Documents/Youtube-Channel/models/`:
  - `models/kokoro-v1.0.onnx`: 325,532,387 bytes (311 MB).
  - `models/voices-v1.0.bin`: 28,214,398 bytes (27 MB).

### Operational Benchmark Results
- **Kokoro ONNX Engine Test (`.venv/bin/python`):**
  - Initialization Time: **1.25s**
  - Text: `"Dijkstra algorithm calculates the shortest path in a weighted graph efficiently."`
  - Voice Model: `af_bella` (24,000 Hz)
  - Audio Length Generated: **4.86 seconds** (233,516 bytes WAV file written to `/tmp/test_kokoro_onnx.wav`)
  - Execution Time: **2.30s**
  - Real-Time Factor (RTF): **0.473** (Faster than real-time on CPU, 0 CUDA calls, 0 segfaults).
  - Available Voices (54 total): `af_bella`, `af_sarah`, `af_heart`, `am_adam`, `am_michael`, `bf_emma`, `bm_george`, etc.
- **Edge-TTS Engine Test (`.venv/bin/python`):**
  - Generated MP3: 31,968 bytes in **1.4s** using voice `en-US-ChristopherNeural`.
  - Pydub WAV Export: Successfully converted to 5.33s mono WAV at 24,000 Hz.
- **Pyttsx3 Engine Test (`.venv/bin/python`):**
  - Generated offline eSpeak WAV: 93,224 bytes in **0.08s**.
- **Audio Concatenation Test (`pydub` & `soundfile`):**
  - Concatenation of multiple audio segments with silence gap pauses (e.g. 300ms) succeeded without clipping or format mismatch errors.

---

## 2. Logic Chain

1. **Host Constraint Assessment:**
   - *Observation:* Host runs on Linux x86_64 without dedicated NVIDIA CUDA hardware.
   - *Deduction:* PyTorch-based TTS inference (`torch.cuda`) would either fail with `AssertionError: Torch not compiled with CUDA enabled`, segfault, or require massive PyTorch CUDA wheels (>2GB) running inefficiently on CPU.
   - *Solution:* ONNX Runtime (`onnxruntime`) utilizes CPU C++ SIMD vectorization (AVX2/AVX512), eliminating GPU driver/CUDA runtime dependencies while achieving superior CPU performance.

2. **Python 3.13 Compatibility:**
   - *Observation:* Python 3.13 removed the built-in `audioop` C module, which traditional audio libraries like `pydub` depend on.
   - *Verification:* `audioop-lts` (v0.2.2) is installed in `.venv`. Importing `pydub` and performing `AudioSegment` manipulations succeeded without `ModuleNotFoundError: No module named 'audioop'`.

3. **Local Neural TTS vs Cloud & Offline Fallbacks:**
   - *Primary Strategy:* `KokoroVoiceProvider` using `kokoro-onnx` + `onnxruntime` + `models/kokoro-v1.0.onnx`. It achieves high-quality neural voice synthesis completely offline on CPU with RTF 0.473.
   - *Secondary Strategy (Cloud Fallback):* `EdgeTTSVoiceProvider` using `edge-tts`. Zero local model footprint, excellent Microsoft Edge neural voices (`en-US-ChristopherNeural`, `en-US-GuyNeural`), very fast network synthesis.
   - *Tertiary Strategy (Offline Fallback):* `Pyttsx3VoiceProvider` using `pyttsx3`. 100% offline emergency fallback if network is unavailable and model files are missing.
   - *Manual Override:* `ManualVoiceProvider` reads existing human-recorded `.wav` files as defined in `PromptBook/Phase13/02_Voice_Production.md`.

4. **Audio Assembly & Export Reliability:**
   - *Observation:* FFmpeg 7.1.1 is available at `/usr/bin/ffmpeg`. `soundfile` and `pydub` can read/write 24kHz 16-bit PCM `.wav` format files directly.
   - *Conclusion:* Concatenation of voice segments with inter-segment silence padding (e.g., 300ms) for Manim visual synchronization can be performed reliably without missing native dependencies.

---

## 3. Caveats

1. **Network Dependency for Edge-TTS:** `edge-tts` requires outbound HTTPS internet access to Microsoft's TTS service. If the environment loses internet connectivity, synthesis must fallback to local `kokoro-onnx` or `pyttsx3`.
2. **Model Weight Locations:** `kokoro-onnx` relies on local model files (`models/kokoro-v1.0.onnx` and `models/voices-v1.0.bin`). These files (~338 MB combined) are present in the workspace `models/` directory. If moved or deleted, the initialization code should automatically download them from GitHub release assets (`thewh1teagle/kokoro-onnx`).
3. **Pronunciation Sanitization:** Technical DSA terms (e.g. `Dijkstra`, `O(N)`, `O(N^2)`) require preprocessing via `pronunciation_dict` (e.g., `"Dijkstra" -> "dike-struh"`) before text is fed to any TTS engine.

---

## 4. Conclusion

- **Optimal TTS Provider Strategy:**
  1. **Default / Production Engine:** `KokoroVoiceProvider` powered by `kokoro-onnx` (`models/kokoro-v1.0.onnx` & `models/voices-v1.0.bin`).
  2. **Secondary Fallback:** `EdgeTTSVoiceProvider` (`edge-tts` with `en-US-ChristopherNeural` or `en-US-GuyNeural`).
  3. **Tertiary Offline Fallback:** `Pyttsx3VoiceProvider` (`pyttsx3`).
  4. **Manual Voice Provider:** `ManualVoiceProvider` for human voice override.
- **Audio Output Standard:** 24,000 Hz mono 16-bit PCM `.wav` format, concatenated via `pydub` or `soundfile` with customizable silence padding.
- **Hardware Resiliency:** Tested on CPU without CUDA. RTF is ~0.473 (synthesis takes ~2.3 seconds for 4.86 seconds of audio).

---

## 5. Verification Method

To independently verify the operational status of the Voice Production environment, run the following commands:

```bash
# 1. Verify python environment and audio dependencies
.venv/bin/python -c "import kokoro_onnx, soundfile, pydub, scipy, edge_tts, pyttsx3; print('All TTS & audio dependencies imported successfully!')"

# 2. Verify kokoro-onnx CPU synthesis
.venv/bin/python -c "
from kokoro_onnx import Kokoro
import soundfile as sf
kokoro = Kokoro('models/kokoro-v1.0.onnx', 'models/voices-v1.0.bin')
samples, rate = kokoro.create('Testing Kokoro ONNX CPU verification.', voice='af_bella')
sf.write('/tmp/verify_kokoro.wav', samples, rate)
print('Verified Kokoro ONNX sample generated at /tmp/verify_kokoro.wav')
"

# 3. Verify Edge-TTS cloud synthesis
.venv/bin/python -c "
import asyncio, edge_tts
asyncio.run(edge_tts.Communicate('Testing Edge TTS verification.', 'en-US-ChristopherNeural').save('/tmp/verify_edge.mp3'))
print('Verified Edge-TTS sample generated at /tmp/verify_edge.mp3')
"
```
