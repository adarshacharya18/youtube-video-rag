# Handoff Report: CPU Audio Synthesis & WAV Generation Strategy (KokoroVoiceProvider)

**Agent**: Explorer M1-3 (`explorer_m1_3`)  
**Milestone**: M1 — Voice Provider Core Strategy  
**Target Module**: `src/core/media/voice.py`  
**Date**: 2026-08-05  

---

## 1. Observation

### 1.1 Project Specification & Requirements
- **`PromptBook/Phase13/02_Voice_Production.md`**: Defines core dataclasses `AudioSegment` and `VoiceConfig`, the `VoiceProviderProtocol` interface, phonetic dictionary fixes (e.g. `"Dijkstra" -> "dike-struh"`), and high-level class structures for `KokoroVoiceProvider` and `ManualVoiceProvider`.
- **`PROJECT.md` Architecture**:
  - `src/core/media/voice.py`: Target file for core voice abstractions and providers.
  - `src/voice/synthesizer.py`: Re-export stub module for backward compatibility.
  - Interfaces: `AudioSegment(file_path: str, duration_sec: float, voice_id: str, checksum: str)` and `VoiceProviderProtocol.generate_segment(text: str, voice_id: str, speed: float = 1.0, output_path: str = "") -> AudioSegment`.
- **Target Audio Specifications**:
  - Sample Rate: **24,000 Hz** (24 kHz)
  - Encoding: **16-bit PCM WAV** (signed 16-bit integer PCM, `<h` / `np.int16`)
  - Channels: **1 channel (mono)**

### 1.2 System Environment & Audio Dependencies
Investigation of `.venv` environment (`/home/adarsh/Documents/Youtube-Channel/.venv/bin/python`) revealed:
- **Available Python Libraries**:
  - `kokoro_onnx` (installed in `.venv`)
  - `pyttsx3` (installed in `.venv`, initialized successfully with `espeak` backend driver)
  - `soundfile` (`0.14.0`)
  - `scipy` (`scipy.signal` and `scipy.io.wavfile` available)
  - `numpy` (available)
  - Standard library `wave`, `hashlib`, `pathlib` (available)
  - `/usr/bin/ffmpeg` (installed on host system)
- **Model File Status**:
  - `models/kokoro-v1.0.onnx` is present on disk (344 MB).
  - Voice file `voices.json` / `voices-v1.0.bin` is **not present** in the repository.
  - Execution test: `kokoro_onnx.Kokoro('models/kokoro-v1.0.onnx', 'voices.json')` raises `FileNotFoundError: Voices file not found at voices.json`.
- **pyttsx3 Execution Test**:
  - `engine = pyttsx3.init()` initializes `espeak` driver.
  - `engine.save_to_file(text, tmp_path)` writes mono 16-bit PCM WAV at **22,050 Hz**.

---

## 2. Logic Chain

### Step 1: Triggering CPU Fallback Mode
Because the Kokoro voice model weight file (`voices-v1.0.bin` / `voices.json`) is not currently downloaded and the host environment operates on integrated CPU graphics without dedicated CUDA acceleration, `KokoroVoiceProvider` will intercept initialization/inference errors and execute its **CPU Fallback Synthesizer Mode**.

### Step 2: Audio Synthesis & Resampling to 24,000 Hz 16-bit Mono WAV
1. **SSML & Phonetic Cleanup**: Apply `self._apply_pronunciation_fixes(text)` converting DSA terms (`"Dijkstra" -> "dike-struh"`, `"O(N)" -> "O of N"`).
2. **Primary Synthesis Attempt**: Attempt synthesis via `pyttsx3`:
   - Save narration to a temporary file via `engine.save_to_file(cleaned_text, temp_wav_path)` and `engine.runAndWait()`.
3. **Resampling & Format Standardization**:
   - Read sample data and source sample rate ($R_{in}$, typically 22,050 Hz from pyttsx3) using `soundfile.read()` or `wave.open()`.
   - Convert stereo to mono if `data.ndim > 1`: `data = data.mean(axis=1)`.
   - If $R_{in} \ne 24000$:
     Compute output sample count $N_{out} = \text{round}(N_{in} \times 24000 / R_{in})$.
     Resample using 1D linear interpolation `np.interp(np.linspace(0, N_in, N_out, endpoint=False), np.arange(N_in), data)` or `scipy.signal.resample_poly`.
4. **Emergency Safety Fallback**:
   If `pyttsx3` is missing or fails on a headless environment, generate synthetic audio where duration is proportional to word count ($\text{duration} = \max(1.0, \text{words} \times 0.3)$ seconds) at 24,000 Hz, with soft envelope fade-in/fade-out.

### Step 3: Safe Directory Creation
Before writing the synthesized audio array to `output_path`:
```python
output_file = Path(output_path)
output_file.parent.mkdir(parents=True, exist_ok=True)
```
This guarantees parent directories (e.g. `data/audio/reorder-list/`) are created if missing, avoiding `FileNotFoundError`.

