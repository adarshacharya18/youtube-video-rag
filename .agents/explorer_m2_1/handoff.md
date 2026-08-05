# Handoff Report: Pipeline Node Integration — VoiceGeneratorNode (Milestone 2)

**Agent:** `explorer_m2_1` (Explorer Agent)  
**Working Directory:** `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_m2_1`  
**Target Files:** `src/pipeline/nodes/voice_generator_node.py`, `tests/pipeline/test_voice_node.py`  
**Status:** Completed (Technical Investigation & Implementation Specification)  

---

## 1. Observation

1. **Current Node Implementation Analysis (`src/pipeline/nodes/voice_generator_node.py`):**
   - The current `VoiceGeneratorNode` is a stub implementation (lines 17–71).
   - In `execute()`:
     ```python
     if not audio_file.exists():
         raise VoiceGenerationError(
             f"TTS audio synthesis failed for slug '{slug}': master audio file was not found at {audio_file}"
         )
     ```
   - It expects `master_audio.wav` to already exist on disk. It does NOT invoke any voice synthesis engine or retrieve upstream script outputs from `StateLedger`.

2. **Upstream Script Node Payload Structure (`src/pipeline/nodes/script_generator_node.py` & `src/models/script.py`):**
   - `ScriptGeneratorNode.execute()` records output dictionary containing:
     ```python
     {
         "script": script_model.model_dump(),  # YouTubeScript schema
         "slug": script_model.slug,
         "topic": script_model.topic,
         "status": "completed",
     }
     ```
   - `YouTubeScript` contains `spoken_narration` (a `List[str]` consisting of `[hook.narration, context.narration, solution.narration, complexity.narration]`).

3. **Voice Provider Capabilities (`src/core/media/voice.py`):**
   - `VoiceProviderProtocol`: Protocol with `generate_segment(text: str, voice_id: str, speed: float = 1.0, output_path: str = "") -> AudioSegment`.
   - `KokoroVoiceProvider`: Concrete CPU-friendly voice synthesizer. Generates 16-bit PCM WAV audio at 24000 Hz sample rate, creates output directories automatically, applies phonetic fixes (`Dijkstra`, `O(N)`), calculates SHA-256 checksum and audio duration, and handles up to 3 hardware retries before raising `VoiceGenerationError`.

4. **Base Node Execution Pattern (`src/core/workflow/node.py`):**
   - `Node.get_run_record(run_id, ledger)` returns `PipelineRunRecord` with `slug`.
   - `ledger.get_completed_steps(run_id)` returns a dictionary of completed step names mapped to `PipelineStepRecord`.

---

## 2. Logic Chain

1. **Upstream Data Retrieval & Narration Extraction:**
   - `VoiceGeneratorNode` checks `StateLedger.get_completed_steps(run_id)` for `"script_generator"`.
   - If present, it extracts `script_payload`.
   - It parses `YouTubeScript` or fallback dict keys (`hook`, `context`, `solution`, `complexity`) to extract spoken narration blocks as a list of strings (`narration_segments`).
   - If no upstream script output is available and `master_audio.wav` is missing, it raises `VoiceGenerationError` explaining the missing synthesis prerequisites.

2. **Voice Synthesis Execution:**
   - Instantiates `KokoroVoiceProvider` (or a passed `VoiceProviderProtocol` instance).
   - Combines narration text segments (`combined_text = " ".join(narration_segments)`).
   - Resolves base directory (`data/audio/{slug}`) and output file path (`data/audio/{slug}/master_audio.wav`).
   - Invokes `provider.generate_segment(text=combined_text, voice_id=self.voice_id, speed=self.speed, output_path=str(audio_file))`.
   - Ensures output directory exists prior to synthesis and catches any provider/hardware synthesis exceptions, wrapping them cleanly into `VoiceGenerationError`.

3. **SRT Subtitle Generation:**
   - Computes character ratio per narration segment relative to `total_duration_sec`.
   - Formats start and end timestamps into standard SRT format (`HH:MM:SS,mmm`).
   - Writes `subtitles.srt` to `data/audio/{slug}/subtitles.srt`.

