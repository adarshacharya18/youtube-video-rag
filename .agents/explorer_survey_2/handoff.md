# Handoff Report: Voice Production Subsystem Codebase Exploration

## 1. Observation

### Key Codebase Files & Existing Stubs
1. **`src/voice/synthesizer.py`**:
   - Location: `/home/adarsh/Documents/Youtube-Channel/src/voice/synthesizer.py`
   - Content: Empty 0-byte file (stub).
2. **`src/voice/audio_utils.py`**:
   - Location: `/home/adarsh/Documents/Youtube-Channel/src/voice/audio_utils.py`
   - Content: Empty 0-byte file (stub).
3. **`src/models/voice.py`**:
   - Location: `/home/adarsh/Documents/Youtube-Channel/src/models/voice.py`
   - Content: Empty 0-byte file (stub).
4. **`src/core/media/voice.py`**:
   - Location: `/home/adarsh/Documents/Youtube-Channel/src/core/media/voice.py`
   - Content: File does not exist yet. Directory `src/core/media/` is missing.
   - Reference: Referenced in `PromptBook/Phase13/02_Voice_Production.md` and `tests/media/test_media_pipeline.py` (line 12: `from src.core.media.voice import VoiceConfig, AudioSegment`).
5. **`src/pipeline/nodes/voice_generator_node.py`**:
   - Location: `/home/adarsh/Documents/Youtube-Channel/src/pipeline/nodes/voice_generator_node.py` (72 lines)
   - Functionality: Currently raises `VoiceGenerationError` if `data/audio/<slug>/master_audio.wav` is missing on disk. It contains no TTS instantiation or audio synthesis logic.
6. **`PromptBook Specification`**:
   - Location: `/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/02_Voice_Production.md` (172 lines)
   - Architecture: Defines `AudioSegment` dataclass, `VoiceProviderProtocol`, `KokoroVoiceProvider` (with pronunciation dictionary), and `ManualVoiceProvider`.

### Environment & Dependency Inspection
- Python environment: `/home/adarsh/Documents/Youtube-Channel/.venv`
- Tested packages via Python runtime:
  - `kokoro`: Not installed
  - `torch`: Not installed
  - `openvino`: Not installed
  - `pyttsx3`: **Available**
  - `gtts`: **Available**
  - `wave`, `scipy`, `soundfile`, `pydub`, `numpy`: **Available**

### Pipeline Data Passing Mechanics
- **`ScriptGeneratorNode` (`src/pipeline/nodes/script_generator_node.py`)**:
  - Outputs payload: `{"script": script_model.model_dump(), "slug": script_model.slug, "topic": script_model.topic, "status": "completed"}`.
- **`YouTubeScript` Schema (`src/models/script.py`)**:
  - Structure: `hook`, `context`, `solution`, `complexity` (each with `.narration` string and `.estimated_duration` float).
  - Aggregated list: `spoken_narration` (`List[str]`).
- **`PipelineRunner` (`src/core/orchestrator/pipeline_runner.py`)**:
  - Sequence: `IngestionNode` -> `PlanNode` -> `ScriptGeneratorNode` -> `VoiceGeneratorNode` -> `AnimationGeneratorNode` -> `VideoAssemblyNode`.
- **Downstream expectations (`src/pipeline/nodes/video_assembly_node.py`)**:
  - `VideoAssemblyNode` inspects `voice_generator` step output payload for `audio_path`, `subtitle_path`, and `srt_content`.

### Test Suite Baseline
- `tests/pipeline/test_voice_node.py`: Currently 4 unit tests passing when run with `.venv/bin/pytest tests/pipeline/test_voice_node.py`.
- `tests/media/test_media_pipeline.py`: Fails collection due to missing `src.core.media.voice`.

---

## 2. Logic Chain

1. **Strategy Pattern Architecture**:
   - `PromptBook/Phase13/02_Voice_Production.md` specifies a Strategy Pattern where `VoiceProviderProtocol` defines `generate_segment(text, voice_id, speed, output_path) -> AudioSegment`.
   - `KokoroVoiceProvider` and `ManualVoiceProvider` are the concrete providers.
   - Creating `src/core/media/voice.py` with `VoiceConfig`, `AudioSegment`, `VoiceProviderProtocol`, `KokoroVoiceProvider`, and `ManualVoiceProvider` satisfies both specification R1 and the import expectations of `tests/media/test_media_pipeline.py`.

2. **Hardware Resilience & Fallback (CPU execution R3)**:
   - Since `kokoro` and `openvino` packages are not present in `.venv` and CUDA is unavailable, `KokoroVoiceProvider` must fall back gracefully to a CPU-friendly offline TTS engine (e.g. `pyttsx3` or wave-based synthesis) when local ML weights/libraries are absent.
   - This prevents crashes and ensures idempotent generation of non-zero byte `.wav` files on any CPU host.

3. **Pipeline Node Integration (R2)**:
   - `VoiceGeneratorNode.execute(run_id, ledger)` must:
     1. Fetch completed step output from `script_generator` using `self.get_step_output(run_id, ledger, "script_generator")`.
     2. Extract narration text segments from `script` (`spoken_narration` or section narrations: `hook`, `context`, `solution`, `complexity`).
     3. Instantiate the configured voice provider (e.g. `KokoroVoiceProvider`).
     4. Synthesize each segment and combine/concatenate them into `data/audio/<slug>/master_audio.wav`.
     5. Generate subtitle timestamp markers and save `subtitles.srt`.
     6. Calculate total audio duration and return the output dictionary containing `audio_path`, `subtitle_path`, `srt_content`, `duration_seconds`, and `status`.

4. **Test Verification**:
   - Running `python src/cli/ops.py run --slug reorder-list --solution-id 4163684` executes `PipelineRunner`.
   - When `VoiceGeneratorNode` synthesizes `master_audio.wav` (>0 bytes) to `data/audio/reorder-list/`, all acceptance criteria of `ORIGINAL_REQUEST.md` will be fulfilled.

---

## 3. Caveats

- **No Source Modification**: As a read-only Explorer, no source code in `src/` or `tests/` was modified during this survey.
- **Subprocess Dependencies**: `pyttsx3` depends on system `espeak` / `SAPI`. If `espeak` is absent, synthetic raw `.wav` generation using Python's native `wave` module provides a 100% dependency-free CPU fallback for unit test and CLI execution.

---

## 4. Conclusion

The existing voice production code consists of empty stubs (`src/voice/synthesizer.py`, `src/models/voice.py`) and a mock node check (`src/pipeline/nodes/voice_generator_node.py`).
To complete the Voice Production Subsystem:
1. Create `src/core/media/voice.py` implementing `VoiceConfig`, `AudioSegment`, `VoiceProviderProtocol`, `KokoroVoiceProvider` (with CPU fallback), and `ManualVoiceProvider`.
2. Update `src/voice/synthesizer.py` to re-export or alias core strategy classes.
3. Update `src/pipeline/nodes/voice_generator_node.py` to read narration from `script_generator`, synthesize `master_audio.wav` via the voice provider, write `subtitles.srt`, and return metadata.

---

## 5. Verification Method

1. **Unit Tests**:
   - Run `.venv/bin/pytest tests/pipeline/test_voice_node.py`
   - Run `.venv/bin/pytest tests/media/test_media_pipeline.py`
2. **CLI End-to-End Test**:
   - Run `.venv/bin/python src/cli/ops.py run --slug reorder-list --solution-id 4163684`
   - Confirm `data/audio/reorder-list/master_audio.wav` exists and size > 0 bytes.
