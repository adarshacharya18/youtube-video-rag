# Handoff Report: Voice Provider Core Strategy Re-Exports and Import Architecture

**Agent**: `explorer_m1_2`  
**Milestone**: Milestone 1 (Voice Provider Core Strategy)  
**Target Files**: `src/voice/synthesizer.py`, `src/voice/audio_utils.py`, `src/voice/__init__.py`, `src/models/voice.py`  
**Core Source**: `src/core/media/voice.py`  

---

## 1. Observation

Direct examination of the workspace revealed the following file states and import references:

1. **`src/voice/synthesizer.py`**
   - Path: `/home/adarsh/Documents/Youtube-Channel/src/voice/synthesizer.py`
   - Current State: 0 bytes (empty stub).
   - Architectural Contract (`.agents/orchestrator/PROJECT.md` line 6, 18, 38):
     - Line 6: `src/voice/synthesizer.py`: Re-exports core voice definitions for backward compatibility.
     - Line 18 (Feature 7): `Re-export Module` — `src/voice/synthesizer.py` re-exporting core voice definitions.

2. **`src/voice/audio_utils.py` & `src/voice/__init__.py`**
   - Path: `/home/adarsh/Documents/Youtube-Channel/src/voice/audio_utils.py` and `src/voice/__init__.py`
   - Current State: Both files are 0 bytes (empty stubs).
   - Standard Specifications (`PromptBook/04_Folder_Structure.md` line 853):
     - `audio_utils.py`: Audio processing utilities: sample rate validation, silence trimming, WAV export, duration calculation. Pure audio manipulation without TTS inference.

3. **`src/models/voice.py`**
   - Path: `/home/adarsh/Documents/Youtube-Channel/src/models/voice.py`
   - Current State: 0 bytes (empty stub).
   - Standard Specifications (`PromptBook/Phase01/03_Interface_Contracts.md` line 171):
     - References `from src.models.voice import VoiceResult`.

4. **`src/core/media/voice.py`**
   - Path: `/home/adarsh/Documents/Youtube-Channel/src/core/media/voice.py`
   - Current State: Directory `src/core/media` does not exist yet (to be implemented under M1).
   - Specification (`PromptBook/Phase13/02_Voice_Production.md` lines 37-163):
     - Defines dataclasses `AudioSegment` and `VoiceConfig`.
     - Defines protocol `VoiceProviderProtocol` (`generate_segment(...) -> AudioSegment`).
     - Defines concrete classes `KokoroVoiceProvider` and `ManualVoiceProvider`.

5. **Existing Test Suite Observations**
   - `tests/media/test_media_pipeline.py` line 12:
     ```python
     from src.core.media.voice import VoiceConfig, AudioSegment
     ```
     Execution result when running `./.venv/bin/pytest tests/media/test_media_pipeline.py`:
     ```
     ModuleNotFoundError: No module named 'src.core.media'
     ```
   - `tests/pipeline/test_voice_node.py` tests `VoiceGeneratorNode` execution and currently passes (4 tests passed).

---

## 2. Logic Chain

1. **Core Voice Strategy Placement**:
   - Per `PROJECT.md` and Phase 13 architecture, `src/core/media/voice.py` is the canonical location for core data structures (`AudioSegment`, `VoiceConfig`), the strategy interface (`VoiceProviderProtocol`), and concrete providers (`KokoroVoiceProvider`, `ManualVoiceProvider`).

2. **`src/voice/synthesizer.py` Re-Export Requirement**:
   - `src/voice/synthesizer.py` must import all 5 core voice entities from `src.core.media.voice` and re-export them cleanly using `__all__`:
     - `AudioSegment`
     - `VoiceConfig`
     - `VoiceProviderProtocol`
     - `KokoroVoiceProvider`
     - `ManualVoiceProvider`
   - Re-exporting these entities guarantees backward compatibility for any modules or tests importing from `src.voice.synthesizer`.
   - Additionally, providing legacy aliases in `src/voice/synthesizer.py`:
     - `KokoroVoiceSynthesizer = KokoroVoiceProvider`
     - `VoiceSynthesizerProtocol = VoiceProviderProtocol`
     ensures full compatibility with early PromptBook drafts and legacy specifications.

3. **`src/voice/__init__.py` Package Exposure**:
   - Re-exporting all symbols in `src/voice/__init__.py` allows convenient package-level imports (e.g. `from src.voice import KokoroVoiceProvider, AudioSegment`).

4. **`src/voice/audio_utils.py` Design Recommendation**:
   - `audio_utils.py` should serve as a dedicated helper module for pure audio manipulation (decoupled from TTS model inference):
     - `get_audio_duration(file_path: str | Path) -> float`: Calculates `.wav` file duration using Python standard library `wave` module.
     - `validate_wav_file(file_path: str | Path) -> bool`: Verifies existence, non-zero file size (>0 bytes), and valid RIFF/WAVE header structure.
     - `normalize_audio_text(text: str, custom_dict: Optional[Dict[str, str]] = None) -> str`: Converts technical DSA jargon ("Dijkstra" -> "dike-struh", "O(N)" -> "O of N", "O(N^2)" -> "O of N squared") into phonetic equivalents prior to TTS synthesis.

