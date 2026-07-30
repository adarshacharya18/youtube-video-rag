# Handoff Report: Explorer M1-1 (FFmpeg Command Generator Specification)

## 1. Observation
- **Target File**: `src/assembly/ffmpeg_commands.py` (currently an empty 0-byte file created during workspace scaffold).
- **Requirements & Specifications**:
  - `ORIGINAL_REQUEST.md` (Phase 13 section): Specifies combining `.wav` audio artifacts from Phase 11 and `.mp4` Manim artifacts from Phase 12 into a 4K YouTube video with burned-in subtitles.
  - `SCOPE.md` (`.agents/orchestrator_phase13/SCOPE.md`): Mandates pure helper functions in `src/assembly/ffmpeg_commands.py` for 4K rendering, concatenation, audio mixing, and subtitle burning.
  - Prior survey (`.agents/spec_miner_1/spec_analysis.md`): Specifies FFmpeg parameters: 4K UHD (`3840x2160`), 30 FPS (`-r 30`), H.264 video codec (`libx264`), 8-bit YUV420p (`yuv420p`), preset `medium`, CRF `18`, AAC audio codec (`aac`), audio bitrate `384k`, audio sample rate `48000` Hz, and subtitle filter graph escaping rules.
- **Reference Pattern**: `src/animation/renderer.py` lines 57-109 demonstrates non-shell list argument array generation (`List[str]`) for `subprocess.run(cmd, close_fds=True, shell=False)`.

## 2. Logic Chain
1. **Observation 1**: Security and robustness require avoiding shell string invocation (`shell=False`).
   - *Reasoning*: Constructing commands as `List[str]` ensures arguments are passed directly to system `execve()`, preventing shell injection vulnerabilities and avoiding quotes/space splitting issues.
2. **Observation 2**: FFmpeg filter graphs parse strings using internal delimiter syntax (`:`, `'`, `\`, `[`, `]`).
   - *Reasoning*: File paths containing colons (e.g. `/tmp/run:1/sub.srt`) or single quotes will break the FFmpeg `-filter_complex` parser unless explicitly escaped. We designed `escape_ffmpeg_filter_path()` to handle backslashes, colons, single quotes, and square brackets.
3. **Observation 3**: Different input video clips (e.g. Manim animations) may have varying resolutions or aspect ratios.
   - *Reasoning*: `build_4k_scale_filter()` normalizes all video streams to 3840x2160 with `force_original_aspect_ratio=decrease` and letterbox/pillarbox padding (`pad=3840:2160:(ow-iw)/2:(oh-ih)/2,setsar=1`), guaranteeing uniform input to the `concat` filter graph.
4. **Observation 4**: Subtitle burning requires custom typography for 4K display readability.
   - *Reasoning*: `build_subtitle_filter()` provides sensible defaults (`FontName=Sans`, `FontSize=28`, ASS white text with black outline, bottom-center alignment) while allowing caller overrides via `force_style`.
5. **Observation 5**: Separation of concerns requires pure functions with zero I/O side effects.
   - *Reasoning*: `build_assembly_command()` and `build_concat_filter_graph()` perform string and list manipulations only, allowing unit tests to validate CLI arguments without needing a real FFmpeg binary or disk I/O.

## 3. Caveats
- No caveats. The specifications directly cover all required helper functions (`build_assembly_command`, `build_concat_filter_graph`, `build_subtitle_filter`, `build_4k_scale_filter`, `escape_ffmpeg_filter_path`, `build_demuxer_assembly_command`), parameter constraints, escaping rules, and edge cases.

## 4. Conclusion
The detailed design specification and exact code implementation for `src/assembly/ffmpeg_commands.py` have been fully formulated and published to `.agents/explorer_m1_1/analysis.md`. Implementers can adopt the complete PEP 8 and type-annotated code provided in `analysis.md` to populate `src/assembly/ffmpeg_commands.py`.

## 5. Verification Method
To verify the design:
1. Inspect `.agents/explorer_m1_1/analysis.md` for complete API documentation, function signatures, and Python code implementation.
2. Verify function signatures match task requirements:
   - `escape_ffmpeg_filter_path(path: Union[str, Path]) -> str`
   - `build_4k_scale_filter(...) -> str`
   - `build_subtitle_filter(...) -> str`
   - `build_concat_filter_graph(...) -> Tuple[str, str, Optional[str]]`
   - `build_assembly_command(...) -> List[str]`
   - `build_demuxer_assembly_command(...) -> List[str]`
3. Run unit tests once implemented via:
   `pytest tests/pipeline/test_assembly_node.py`
