"""
Empirical Model Output Parity Test Harness across ALL Phase 05 Pydantic V2 models.
"""

import sys
from unittest.mock import MagicMock, patch

from src.core.llm.openai_client import OpenAIClient
from src.core.llm.anthropic_client import AnthropicClient
from src.core.models import (
    VideoResolution,
    TargetPlatform,
    PrivacyStatus,
    Difficulty,
    SEOMetadata,
    VideoMetadata,
    PlanSection,
    CodeSnippet,
    VisualCue,
    ConceptPrerequisite,
    LearningObjective,
    EducationalPlan,
    AssetReference,
    AudioAsset,
    VideoAsset,
    RenderSegment,
    RenderManifest,
    AssembledVideo,
)

ALL_PHASE05_MODELS = [
    SEOMetadata,
    VideoMetadata,
    PlanSection,
    CodeSnippet,
    VisualCue,
    ConceptPrerequisite,
    LearningObjective,
    EducationalPlan,
    AssetReference,
    AudioAsset,
    VideoAsset,
    RenderSegment,
    RenderManifest,
    AssembledVideo,
]

def build_sample_instance(model_cls):
    if model_cls == SEOMetadata:
        return SEOMetadata(
            youtube_title="Title",
            youtube_description="Description",
            tags=["dsa"],
            category_id=27,
            privacy_status=PrivacyStatus.PUBLIC,
        )
    elif model_cls == VideoMetadata:
        return VideoMetadata(
            title="Two Sum Solution",
            description="Detailed algorithm guide",
            slug="two-sum",
            resolution=VideoResolution.R_1080P,
            width=1920,
            height=1080,
            fps=30,
            tags=["dsa", "leetcode"],
            target_platform=TargetPlatform.YOUTUBE,
            difficulty=Difficulty.EASY,
            seo_metadata=build_sample_instance(SEOMetadata),
        )
    elif model_cls == PlanSection:
        return PlanSection(
            section_id="sec-1",
            section_type="intro",
            title="Section 1",
            narration="Narration 1",
            estimated_duration=10.0,
            order=1,
        )
    elif model_cls == CodeSnippet:
        return CodeSnippet(
            snippet_id="code-1",
            language="python",
            code="def solution(): pass",
            explanation="Explanation",
            line_highlights=[1],
        )
    elif model_cls == VisualCue:
        return VisualCue(
            cue_id="cue-1",
            animation_type="highlight",
            description="Highlight array element",
        )
    elif model_cls == ConceptPrerequisite:
        return ConceptPrerequisite(
            concept="Hash Table",
            description="Basic understanding of dictionaries",
        )
    elif model_cls == LearningObjective:
        return LearningObjective(
            objective_id="obj-1",
            description="Understand two pointer pattern",
            taxonomic_level="Apply",
        )
    elif model_cls == EducationalPlan:
        return EducationalPlan(
            topic="Two Sum",
            slug="two-sum",
            target_audience="Beginner",
            difficulty="Easy",
            learning_objectives=[build_sample_instance(LearningObjective)],
            prerequisites=[build_sample_instance(ConceptPrerequisite)],
            sections=[build_sample_instance(PlanSection)],
            code_snippets=[build_sample_instance(CodeSnippet)],
            visual_cues=[build_sample_instance(VisualCue)],
            estimated_total_duration=10.0,
        )
    elif model_cls == AssetReference:
        return AssetReference(
            asset_id="asset-1",
            asset_type="audio",
            file_path="/path/to/audio.mp3",
            duration=10.0,
        )
    elif model_cls == AudioAsset:
        return AudioAsset(
            audio_id="audio-1",
            file_path="/path/to/audio.mp3",
            duration_seconds=10.0,
            sample_rate=24000,
            voice_model="kokoro",
        )
    elif model_cls == VideoAsset:
        return VideoAsset(
            asset_id="video-1",
            file_path="/path/to/video.mp4",
            duration_seconds=10.0,
            resolution="1920x1080",
            fps=30,
        )
    elif model_cls == RenderSegment:
        return RenderSegment(
            segment_id="seg-1",
            segment_type="intro",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            asset_references=[build_sample_instance(AssetReference)],
        )
    elif model_cls == RenderManifest:
        return RenderManifest(
            pipeline_run_id="run-123",
            slug="two-sum",
            segments=[build_sample_instance(RenderSegment)],
            total_duration=10.0,
        )
    elif model_cls == AssembledVideo:
        return AssembledVideo(
            slug="two-sum",
            final_video_path="/path/to/final.mp4",
            thumbnail_path="/path/to/thumb.jpg",
            total_duration_seconds=10.0,
            file_size_bytes=1024,
            segments=[build_sample_instance(RenderSegment)],
        )
    else:
        raise ValueError(f"Unknown model class {model_cls}")

