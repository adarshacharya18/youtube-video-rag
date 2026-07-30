# Detailed Design Specifications: `VideoAssemblyNode` (`src/pipeline/nodes/video_assembly_node.py`)

## Executive Summary
This document defines the exact architecture, input/output data flow, error-handling mechanisms, and Python implementation details for `VideoAssemblyNode` in `src/pipeline/nodes/video_assembly_node.py` (Phase 13: Media Production — Video Assembly). 

`VideoAssemblyNode` inherits from the foundational `Node` abstract base class (`src/core/workflow/node.py`), communicates strictly via the SQLite `StateLedger` using `run_id`, retrieves Phase 12 visual animation clips (`animation_generator`) and Phase 11 audio/narration artifacts (`script_generator` / `voice_generator`), instantiates `VideoAssembler` (`src/assembly/assembler.py`) to execute non-shell FFmpeg commands, validates the final artifact against the `AssembledVideo` Pydantic schema (`src/core/models/assets.py`), and raises domain-specific exceptions (`AssemblyError`, `PipelineStageError`) on failures.

---

## 1. Node Architecture & Interface Specifications

### 1.1 Class Contract & Inheritance
- **Module Path**: `src/pipeline/nodes/video_assembly_node.py`
- **Class Name**: `VideoAssemblyNode`
- **Superclass**: `Node` (`src/core/workflow/node.py`)
- **Step Name Identifier**: `@property def name(self) -> str: return "video_assembly"`

```python
from src.core.workflow.node import Node

class VideoAssemblyNode(Node):
    @property
    def name(self) -> str:
        return "video_assembly"
```

### 1.2 Constructor Signature (`__init__`)
```python
def __init__(
    self,
    ffmpeg_binary: Optional[str] = None,
    resolution: str = "3840x2160",
    fps: int = 30,
    crf: int = 18,
    preset: str = "medium",
    output_dir: Optional[Union[str, Path]] = None,
    timeout: float = 300.0,
    temp_dir: Optional[Union[str, Path]] = None,
) -> None
```
- **`ffmpeg_binary`**: Optional custom path or binary name for FFmpeg (allows passing mock binary script ending in `.py` during unit testing).
- **`resolution`**: Output video resolution string (default: `"3840x2160"` for 4K YouTube rendering).
- **`fps`**: Target video frame rate (default: `30`).
- **`crf`**: Constant Rate Factor quality setting (default: `18`).
- **`preset`**: H.264 encoding preset (default: `"medium"`).
- **`output_dir`**: Destination folder for final assembled videos (default: `data/assets/assembled`).
- **`timeout`**: Subprocess wall-clock timeout limit in seconds (default: `300.0`).
- **`temp_dir`**: Custom parent directory for intermediate temporary file operations.

---

## 2. Input Retrieval Protocol & StateLedger Integration

### 2.1 StateLedger Validation & Queries
The node receives `run_id: str` and `ledger: Optional[StateLedger]`.
1. **Ledger Guard**: If `ledger is None`, raise `PipelineStageError("Node 'video_assembly' requires an active StateLedger instance.")`.
2. **Animation Generator Output**:
   - Query: `anim_output = self.get_step_output(run_id, ledger, "animation_generator")`
   - Extracts:
     - `slug`: Problem slug (e.g. `"two-sum"`).
     - `segments`: List of render segment dicts containing `visual_path` or `asset_references`.
   - Validation: If `segments` is missing, empty, or contains no valid existing video file paths, raise `PipelineStageError`.
3. **Audio & Subtitle Artifact Retrieval**:
   - Inspects `completed_steps = ledger.get_completed_steps(run_id)`.
   - If `"voice_generator"` step is present in `completed_steps`:
     - Reads `audio_path` and `subtitle_path`.
   - If `"script_generator"` step is present in `completed_steps`:
     - Reads fallback `audio_path`, `subtitle_path`, or raw SRT `srt_content` string.

---

## 3. Assembly Execution Flow & Exception Mapping