5. **`src/models/voice.py` Compatibility Recommendation**:
   - `src/models/voice.py` should re-export `AudioSegment` and `VoiceConfig` from `src.core.media.voice`.
   - Adding alias `VoiceResult = AudioSegment` satisfies legacy Phase 01 interface contracts (`from src.models.voice import VoiceResult`).

---

## 3. Caveats

1. **Dependency on Core Media Module**:
   - `src/core/media/voice.py` must be written by `implementer_m1_1` first (or concurrently) before the imports in `src/voice/synthesizer.py` and `src/models/voice.py` can be resolved at runtime.
2. **Hardware Environment Constraints**:
   - The host machine runs on an integrated GPU without NVIDIA CUDA. `KokoroVoiceProvider` must handle CPU fallback smoothly and raise `VoiceGenerationError` on audio output failure rather than crashing the process.

---

## 4. Conclusion

We recommend the following exact file implementations for Milestone 1 re-exports and utilities:

### Proposed Implementation 1: `src/voice/synthesizer.py`
```python
"""
Re-export module for voice synthesis components (backward compatibility).

Re-exports core voice data structures, protocols, and providers from `src.core.media.voice`.
"""

from src.core.media.voice import (
    AudioSegment,
    VoiceConfig,
    VoiceProviderProtocol,
    KokoroVoiceProvider,
    ManualVoiceProvider,
)

# Legacy aliases for backwards compatibility with early specifications
KokoroVoiceSynthesizer = KokoroVoiceProvider
VoiceSynthesizerProtocol = VoiceProviderProtocol

__all__ = [
    "AudioSegment",
    "VoiceConfig",
    "VoiceProviderProtocol",
    "KokoroVoiceProvider",
    "ManualVoiceProvider",
    "KokoroVoiceSynthesizer",
    "VoiceSynthesizerProtocol",
]
```

### Proposed Implementation 2: `src/voice/__init__.py`
```python
"""
Voice production subsystem package.
"""

from src.voice.synthesizer import (
    AudioSegment,
    VoiceConfig,
    VoiceProviderProtocol,
    KokoroVoiceProvider,
    ManualVoiceProvider,
)

__all__ = [
    "AudioSegment",
    "VoiceConfig",
    "VoiceProviderProtocol",
    "KokoroVoiceProvider",
    "ManualVoiceProvider",
]
```

### Proposed Implementation 3: `src/voice/audio_utils.py`
```python
"""
Audio Processing Utilities.

Pure audio manipulation helpers: duration calculation, WAV validation,
and phonetic text normalization for TTS synthesis.
"""

import wave
from pathlib import Path
from typing import Dict, Optional

DEFAULT_PRONUNCIATION_DICT: Dict[str, str] = {
    "Dijkstra": "dike-struh",
    "O(N)": "O of N",
    "O(N^2)": "O of N squared",
    "O(1)": "O of 1",
    "O(log N)": "O of log N",
    "O(N log N)": "O of N log N",
}


def get_audio_duration(file_path: str | Path) -> float:
    """Calculates exact duration in seconds of a WAV audio file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        if rate == 0:
            return 0.0
        return frames / float(rate)


def validate_wav_file(file_path: str | Path) -> bool:
    """Validates if a file exists, is non-empty, and is a valid WAV audio file."""
    path = Path(file_path)
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with wave.open(str(path), "rb") as wav_file:
            return wav_file.getnframes() > 0
    except Exception:
        return False


def normalize_audio_text(text: str, custom_dict: Optional[Dict[str, str]] = None) -> str:
    """Sanitizes technical DSA jargon into phonetic equivalents for speech synthesis."""
    mapping = {**DEFAULT_PRONUNCIATION_DICT, **(custom_dict or {})}
    normalized = text
    for word, phonetic in mapping.items():
        normalized = normalized.replace(word, phonetic)
    return normalized
```

### Proposed Implementation 4: `src/models/voice.py`
```python
"""
Voice data models re-export module.

Re-exports core voice dataclasses from `src.core.media.voice` for data model layer compatibility.
"""

from src.core.media.voice import AudioSegment, VoiceConfig

# Legacy alias for Phase 01 interface contracts
VoiceResult = AudioSegment

__all__ = [
    "AudioSegment",
    "VoiceConfig",
    "VoiceResult",
]
```

---

## 5. Verification Method

To verify these re-exports and utilities independently once implemented:

1. **Verify Python Import Paths**:
   ```bash
   ./.venv/bin/python3 -c "from src.voice.synthesizer import AudioSegment, VoiceConfig, VoiceProviderProtocol, KokoroVoiceProvider, ManualVoiceProvider; print('Synthesizer re-exports OK')"
   ./.venv/bin/python3 -c "from src.voice import KokoroVoiceProvider, AudioSegment; print('Package re-exports OK')"
   ./.venv/bin/python3 -c "from src.models.voice import AudioSegment, VoiceConfig, VoiceResult; print('Models re-exports OK')"
   ./.venv/bin/python3 -c "from src.voice.audio_utils import get_audio_duration, validate_wav_file, normalize_audio_text; print('Audio utils OK')"
   ```

2. **Execute Pytest Unit Test Suite**:
   ```bash
   ./.venv/bin/pytest tests/media/test_media_pipeline.py tests/pipeline/test_voice_node.py
   ```
   *Expected Result*: All tests pass with 0 errors and 0 missing module exceptions.