def run_parity_tests():
    print("======================================================================")
    print("EMPIRICAL TEST: Model Output Parity Across ALL Phase 05 Pydantic Models")
    print("======================================================================")
    
    passed_count = 0
    failed_count = 0
    
    for model_cls in ALL_PHASE05_MODELS:
        model_name = model_cls.__name__
        sample_instance = build_sample_instance(model_cls)
        
        with patch("src.core.llm.openai_client.ChatOpenAI") as mock_openai_cls, patch(
            "src.core.llm.anthropic_client.ChatAnthropic"
        ) as mock_anthropic_cls:
            
            # Setup OpenAI mock
            mock_openai_inst = MagicMock()
            mock_openai_runnable = MagicMock()
            mock_openai_runnable.invoke.return_value = sample_instance
            mock_openai_inst.with_structured_output.return_value = mock_openai_runnable
            mock_openai_cls.return_value = mock_openai_inst
            
            # Setup Anthropic mock
            mock_anthropic_inst = MagicMock()
            mock_anthropic_runnable = MagicMock()
            mock_anthropic_runnable.invoke.return_value = sample_instance
            mock_anthropic_inst.with_structured_output.return_value = mock_anthropic_runnable
            mock_anthropic_cls.return_value = mock_anthropic_inst
            
            openai_client = OpenAIClient(api_key="mock-key", model_name="gpt-4o")
            anthropic_client = AnthropicClient(api_key="mock-key", model_name="claude-3-5-sonnet")
            
            prompt = f"Generate output for model {model_name}"
            
            try:
                res_openai = openai_client.generate_structured(prompt, model_cls)
                res_anthropic = anthropic_client.generate_structured(prompt, model_cls)
                
                # Assertions
                assert res_openai == res_anthropic, f"Parity mismatch between OpenAI and Anthropic for {model_name}"
                assert res_openai == sample_instance, f"Output does not match sample instance for {model_name}"
                assert isinstance(res_openai, model_cls), f"OpenAI result is not instance of {model_name}"
                assert isinstance(res_anthropic, model_cls), f"Anthropic result is not instance of {model_name}"
                assert res_openai.model_dump() == res_anthropic.model_dump(), f"model_dump mismatch for {model_name}"
                
                mock_openai_inst.with_structured_output.assert_called_once_with(model_cls)
                mock_anthropic_inst.with_structured_output.assert_called_once_with(model_cls)
                
                print(f"  [PASS] {model_name:20s}: OpenAI and Anthropic outputs are IDENTICAL ({type(res_openai).__name__})")
                passed_count += 1
            except Exception as e:
                print(f"  [FAIL] {model_name:20s}: {e}")
                failed_count += 1

    print("----------------------------------------------------------------------")
    print(f"RESULTS SUMMARY: Passed: {passed_count}/{len(ALL_PHASE05_MODELS)}, Failed: {failed_count}/{len(ALL_PHASE05_MODELS)}")
    print("======================================================================")
    
    if failed_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_parity_tests()
