## 2026-08-05T11:25:16Z
You are the Implementer Worker for Milestone 1 (Voice Provider Core Strategy).

Your working directory is: /home/adarsh/Documents/Youtube-Channel/.agents/worker_m1_1

MANDATORY INTEGRITY WARNING: DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY: Read the original user request at /home/adarsh/Documents/Youtube-Channel/.agents/ORIGINAL_REQUEST.md before starting work.
Read project specification at /home/adarsh/Documents/Youtube-Channel/.agents/orchestrator/PROJECT.md.
Read explorer findings at /home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_1/handoff.md.

Task:
1. Implement src/core/media/voice.py:
   - AudioSegment: frozen dataclass (file_path: str, duration_sec: float, voice_id: str, checksum: str)
   - VoiceConfig: dataclass (voice_id: str = "af_sky", sample_rate: int = 24000, speed: float = 1.0, pitch: float = 1.0)
   - VoiceProviderProtocol: typing.Protocol with method signature generate_segment(self, text: str, voice_id: str, speed: float = 1.0, output_path: str = "") -> AudioSegment
   - KokoroVoiceProvider:
     - __init__(self, model_path: str = "", pronunciation_dict: Optional[Dict[str, str]] = None)
     - Default pronunciation dictionary: {"Dijkstra": "dike-struh", "O(N)": "O of N", "O(N^2)": "O of N squared"}
     - _apply_pronunciation_fixes(self, text: str) -> str
     - Up to 3 retries on hardware/synthesis failure
     - CPU audio synthesis generating valid 16-bit PCM WAV (24000 Hz sample rate, mono) using stdlib `wave` and `struct` or installed audio libraries (`soundfile`/`scipy`/`numpy`/`pyttsx3`), calculating actual audio duration and SHA-256 checksum. Ensures parent directories exist.
   - ManualVoiceProvider:
     - generate_segment checking physical file presence at output_path, raising FileNotFoundError if absent.
2. Implement src/voice/synthesizer.py:
   - Import and re-export AudioSegment, VoiceConfig, VoiceProviderProtocol, KokoroVoiceProvider, ManualVoiceProvider from src.core.media.voice.
3. Run build and tests:
   - Run `pytest tests/media/test_media_pipeline.py -v` (or run pytest across test directories) to verify imports and execution pass.
4. Document commands run, build/test results, and modified files in /home/adarsh/Documents/Youtube-Channel/.agents/worker_m1_1/handoff.md following the Handoff Protocol.
5. Message parent with your handoff report path and summary of completed work.