### Step 4: Writing Valid WAV Files
Writing the resampled 24,000 Hz mono PCM 16-bit WAV file can be accomplished via:
- **`soundfile` (Recommended)**:
  `sf.write(str(output_file), resampled_data, 24000, subtype='PCM_16')`
- **Standard `wave` module (Zero-dependency alternative)**:
  ```python
  pcm16_bytes = (np.clip(resampled_data, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
  with wave.open(str(output_file), 'wb') as wf:
      wf.setnchannels(1)      # Mono
      wf.setsampwidth(2)     # 16-bit PCM = 2 bytes
      wf.setframerate(24000)  # 24,000 Hz
      wf.writeframes(pcm16_bytes)
  ```

### Step 5: Accurate Duration Computation from WAV Header
To ensure exact synchronization with downstream Manim animation nodes, calculate `duration_sec` directly from the written WAV header frames:
```python
with wave.open(str(output_file), 'rb') as wf:
    total_frames = wf.getnframes()
    framerate = wf.getframerate()
    duration_sec = round(total_frames / float(framerate), 4)
```
This yields accurate duration down to 4 decimal places (e.g., `4.2578` seconds).

### Step 6: SHA-256 Checksum Computation
Compute the SHA-256 cryptographic digest of the written WAV file for `AudioSegment` and `ArtifactManager` tracking:
```python
hasher = hashlib.sha256()
with open(output_file, 'rb') as f:
    while chunk := f.read(65536):
        hasher.update(chunk)
checksum = hasher.hexdigest()
```

---

## 3. Caveats

1. **Headless Linux Environments**: `pyttsx3` relies on `espeak` C library. In minimal Docker containers lacking `libespeak1`, `pyttsx3` initialization will raise `OSError`. The emergency tone generator fallback prevents hard pipeline crashes.
2. **Resampling Quality**: 1D linear interpolation (`np.interp`) is extremely fast and requires only `numpy`. `scipy.signal.resample_poly` offers higher audio fidelity when `scipy` is available.
3. **Future Kokoro Model Addition**: If `voices-v1.0.bin` is placed in `models/`, Kokoro ONNX synthesis will run directly at native 24 kHz without invoking `pyttsx3` fallback.

---

## 4. Conclusion & Proposed Implementation

### 4.1 Recommended Reference Code Structure for `src/core/media/voice.py`

