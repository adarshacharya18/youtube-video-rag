## 2026-07-25T20:47:41Z

You are Worker 1 (Model Implementer) for Phase 05: Core Data Models & Schemas.
Your working directory is: /home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_m1

MANDATORY FIRST STEP: Read /home/adarsh/Documents/Youtube-Channel/ORIGINAL_REQUEST.md.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Scope & Owned Files (EXCLUSIVELY):
- `src/core/models/__init__.py`
- `src/core/models/video.py`
- `src/core/models/plan.py`
- `src/core/models/assets.py`

Requirements for Pydantic V2 Models:
1. All models MUST inherit strictly from `pydantic.BaseModel` (Pydantic V2).
2. `src/core/models/video.py`:
   - Enums: `VideoResolution` (StrEnum: "720p", "1080p", "1440p", "4K"), `TargetPlatform` (StrEnum: "youtube", "youtube_shorts", "tiktok"), `PrivacyStatus` (StrEnum: "public", "unlisted", "private"), `Difficulty` (StrEnum: "EASY", "MEDIUM", "HARD").
   - `SEOMetadata`: `youtube_title` (str, 1..100 chars, non-whitespace), `youtube_description` (str, 1..5000 chars, non-whitespace), `tags` (list[str], max 500 total chars), `category_id` (int, default 27), `privacy_status` (PrivacyStatus), `chapter_timestamps` (list[dict[str, str]]).
   - `VideoMetadata`: `title` (str, 1..100 chars, non-whitespace), `description` (str, 1..5000 chars, non-whitespace), `slug` (str, pattern `^[a-z0-9-]+$`), `resolution` (str, default "1080p"), `width` (int, gt 0), `height` (int, gt 0), `fps` (int, gt 0, le 120, allowed set {24, 25, 30, 50, 60, 120}), `tags` (list[str], total chars <= 500), `format` (str, default "mp4"), `target_platform` (TargetPlatform, default "youtube"), `category_id` (int, gt 0, default 27), `privacy_status` (PrivacyStatus, default "public"), `language` (str, default "en"), `problem_number` (int | None), `difficulty` (Difficulty | None), `seo_metadata` (SEOMetadata | None). Include `@field_validator` for non-empty strings, fps allowed set, tag length, and `@model_validator(mode="after")` to validate/align resolution with width/height (e.g. 1080p -> 1920x1080, 4K -> 3840x2160, 720p -> 1280x720).

3. `src/core/models/plan.py`:
   - `PlanSection`: `section_id` (str, non-whitespace), `section_type` (str, non-whitespace), `title` (str, non-whitespace), `narration` (str, non-whitespace), `estimated_duration` (float, gt 0.0), `visual_cue_ids` (list[str]), `order` (int, ge 0).
   - `CodeSnippet`: `snippet_id` (str, non-whitespace), `language` (str, default "python"), `code` (str, non-whitespace), `explanation` (str | None), `line_highlights` (list[int], all entries ge 1).
   - `VisualCue`: `cue_id` (str, non-whitespace), `animation_type` (str, non-whitespace), `description` (str, non-whitespace), `parameters` (dict[str, Any]).
   - `ConceptPrerequisite`: `concept` (str, non-whitespace), `description` (str | None).
   - `LearningObjective`: `objective_id` (str, non-whitespace), `description` (str, non-whitespace), `taxonomic_level` (str | None).
   - `EducationalPlan`: `topic` (str, non-whitespace), `slug` (str, pattern `^[a-z0-9-]+$`), `target_audience` (str, default "Beginner"), `difficulty` (str, default "Medium"), `learning_objectives` (list[str] or list[LearningObjective], min 1 non-empty item), `prerequisites` (list[str] or list[ConceptPrerequisite]), `sections` (list[PlanSection], min 1 item), `code_snippets` (list[CodeSnippet]), `visual_cues` (list[VisualCue]), `estimated_total_duration` (float, gt 0.0). Include `@field_validator` for slug format, non-empty objectives, line numbers >= 1, and `@model_validator(mode="after")` enforcing duplicate `section_id` check and `estimated_total_duration` matching sum of section durations within float tolerance (0.1s).

4. `src/core/models/assets.py`:
   - `AssetReference`: `asset_id` (str, non-whitespace), `asset_type` (str, non-whitespace), `file_path` (str, non-whitespace), `duration` (float | None, gt 0.0).
   - `AudioAsset`: `audio_id` (str, non-whitespace), `file_path` (str, non-whitespace), `duration_seconds` (float, gt 0.0), `sample_rate` (int, gt 0, default 24000), `voice_model` (str, default "kokoro").
   - `VideoAsset`: `asset_id` (str, non-whitespace), `file_path` (str, non-whitespace), `duration_seconds` (float, gt 0.0), `resolution` (str, default "1920x1080"), `fps` (int, gt 0, le 120, default 30), `file_size_bytes` (int, ge 0, default 0).
   - `RenderSegment`: `segment_id` (str, non-whitespace), `segment_type` (str, must be in {"intro", "code_walkthrough", "visual_anim", "outro", "narration"}), `start_time` (float, ge 0.0), `end_time` (float, gt 0.0), `duration` (float, gt 0.0), `asset_references` (list[AssetReference]), `audio_path` (str | None), `visual_path` (str | None), `narration_text` (str | None), `volume` (float, ge 0.0, le 2.0, default 1.0), `transition_in` (str | None), `transition_out` (str | None), `audio_asset` (AudioAsset | None), `scene_type` (str | None), `visual_parameters` (dict[str, Any], default {}). Validate `end_time > start_time`, `duration == end_time - start_time` (tolerance 1e-3), and require at least one asset reference (audio_path, visual_path, asset_references, or audio_asset).
   - `RenderManifest`: `pipeline_run_id` (str, non-whitespace), `slug` (str, pattern `^[a-z0-9-]+$`), `segments` (list[RenderSegment], min 1 item), `total_duration` (float, gt 0.0).
   - `AssembledVideo`: `slug` (str, pattern `^[a-z0-9-]+$`), `final_video_path` (str, non-whitespace), `thumbnail_path` (str | None), `total_duration_seconds` (float, gt 0.0), `file_size_bytes` (int, ge 0, default 0), `segments` (list[RenderSegment]), `assembled_at` (str | datetime | None).

5. Re-export all models in `src/core/models/__init__.py`.

Verify syntax and run pytest on any existing core tests to ensure no breakage. Write your summary to `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_m1/handoff.md` and send a message when done.