4. **StateLedger Output Contract:**
   - Returns payload dict matching workflow contract:
     ```python
     {
         "slug": slug,
         "audio_path": str(audio_file.resolve()),
         "subtitle_path": str(sub_file.resolve()) if sub_file.exists() else "",
         "srt_content": srt_content,
         "duration_seconds": duration_sec,
         "status": "completed",
     }
     ```

---

## 3. Caveats

- **Host GPU Constraints:** Host machine operates without CUDA GPU acceleration. All voice synthesis must rely on `KokoroVoiceProvider` CPU PCM WAV generation.
- **Standalone Node Testing Compatibility:** When running in standalone mode or in pre-existing test fixtures where `master_audio.wav` is manually placed without an upstream `script_generator` step in `StateLedger`, the node checks for pre-existing audio files before throwing `VoiceGenerationError`.

---

## 4. Conclusion

### Proposed Code for `src/pipeline/nodes/voice_generator_node.py`

```python
"""Voice Generator / TTS Workflow Node (Phase 08 / Phase 13).

Synthesizes audio narration and generates subtitle alignment artifacts.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.core.exceptions import PipelineStageError, VoiceGenerationError
from src.core.media.voice import AudioSegment, KokoroVoiceProvider, VoiceProviderProtocol
from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node
from src.models.script import YouTubeScript

logger = logging.getLogger(__name__)


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp format (HH:MM:SS,mmm)."""
    seconds = max(0.0, seconds)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        total_seconds = int(seconds) + 1
        millis = 0
    else:
        total_seconds = int(seconds)
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    mins = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"


class VoiceGeneratorNode(Node):
    """Workflow Engine Node for Phase 08 / 13 TTS & Voice Synthesis."""

    def __init__(
        self,
        output_dir: Optional[Union[str, Path]] = None,
        provider: Optional[VoiceProviderProtocol] = None,
        voice_id: str = "af_sky",
        speed: float = 1.0,
    ) -> None:
        self.output_dir = Path(output_dir) if output_dir else None
        self.provider: VoiceProviderProtocol = provider if provider is not None else KokoroVoiceProvider()
        self.voice_id = voice_id
        self.speed = speed

    @property
    def name(self) -> str:
        """Unique step name identifier in StateLedger."""
        return "voice_generator"

    def execute(self, run_id: str, ledger: Optional[StateLedger] = None) -> Dict[str, Any]:
        """Execute voice generation TTS step for the specified run_id.

        Args:
            run_id: Unique pipeline run identifier.
            ledger: Active StateLedger instance.

        Returns:
            Dict[str, Any]: Audio and subtitle artifact payload recorded in StateLedger.

        Raises:
            PipelineStageError: If ledger is missing.
            VoiceGenerationError: If audio synthesis fails or output is missing.
        """
        if ledger is None:
            raise PipelineStageError(f"Node '{self.name}' requires a valid StateLedger instance.")

        run_record = self.get_run_record(run_id, ledger)
        slug = run_record.slug

        logger.info("Executing VoiceGeneratorNode for slug=%s (run_id=%s)", slug, run_id)

        base_dir = self.output_dir if self.output_dir else Path("data/audio") / slug
        base_dir.mkdir(parents=True, exist_ok=True)

        audio_file = base_dir / "master_audio.wav"
        sub_file = base_dir / "subtitles.srt"

        # 1. Retrieve script_generator output payload from ledger
        completed_steps = ledger.get_completed_steps(run_id)
        script_payload: Optional[Dict[str, Any]] = None
        if "script_generator" in completed_steps:
            script_payload = completed_steps["script_generator"].output_payload or {}

        narration_segments: List[str] = []
        if script_payload:
            narration_segments = self._extract_narration_segments(script_payload)

        # 2. Execute Voice Synthesis
        duration_sec = 10.0
        if narration_segments:
            combined_text = " ".join(narration_segments)
            try:
                segment: AudioSegment = self.provider.generate_segment(
                    text=combined_text,
                    voice_id=self.voice_id,
                    speed=self.speed,
                    output_path=str(audio_file),
                )
                duration_sec = segment.duration_sec
            except VoiceGenerationError:
                raise
            except Exception as e:
                logger.error("TTS synthesis error for slug '%s': %s", slug, e)
                raise VoiceGenerationError(f"TTS audio synthesis failed for slug '{slug}': {e}") from e
        elif not audio_file.exists():
            raise VoiceGenerationError(
                f"TTS audio synthesis failed for slug '{slug}': master audio file was not found at {audio_file} "
                f"and no upstream script_generator output was present in StateLedger."
            )

        if not audio_file.exists() or audio_file.stat().st_size == 0:
            raise VoiceGenerationError(
                f"TTS audio synthesis failed for slug '{slug}': master audio file was not found or zero-byte at {audio_file}"
            )

        # 3. Subtitle / SRT Generation
        srt_content = ""
        if narration_segments:
            srt_content = self._generate_srt_content(narration_segments, duration_sec)
            sub_file.write_text(srt_content, encoding="utf-8")
        elif sub_file.exists():
            srt_content = sub_file.read_text(encoding="utf-8")

        return {
            "slug": slug,
            "audio_path": str(audio_file.resolve()),
            "subtitle_path": str(sub_file.resolve()) if sub_file.exists() else "",
            "srt_content": srt_content,
            "duration_seconds": duration_sec,
            "status": "completed",
        }

    def _extract_narration_segments(self, script_payload: Dict[str, Any]) -> List[str]:
        """Extract list of spoken narration text segments from script payload or YouTubeScript."""
        script_data = script_payload.get("script")
        narration_list: List[str] = []

        if isinstance(script_data, dict):
            try:
                script_model = YouTubeScript.model_validate(script_data)
                narration_list = [s for s in script_model.spoken_narration if s and s.strip()]
            except Exception:
                for key in ("hook", "context", "solution", "complexity"):
                    sec = script_data.get(key)
                    if isinstance(sec, dict) and "narration" in sec and isinstance(sec["narration"], str):
                        txt = sec["narration"].strip()
                        if txt:
                            narration_list.append(txt)
        elif isinstance(script_data, YouTubeScript):
            narration_list = [s for s in script_data.spoken_narration if s and s.strip()]

        if not narration_list and "spoken_narration" in script_payload:
            raw_sp = script_payload["spoken_narration"]
            if isinstance(raw_sp, list):
                narration_list = [str(s).strip() for s in raw_sp if str(s).strip()]

        return narration_list

    def _generate_srt_content(self, segments: List[str], total_duration: float) -> str:
        """Format list of narration segments into valid SRT subtitle string."""
        total_chars = sum(len(s) for s in segments)
        if total_chars == 0:
            total_chars = 1

        current_time = 0.0
        srt_entries: List[str] = []

        for idx, text in enumerate(segments, start=1):
            char_ratio = len(text) / total_chars
            seg_duration = char_ratio * total_duration
            start_t = current_time
            end_t = total_duration if idx == len(segments) else start_t + seg_duration

            start_str = format_srt_timestamp(start_t)
            end_str = format_srt_timestamp(end_t)

            srt_entries.append(f"{idx}\n{start_str} --> {end_str}\n{text.strip()}\n")
            current_time = end_t

        return "\n".join(srt_entries)
```

---

## 5. Verification Method

1. **Unit Testing:**
   Run the pytest test suite for voice core and pipeline voice node:
   ```bash
   .venv/bin/pytest tests/pipeline/test_voice_node.py tests/media/test_voice_core.py -v
   ```

2. **Pipeline CLI Verification:**
   Run the pipeline CLI ops runner:
   ```bash
   python src/cli/ops.py run --slug reorder-list --solution-id 4163684
   ```
   Verify that:
   - The execution passes `voice_generator` node without errors.
   - `data/audio/reorder-list/master_audio.wav` is generated and has size > 0 bytes.
   - `data/audio/reorder-list/subtitles.srt` is created with valid SRT timestamps.
