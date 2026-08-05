# Project: Voice Production Subsystem (TTS Integration)

## Architecture
The Voice Production Subsystem provides text-to-speech synthesis for the automated DSA educational video pipeline.
- `src/core/media/voice.py`: Defines core data structures (`AudioSegment`, `VoiceConfig`), strategy protocol (`VoiceProviderProtocol`), and concrete providers (`KokoroVoiceProvider` with CPU fallback, `ManualVoiceProvider`).
- `src/voice/synthesizer.py`: Re-exports core voice definitions for backward compatibility.
- `src/pipeline/nodes/voice_generator_node.py`: Workflow pipeline node that retrieves generated script from `StateLedger`, synthesizes narration into `data/audio/{slug}/master_audio.wav`, and records output payload in `StateLedger`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | `AudioSegment` Dataclass | Immutable dataclass tracking file_path, duration_sec, voice_id, checksum | M1 | Survey (PromptBook 02_Voice_Production.md:43) |
| 2 | `VoiceConfig` Dataclass | Configuration settings for voice synthesis (voice_id, sample_rate, speed, pitch) | M1 | Survey (PromptBook 04_08:86) |
| 3 | `VoiceProviderProtocol` Interface | Strategy pattern protocol defining `generate_segment(...) -> AudioSegment` | M1 | Survey (PromptBook 02_Voice_Production.md:51) |
| 4 | Phonetic Fixer Helper | Converts DSA terms ("Dijkstra", "O(N)", "O(N^2)") to phonetic strings | M1 | Survey (PromptBook 02_Voice_Production.md:92) |
| 5 | `KokoroVoiceProvider` | CPU-friendly TTS provider with hardware retries and fallback mechanism | M1 | Survey (PromptBook 02_Voice_Production.md:73) |
| 6 | `ManualVoiceProvider` | Human voice actor fallback provider verifying disk file presence | M1 | Survey (PromptBook 02_Voice_Production.md:130) |
| 7 | Re-export Module | `src/voice/synthesizer.py` re-exporting core voice definitions | M1 | Survey (ORIGINAL_REQUEST.md:20) |
| 8 | `VoiceGeneratorNode` Update | Pipeline node invoking provider, synthesizing `master_audio.wav` from script | M2 | Survey (src/pipeline/nodes/voice_generator_node.py:17) |
| 9 | Master Audio Post-Processing | Normalizes volume and writes valid WAV master file to `data/audio/{slug}/master_audio.wav` | M2 | Survey (PromptBook 03_Audio_Post_Processing.md) |
| 10 | Unit & E2E Verification | Pytest unit test execution and CLI ops run pipeline execution (`reorder-list`) | M3 | Survey (ORIGINAL_REQUEST.md:31-36) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Voice Provider Core Strategy | Implement `src/core/media/voice.py` (`AudioSegment`, `VoiceConfig`, `VoiceProviderProtocol`, `KokoroVoiceProvider`, `ManualVoiceProvider`) and `src/voice/synthesizer.py` re-exports | None | DONE |
| M2 | Pipeline Node Integration | Update `src/pipeline/nodes/voice_generator_node.py` to extract script, synthesize audio, and output `master_audio.wav` | M1 | DONE |
| M3 | End-to-End Verification & Testing | Run unit tests (`tests/pipeline/test_voice_node.py`, `tests/media/test_media_pipeline.py`) and verify CLI ops run pipeline execution | M2 | DONE |

## Interface Contracts
### `src/core/media/voice.py` ↔ `VoiceGeneratorNode`
- `AudioSegment(file_path: str, duration_sec: float, voice_id: str, checksum: str)`
- `VoiceProviderProtocol.generate_segment(text: str, voice_id: str, speed: float = 1.0, output_path: str = "") -> AudioSegment`
- Exception handling: `VoiceGenerationError` raised on synthesis failure.

## Code Layout
- `src/core/media/voice.py`: Core dataclasses, protocol, and provider implementations.
- `src/voice/synthesizer.py`: Re-export stub for compatibility.
- `src/pipeline/nodes/voice_generator_node.py`: Pipeline node implementation.
- `tests/media/test_media_pipeline.py`: Unit tests for media pipeline and voice providers.
- `tests/pipeline/test_voice_node.py`: Unit tests for VoiceGeneratorNode.
