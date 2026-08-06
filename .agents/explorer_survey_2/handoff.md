# Handoff Report: Manim Video Subsystem & Animation Freeze Diagnosis

## 1. Observation

### Codebase Observations
1. **Scene Templates Runtimes (`src/animation/scenes/`)**:
   - `ArrayScene` (`src/animation/scenes/array_scene.py:32-33`):
     ```python
     self.play(manim.Create(array_group))
     self.wait(1)
     ```
   - `CodeScene` (`src/animation/scenes/code_scene.py:27-28`):
     ```python
     self.play(manim.Create(code_block))
     self.wait(1)
     ```
   - `TreeScene` (`src/animation/scenes/tree_scene.py:20-21`):
     ```python
     self.play(manim.Create(node))
     self.wait(1)
     ```
   - `LinkedListScene` (`src/animation/scenes/linkedlist_scene.py:29-30`):
     ```python
     self.play(manim.Create(chain))
     self.wait(1)
     ```
   - `GraphScene` (`src/animation/scenes/graph_scene.py:20-21`), `HashmapScene` (`src/animation/scenes/hashmap_scene.py:27-28`), `StackQueueScene` (`src/animation/scenes/stack_queue_scene.py:26-27`), `ComplexityScene` (`src/animation/scenes/complexity_scene.py:25-26`): All execute a single `Create()` (or `Write()`) animation (1.0s) followed by `self.wait(1)`.
   - **Parameter Discrepancy**: `AnimationGeneratorNode` (`src/pipeline/nodes/animation_generator_node.py:190`) extracts `duration = float(parameters.get("duration") or 5.0)`. None of the scene templates read or budget against `duration`.

2. **FFmpeg Concatenation & Image Cloning (`src/assembly/ffmpeg_commands.py`)**:
   - `build_concat_filter_graph()` (`src/assembly/ffmpeg_commands.py:168`):
     ```python
     if num_audio_inputs > 0:
         clauses.append(f"[{current_v_label}]tpad=stop_mode=clone:stop=-1[v_padded]")
         current_v_label = "v_padded"
     ```
   - `build_4k_scale_filter()` (`src/assembly/ffmpeg_commands.py:88-94`):
     ```python
     return (
         f"[{input_label}]"
         f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
         f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
         f"setsar=1"
         f"[{output_label}]"
     )
     ```
     `build_4k_scale_filter` does not include `fps=fps` or `setpts=PTS-STARTPTS` per input stream. `-r 30` is only specified on output encoding options.

3. **Shallow Video Validation (`src/pipeline/nodes/animation_generator_node.py` & `src/assembly/assembler.py`)**:
   - `_is_valid_video_file()` (`src/pipeline/nodes/animation_generator_node.py:121-134`):
     Checks only `file_path.exists()`, `file_path.stat().st_size >= 100`, and reads 100 header bytes.
   - `_is_valid_video()` (`src/assembly/assembler.py:71-78`):
     Checks only `file_path.exists()` and `file_path.stat().st_size >= 100`.

4. **Test Suite Status (`tests/pipeline/test_animation_node.py`)**:
   - Running `pytest tests/pipeline/test_animation_node.py` ran 37 tests (36 passed, 1 failed in `test_cli_flags_and_command_array_construction` due to absolute path string matching).

---

## 2. Logic Chain

1. **Step 1**: Observations show that all 8 scene template classes (`ArrayScene`, `CodeScene`, `TreeScene`, `LinkedListScene`, `GraphScene`, `HashmapScene`, `StackQueueScene`, `ComplexityScene`) render a fixed ~2-second animation (`Create` 1s + `wait(1)` 1s) regardless of the visual cue `duration` parameter (which defaults to 5s and can be 10-15s).
2. **Step 2**: Observations show that when `VideoAssemblyNode` concats the ~2-second visual segment with section audio narration (e.g. 10-15 seconds long), FFmpeg applies `tpad=stop_mode=clone:stop=-1`.
3. **Step 3**: `tpad=stop_mode=clone:stop=-1` instructs FFmpeg to duplicate the very last frame of the video segment infinitely until the audio narration ends. Consequently, after the first 2 seconds, the video displays a completely static frozen frame for the remaining 80-90% of the section duration.
4. **Step 4**: Observations show that `build_4k_scale_filter()` lacks per-input stream framerate and timestamp normalization (`fps=fps,setpts=PTS-STARTPTS`). When concatenating Manim clips with variable framerates or differing timebases, FFmpeg's `concat` filter can freeze output timestamps at frame 0.
5. **Step 5**: Observations show that scene templates contain no updater functions (`add_updater`), pointer objects (`ValueTracker`), or step-by-step keyframe sequences. Even during the initial 2 seconds, motion stops after 1 second (`Create` completion).
6. **Step 6**: Observations show that existing validation functions (`_is_valid_video_file` and `_is_valid_video`) only check file size >= 100 bytes, allowing static 1-frame or frozen clips to pass validation without raising an error.

---

## 3. Caveats

- Manim binary execution was tested with mock Python scripts during pytest; physical GPU/OpenGL rendering under full Manim Community binary was not executed in this read-only survey turn.
- FFmpeg behavior with `tpad` is based on standard FFmpeg filtergraph specification and verified code path analysis in `src/assembly/ffmpeg_commands.py`.

---

## 4. Conclusion

Animations freeze on the first frame (or freeze after 1-2 seconds) because:
1. **Scene Runtimes are Fixed at ~2 Seconds**: Scene templates do not use `duration` parameter and end after `Create()` + `wait(1)`.
2. **FFmpeg `tpad=stop_mode=clone` Clones Frozen Frames**: FFmpeg holds the final frame static for the entire audio duration (up to 15s).
3. **Lack of Updaters & Dynamic Keyframes**: No continuous motion or step animations exist in scene templates.
4. **FFmpeg Filtergraph Lacks Input Stream Normalization**: Pre-concat scaling does not normalize `fps` or `setpts`.
5. **Shallow File Validation**: Validation checks only file size >= 100 bytes, ignoring frame motion or duration.

To fix the issue and implement requirement R2:
- Update scene templates to extract `duration`, budget animation keyframes, and use `add_updater` / `ValueTracker`.
- Update `build_4k_scale_filter` to include `fps=fps,setpts=PTS-STARTPTS`.
- Enhance `_is_valid_video_file` using `ffprobe` to verify `nb_frames > 1`.
- Build pytest isolation suite `tests/test_animation/test_manim_moving_frames.py` verifying frame count and non-zero frame motion deltas.

---

## 5. Verification Method

To independently verify these observations and conclusions:
1. **Inspect Scene Runtimes**: View `src/animation/scenes/array_scene.py:32-33`, `code_scene.py:27-28`, `tree_scene.py:20-21`, `linkedlist_scene.py:29-30`.
2. **Inspect FFmpeg Commands**: View `src/assembly/ffmpeg_commands.py:88-94` and `168`.
3. **Inspect Validation Logic**: View `src/pipeline/nodes/animation_generator_node.py:121-134` and `src/assembly/assembler.py:71-78`.
4. **Run Pytest Suite**: Execute `pytest tests/pipeline/test_animation_node.py` in terminal.