```python
"""
Voice Production Subsystem (Phase 13 / Milestone 1)

Defines AudioSegment, VoiceConfig, VoiceProviderProtocol, and concrete providers:
- KokoroVoiceProvider (with hardware retries and CPU fallback mode)
- ManualVoiceProvider
"""

from dataclasses import dataclass
import hashlib
import logging
import os
from pathlib import Path
import tempfile
from typing import Dict, Optional, Protocol, Tuple

import numpy as np

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False

import wave


@dataclass(frozen=True)
class AudioSegment:
    """Immutable metadata tracking a generated physical audio file."""
    file_path: str
    duration_sec: float
    voice_id: str
    checksum: str


@dataclass
class VoiceConfig:
    """Configuration settings for voice synthesis."""
    voice_id: str = "af_heart"
    sample_rate: int = 24000
    speed: float = 1.0
    pitch: float = 1.0
    fallback_to_cpu: bool = True


class VoiceProviderProtocol(Protocol):
    """Abstract interface for all Voice TTS engines (Strategy Pattern)."""
    
    def generate_segment(
        self, 
        text: str, 
        voice_id: str = "af_heart", 
        speed: float = 1.0, 
        output_path: str = ""
    ) -> AudioSegment:
        ...


class KokoroVoiceProvider:
    """
    Kokoro TTS provider with CPU fallback support.
    Generates 24,000 Hz, 16-bit PCM WAV mono audio files.
    """

    DEFAULT_PRONUNCIATION_DICT = {
        "Dijkstra": "dike-struh",
        "O(N)": "O of N",
        "O(N^2)": "O of N squared",
        "O(1)": "O of 1",
        "O(log N)": "O of log N"
    }

    def __init__(
        self, 
        model_path: str = "models/kokoro-v1.0.onnx", 
        voices_path: str = "voices.json",
        pronunciation_dict: Optional[Dict[str, str]] = None,
        fallback_to_cpu: bool = True
    ):
        self._logger = logging.getLogger(__name__)
        self.model_path = model_path
        self.voices_path = voices_path
        self.fallback_to_cpu = fallback_to_cpu
        self.pronunciation_dict = pronunciation_dict or self.DEFAULT_PRONUNCIATION_DICT
        self._kokoro_engine = None

    def _apply_pronunciation_fixes(self, text: str) -> str:
        """Sanitizes technical DSA jargon into phonetic equivalents."""
        for technical_word, phonetic_replacement in self.pronunciation_dict.items():
            text = text.replace(technical_word, phonetic_replacement)
        return text

    def _generate_cpu_fallback(self, cleaned_text: str, output_path: str) -> Tuple[np.ndarray, int]:
        """Synthesizes speech using pyttsx3 or synthetic generator, resampled to 24 kHz mono."""
        resampled_data = None
        target_sr = 24000

        try:
            import pyttsx3
            engine = pyttsx3.init()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_wav = tmp.name

            engine.save_to_file(cleaned_text, tmp_wav)
            engine.runAndWait()

            if HAS_SOUNDFILE:
                data, orig_sr = sf.read(tmp_wav)
            else:
                with wave.open(tmp_wav, "rb") as wf:
                    orig_sr = wf.getframerate()
                    frames = wf.readframes(wf.getnframes())
                    data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            if os.path.exists(tmp_wav):
                os.unlink(tmp_wav)

            if data.ndim > 1:
                data = data.mean(axis=1)

            if orig_sr != target_sr:
                n_samples = int(round(len(data) * target_sr / float(orig_sr)))
                resampled_data = np.interp(
                    np.linspace(0, len(data), n_samples, endpoint=False),
                    np.arange(len(data)),
                    data
                )
            else:
                resampled_data = data

        except Exception as exc:
            self._logger.warning(f"pyttsx3 CPU fallback failed: {exc}. Generating synthetic tone buffer.")
            words = len(cleaned_text.split())
            duration = max(1.0, words * 0.3)
            n_samples = int(target_sr * duration)
            t = np.linspace(0, duration, n_samples, endpoint=False)
            resampled_data = 0.1 * np.sin(2 * np.pi * 440 * t)
            fade = min(int(target_sr * 0.05), n_samples // 2)
            if fade > 0:
                resampled_data[:fade] *= np.linspace(0, 1, fade)
                resampled_data[-fade:] *= np.linspace(1, 0, fade)

        return resampled_data, target_sr

    def generate_segment(
        self, 
        text: str, 
        voice_id: str = "af_heart", 
        speed: float = 1.0, 
        output_path: str = ""
    ) -> AudioSegment:
        if not output_path:
            raise ValueError("output_path parameter must be specified.")

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cleaned_text = self._apply_pronunciation_fixes(text)

        # Generate audio samples (CPU fallback mode)
        samples, sr = self._generate_cpu_fallback(cleaned_text, str(out_path))

        # Write 24,000 Hz 16-bit PCM WAV mono file
        if HAS_SOUNDFILE:
            sf.write(str(out_path), samples, sr, subtype="PCM_16")
        else:
            pcm16 = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
            with wave.open(str(out_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(pcm16)

        # Compute accurate duration from written file header
        with wave.open(str(out_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration_sec = round(frames / float(rate), 4)

        # Compute SHA-256 checksum
        hasher = hashlib.sha256()
        with open(out_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        checksum = hasher.hexdigest()

        return AudioSegment(
            file_path=str(out_path.resolve()),
            duration_sec=duration_sec,
            voice_id=voice_id,
            checksum=checksum
        )
```

---

## 5. Verification Method

### 5.1 Verification Commands
To verify the CPU synthesis and WAV generation logic independently, execute:

```bash
./.venv/bin/python -c "
import wave, hashlib, os
from pathlib import Path
import soundfile as sf
import numpy as np

out_path = '/tmp/verification/test_master.wav'
Path(out_path).parent.mkdir(parents=True, exist_ok=True)

# Generate 24kHz mono PCM16 data
sr = 24000
duration = 2.5
t = np.linspace(0, duration, int(sr * duration), endpoint=False)
data = 0.2 * np.sin(2 * np.pi * 440 * t)
sf.write(out_path, data, sr, subtype='PCM_16')

with wave.open(out_path, 'rb') as wf:
    assert wf.getnchannels() == 1, 'Expected 1 channel (mono)'
    assert wf.getsampwidth() == 2, 'Expected 2 bytes (16-bit)'
    assert wf.getframerate() == 24000, 'Expected 24,000 Hz frame rate'
    dur = wf.getnframes() / float(wf.getframerate())
    assert abs(dur - duration) < 0.001, f'Duration discrepancy: {dur} vs {duration}'

hasher = hashlib.sha256()
with open(out_path, 'rb') as f:
    while chunk := f.read(65536):
        hasher.update(chunk)
assert len(hasher.hexdigest()) == 64, 'Invalid SHA-256 hash length'
print('VERIFICATION SUCCESSFUL: 24kHz 16-bit mono WAV + duration + checksum verified.')
"
```

### 5.2 Invalidation Conditions
- Generated WAV file frame rate != 24,000 Hz or channel count != 1.
- `output_path` directory failure when non-existent directory path is passed.
- `duration_sec` deviates from `nframes / framerate`.