```
[execute(run_id, ledger)]
         |
         v
Check ledger != None (else PipelineStageError)
         |
         v
Retrieve animation_generator step output from ledger
(Raise PipelineStageError if missing or segments empty)
         |
         v
Retrieve audio_path & subtitle_path / srt_content from voice/script step outputs
         |
         v
Prepare run output dir (data/assets/assembled/<run_id>/)
Target: <run_output_dir>/<slug>_assembled.mp4
         |
         v
Instantiate VideoAssembler(ffmpeg_binary, timeout, temp_dir)
         |
         v
Call assembler.assemble(...)
         |
    +----+----+
    |         |
[Success] [AssemblyError / Exception]
    |         |
    v         v
Validate    Catch & re-raise AssemblyError / PipelineStageError
File Size   Ensure intermediate & temp files deleted
>= 100B
    |
    v
Hydrate & Validate AssembledVideo Pydantic Model
    |
    v
Return model.model_dump() payload dict
```

### 3.1 Exception Mapping Matrix

| Failure Trigger | Exception Raised | Context Details Included |
|---|---|---|
| `ledger is None` | `PipelineStageError` | Node name `video_assembly` |
| `animation_generator` step missing in ledger | `PipelineStageError` | Required step name, `run_id` |
| `animation_generator` output has no segments / missing files | `PipelineStageError` | Segment index, invalid path |
| FFmpeg subprocess non-zero exit code | `AssemblyError` | Exit code, stdout/stderr error details |
| FFmpeg subprocess timeout (> 300s) | `AssemblyError` | Timeout duration, trailing stderr |
| Assembled output file missing or < 100B | `AssemblyError` | Target destination path, file size |
| `AssembledVideo` Pydantic validation failure | `AssemblyError` | Pydantic validation error details |

---

## 4. Schema Validation against `AssembledVideo`

Upon successful FFmpeg execution, `VideoAssemblyNode` validates the output dictionary against the `AssembledVideo` schema (`src/core/models/assets.py`):

```python
assembled_model = AssembledVideo(
    slug=slug,
    final_video_path=str(assembled_file),
    total_duration_seconds=total_duration,
    file_size_bytes=file_size_bytes,
    segments=render_segments,
    assembled_at=datetime.utcnow().isoformat(),
)
return assembled_model.model_dump()
```

- **`slug`**: String matching regex `^[a-z0-9-]+$`.
- **`final_video_path`**: Absolute path string to assembled `.mp4`.
- **`total_duration_seconds`**: Positive finite float (> 0.0).
- **`file_size_bytes`**: Integer >= 0.
- **`segments`**: List of valid `RenderSegment` objects.
- **`assembled_at`**: ISO 8601 formatted UTC timestamp string.

---

## 5. Complete Code Implementation for `src/pipeline/nodes/video_assembly_node.py`

