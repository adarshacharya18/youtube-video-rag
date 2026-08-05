## 2026-08-05T11:23:44Z
<USER_REQUEST>
You are an Explorer for Milestone 1 (Voice Provider Core Strategy).

Your working directory is: /home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_1

MANDATORY: Read the original user request at /home/adarsh/Documents/Youtube-Channel/.agents/ORIGINAL_REQUEST.md before starting your investigation.
Read the project architecture spec at /home/adarsh/Documents/Youtube-Channel/.agents/orchestrator/PROJECT.md.

Task:
1. Examine PromptBook/Phase13/02_Voice_Production.md and tests/media/test_media_pipeline.py.
2. Formulate the exact implementation specification for src/core/media/voice.py:
   - Data classes: AudioSegment (frozen dataclass: file_path, duration_sec, voice_id, checksum), VoiceConfig (voice_id="af_sky", sample_rate=24000, speed=1.0, pitch=1.0).
   - Protocol: VoiceProviderProtocol with generate_segment(self, text: str, voice_id: str, speed: float = 1.0, output_path: str = "") -> AudioSegment.
   - KokoroVoiceProvider:
     - __init__(self, model_path: str = "", pronunciation_dict: Optional[Dict[str, str]] = None)
     - Default dictionary: {"Dijkstra": "dike-struh", "O(N)": "O of N", "O(N^2)": "O of N squared"}
     - _apply_pronunciation_fixes(self, text: str) -> str
     - Retry logic: up to 3 attempts with hardware exception handling
     - Audio generation logic: CPU-friendly TTS synthesis (using pyttsx3 or python wave/soundfile offline synthesizer if Kokoro model weights are missing or CUDA unavailable) producing valid WAV files.
   - ManualVoiceProvider:
     - generate_segment checking physical file presence at output_path, raising FileNotFoundError if absent.
3. Write your detailed technical recommendation and code design report to /home/adarsh/Documents/Youtube-Channel/.agents/explorer_m1_1/handoff.md following the Handoff Protocol.
4. Message parent with your report path and summary.
</USER_REQUEST>
