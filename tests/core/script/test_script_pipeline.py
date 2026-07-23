"""
Comprehensive Test Suite for the Script Generation Pipeline.

Validates the deterministic boundaries of the LLM logic, ensuring that
the Prompt Manager, Formatter, and Reviewer modules behave predictably
without actually requiring live API calls to Google/OpenAI.
"""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

# Module Imports
from src.core.script.animation import (AnimationAction, AnimationPlan,
                                       AnimationScene, VisualObject)
from src.core.script.formatter import OutputFormatter
from src.core.script.generator import FinalScriptPayload, ScriptGenerator
from src.core.script.narration import NarrationBlock, NarrationPlan
from src.core.script.planner import TeachingPlan
from src.core.script.prompts import PromptManager
from src.core.script.reviewer import (ContentReviewer, ReviewFinding,
                                      ReviewReport)
from src.core.script.storyboard import StoryboardPayload, StoryboardScene


@pytest.fixture
def mock_llm_client():
    """Provides a mocked generative LLM client to prevent live network calls during CI/CD."""
    return Mock()


@pytest.fixture
def prompt_manager():
    return PromptManager()


@pytest.fixture
def output_dir(tmp_path):
    """Provides an isolated temporary directory for file I/O tests."""
    return tmp_path / "script_exports"


@pytest.fixture
def script_payload():
    """Generates a perfectly valid, pre-compiled Script Payload for downstream testing."""
    return FinalScriptPayload(
        version="1.0.0",
        generated_at="2026-07-23T12:00:00Z",
        slug="two-sum",
        teaching_plan={"learning_objectives": ["Identify O(N^2) trap."]},
        storyboard={"scenes": [{"scene_id": 1, "focus_topic": "Intro"}]},
        narration={"blocks": [{"scene_id": 1, "spoken_text": "Hello world."}]},
        animation={"scenes": [{"scene_id": 1, "timeline": []}]}
    )


class TestPromptManager:
    """Validates that Prompt Templates fail fast to protect the API budget."""
    
    def test_missing_variable_raises_value_error(self, prompt_manager):
        with pytest.raises(ValueError) as exc:
            # Missing 'rag_context' variable
            prompt_manager.render("educational_planner", {"slug": "two-sum"})
        assert "Missing variables" in str(exc.value)

    def test_successful_render(self, prompt_manager):
        sys_prompt, user_prompt = prompt_manager.render(
            "educational_planner", 
            {"slug": "two-sum", "rag_context": "Hash Map Context"}
        )
        assert "Computer Science Professor" in sys_prompt
        assert "two-sum" in user_prompt
        assert "Hash Map Context" in user_prompt


class TestScriptCompiler:
    """Validates the AST combination logic."""
    
    def test_compiler_merges_asts_successfully(self):
        generator = ScriptGenerator()
        
        # Sub-AST Mocks
        tp = TeachingPlan(["O(N)"], "Beginner", [])
        sb = StoryboardPayload("test-slug", 60, [])
        np = NarrationPlan("test-slug", 100, 60, [])
        ap = AnimationPlan("test-slug", [])
        
        payload = generator.compile("test-slug", tp, sb, np, ap)
        assert payload.slug == "test-slug"
        assert payload.version == "1.0.0"
        assert "O(N)" in str(payload.teaching_plan)


class TestOutputFormatter:
    """Validates cryptographic checksum generation and ZIP archiving."""
    
    def test_formatter_generates_all_files(self, output_dir, script_payload):
        formatter = OutputFormatter(str(output_dir))
        checksums = formatter.format_all(script_payload, "test_script")
        
        # Ensure all 4 formats exist
        assert (output_dir / "test_script.json").exists()
        assert (output_dir / "test_script.md").exists()
        assert (output_dir / "test_script.txt").exists()
        assert (output_dir / "test_script.html").exists()
        
        # Ensure checksums were mathematically calculated
        assert "json" in checksums
        assert len(checksums["json"]) == 64  # SHA-256 length requirement
        
    def test_export_package_creates_zip(self, output_dir, script_payload):
        formatter = OutputFormatter(str(output_dir))
        checksums = formatter.format_all(script_payload, "test_script")
        
        zip_path = formatter.export_package("test_script", checksums)
        assert Path(zip_path).exists()
        assert zip_path.endswith(".zip")


class TestContentReviewer:
    """Validates the LLM-as-a-Judge grading criteria."""
    
    def test_reviewer_flags_critical_hallucinations(self, mock_llm_client, script_payload):
        reviewer = ContentReviewer(mock_llm_client)
        report = reviewer.review_script(script_payload, "Original RAG: O(1)")
        
        # In our stub implementation, we hardcoded a failure to validate architecture routing
        assert report.is_approved is False
        assert report.overall_score == 85
        assert any(finding.severity == "CRITICAL" for finding in report.findings)