```python
"""Video Assembly Workflow Node for Phase 13 Media Production (FFmpeg).

Retrieves visual segments from animation_generator step output and audio/subtitle artifacts
from voice_generator/script_generator prior steps in the StateLedger. Invokes VideoAssembler
to compile them into a 4K video with burned-in subtitles, validates output against AssembledVideo
model, and guarantees explicit cleanup of temporary files.
"""

from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.assembly.assembler import VideoAssembler
from src.core.exceptions import AssemblyError, PipelineStageError
from src.core.models.assets import AssembledVideo, RenderSegment
from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node

logger = logging.getLogger(__name__)


class VideoAssemblyNode(Node):
    """Workflow Engine Node for Phase 13 FFmpeg Video Assembly."""

    def __init__(
        self,
        ffmpeg_binary: Optional[str] = None,
        resolution: str = "3840x2160",
        fps: int = 30,
        crf: int = 18,
        preset: str = "medium",
        output_dir: Optional[Union[str, Path]] = None,
        timeout: float = 300.0,
        temp_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        """Initialize VideoAssemblyNode.

        Args:
            ffmpeg_binary: Optional path or binary name for FFmpeg binary or mock script.
            resolution: Target video resolution string (default: '3840x2160').
            fps: Video framerate (default: 30).
            crf: Constant Rate Factor quality setting (default: 18).
            preset: H.264 encoding preset (default: 'medium').
            output_dir: Destination directory for assembled video artifacts.
            timeout: Wall-clock timeout limit for FFmpeg execution in seconds.
            temp_dir: Custom parent directory for temporary file creation.
        """
        self.ffmpeg_binary = ffmpeg_binary
        self.resolution = resolution
        self.fps = fps
        self.crf = crf
        self.preset = preset
        self.timeout = timeout

        base_dir = Path.cwd()
        self.output_dir = (
            Path(output_dir) if output_dir else base_dir / "data" / "assets" / "assembled"
        )
        self.temp_dir = Path(temp_dir) if temp_dir else None

    @property
    def name(self) -> str:
        """Unique step name identifier in StateLedger."""
        return "video_assembly"

    def execute(self, run_id: str, ledger: Optional[StateLedger] = None) -> Dict[str, Any]:
        """Execute video assembly workflow step for the specified run_id.

        Args:
            run_id: Unique pipeline run identifier.
            ledger: Active StateLedger instance for step input retrieval.

        Returns:
            Dict[str, Any]: Output payload dictionary matching AssembledVideo schema.

        Raises:
            PipelineStageError: If ledger or required input step outputs are missing.
            AssemblyError: If FFmpeg assembly fails, times out, or output artifact is invalid.
        """
        logger.info("Executing VideoAssemblyNode for run_id=%s", run_id)

        if ledger is None:
            raise PipelineStageError(
                f"Node '{self.name}' requires an active StateLedger instance."
            )

        # 1. Retrieve animation_generator output step payload
        anim_output = self.get_step_output(run_id, ledger, "animation_generator")
        slug = anim_output.get("slug", "unknown-slug")
        raw_segments = anim_output.get("segments", [])

        if not raw_segments or not isinstance(raw_segments, list):
            raise PipelineStageError(
                f"Node '{self.name}' found no visual segments in 'animation_generator' output for run '{run_id}'."
            )

        # Extract segment video paths and validated RenderSegment objects
        video_segment_paths: List[Path] = []
        render_segments: List[RenderSegment] = []
        total_duration = 0.0

        for idx, seg_data in enumerate(raw_segments):
            if isinstance(seg_data, dict):
                visual_path = seg_data.get("visual_path")
                if not visual_path and "asset_references" in seg_data:
                    for ref in seg_data["asset_references"]:
                        if isinstance(ref, dict) and ref.get("asset_type") == "video":
                            visual_path = ref.get("file_path")
                            break

                if not visual_path:
                    raise PipelineStageError(
                        f"Segment at index {idx} in 'animation_generator' payload lacks a valid video visual_path."
                    )

                v_path = Path(visual_path)
                if not v_path.exists():
                    raise PipelineStageError(
                        f"Video segment file referenced at index {idx} does not exist: {v_path}"
                    )
                video_segment_paths.append(v_path)

                # Duration tracking
                duration = float(seg_data.get("duration") or 5.0)
                total_duration += duration

                try:
                    seg_model = RenderSegment.model_validate(seg_data)
                    render_segments.append(seg_model)
                except Exception:
                    pass

        if not video_segment_paths:
            raise PipelineStageError(
                f"No valid existing video segment files found in 'animation_generator' output for run '{run_id}'."
            )

        # 2. Retrieve audio and subtitle artifacts (from voice_generator or script_generator)
        audio_path: Optional[Path] = None
        subtitle_path: Optional[Path] = None
        subtitle_text: Optional[str] = None

        completed_steps = ledger.get_completed_steps(run_id)

        # Check voice_generator step if available
        if "voice_generator" in completed_steps:
            voice_output = completed_steps["voice_generator"].output_payload or {}
            raw_audio = voice_output.get("audio_path")
            if raw_audio and Path(raw_audio).exists():
                audio_path = Path(raw_audio)
            raw_sub = voice_output.get("subtitle_path")
            if raw_sub and Path(raw_sub).exists():
                subtitle_path = Path(raw_sub)

        # Fallback to script_generator step
        if "script_generator" in completed_steps:
            script_output = completed_steps["script_generator"].output_payload or {}
            if not audio_path:
                raw_audio = script_output.get("audio_path") or script_output.get("script", {}).get("audio_path")
                if raw_audio and Path(raw_audio).exists():
                    audio_path = Path(raw_audio)
            if not subtitle_path:
                raw_sub = script_output.get("subtitle_path") or script_output.get("script", {}).get("subtitle_path")
                if raw_sub and Path(raw_sub).exists():
                    subtitle_path = Path(raw_sub)
            if not subtitle_path and not subtitle_text:
                srt_str = script_output.get("srt_content") or script_output.get("script", {}).get("srt_content")
                if srt_str and isinstance(srt_str, str):
                    subtitle_text = srt_str

        # 3. Setup output directory & target output video path
        run_output_dir = self.output_dir / run_id
        run_output_dir.mkdir(parents=True, exist_ok=True)
        final_video_path = run_output_dir / f"{slug}_assembled.mp4"

        # 4. Instantiate VideoAssembler & Execute Assembly
        assembler = VideoAssembler(
            ffmpeg_binary=self.ffmpeg_binary,
            timeout=self.timeout,
            temp_dir=self.temp_dir,
        )

        try:
            assembled_file = assembler.assemble(
                video_segments=video_segment_paths,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                subtitle_text=subtitle_text,
                output_path=final_video_path,
                resolution=self.resolution,
                fps=self.fps,
                crf=self.crf,
                preset=self.preset,
            )
        except AssemblyError:
            raise
        except Exception as e:
            logger.error("Unexpected error during video assembly for run_id=%s: %s", run_id, e)
            raise AssemblyError(f"Video assembly failed unexpectedly: {e}") from e

        # 5. Validate Output & Hydrate AssembledVideo Pydantic Model
        if not assembled_file.exists() or assembled_file.stat().st_size < 100:
            raise AssemblyError(
                f"Assembled video artifact missing or corrupted (< 100 bytes) at {assembled_file}"
            )

        file_size = assembled_file.stat().st_size
        assembled_at_str = datetime.utcnow().isoformat()

        try:
            assembled_model = AssembledVideo(
                slug=slug,
                final_video_path=str(assembled_file),
                total_duration_seconds=max(total_duration, 0.1),
                file_size_bytes=file_size,
                segments=render_segments,
                assembled_at=assembled_at_str,
            )
        except Exception as e:
            logger.error("AssembledVideo Pydantic model validation failed: %s", e)
            raise AssemblyError(f"Failed to validate AssembledVideo output schema: {e}") from e

        output_payload = assembled_model.model_dump()
        logger.info(
            "VideoAssemblyNode completed successfully for run_id=%s (file=%s, size=%d bytes)",
            run_id,
            assembled_file,
            file_size,
        )
        return output_payload
```

---

## 6. Verification & Test Plan Matrix

To verify `VideoAssemblyNode` in `tests/pipeline/test_assembly_node.py`:

| Test Case | Scenario Description | Expected Outcome |
|---|---|---|
| `test_node_name()` | Verify `@property name` | Returns `"video_assembly"` |
| `test_missing_ledger()` | Call `execute(run_id, ledger=None)` | Raises `PipelineStageError` |
| `test_missing_animation_step()` | Step `animation_generator` absent in ledger | Raises `PipelineStageError` |
| `test_empty_segments()` | `animation_generator` payload has empty `segments` list | Raises `PipelineStageError` |
| `test_nonexistent_segment_files()` | Segment references `.mp4` path that doesn't exist | Raises `PipelineStageError` |
| `test_successful_assembly()` | Valid segments and mock FFmpeg binary script | Returns dict matching `AssembledVideo` schema |
| `test_assembly_failure()` | Mock FFmpeg binary exits with code 1 | Catches error and raises `AssemblyError` |
| `test_temp_cleanup()` | Check temporary directories after execution | Intermediate files deleted; no lingering temp dirs |

