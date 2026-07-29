"""Script Generator Workflow Node.

Converts DSA problem details into a timed YouTube script with spoken narration
and visual cues, utilizing an Error-Feedback Retry Loop.
"""

import json
import logging
from typing import Any, Dict, Optional

from pydantic import ValidationError as PydanticValidationError

from src.core.exceptions import (
    PipelineError,
    PipelineStageError,
    ScriptGenerationError,
    ValidationError as CoreValidationError,
)
from src.core.llm.prompt_loader import PromptLoader
from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node
from src.models.script import YouTubeScript

logger = logging.getLogger(__name__)


class ScriptGeneratorNode(Node):
    """Workflow Engine Node for Phase 11 Script & Narration Generation."""

    def __init__(
        self,
        llm_provider: Optional[Any] = None,
        prompt_loader: Optional[PromptLoader] = None,
        max_retries: int = 3,
    ) -> None:
        self.llm_provider = llm_provider
        self.prompt_loader = prompt_loader
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return "script_generator"

    def execute(self, run_id: str, ledger: Optional[StateLedger] = None) -> Dict[str, Any]:
        """Execute node processing logic for the specified run_id.

        Retrieves input state/plan from StateLedger or uses default input if running stand-alone.
        """
        # 1. Retrieve problem context from StateLedger or use defaults
        context_data = self._retrieve_input_context(run_id, ledger)

        # 2. Render base prompt
        base_prompt = self._render_prompt(context_data)

        # 3. Error-Feedback Retry Loop
        script_model = self._generate_with_retry(base_prompt, context_data)

        # 4. Construct output payload
        output_payload = {
            "script": script_model.model_dump(),
            "slug": script_model.slug,
            "topic": script_model.topic,
            "status": "completed",
        }

        return output_payload

    def _retrieve_input_context(self, run_id: str, ledger: Optional[StateLedger]) -> Dict[str, Any]:
        """Retrieve problem context from StateLedger step outputs or fallback defaults."""
        slug = "two-sum"
        topic = "Two Sum"
        difficulty = "Easy"
        problem_description = (
            "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target."
        )
        constraints = ["2 <= nums.length <= 10^4", "-10^9 <= nums[i] <= 10^9", "-10^9 <= target <= 10^9"]
        code = "def twoSum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        diff = target - num\n        if diff in seen:\n            return [seen[diff], i]\n        seen[num] = i\n    return []"

        if ledger is not None and run_id:
            try:
                run_record = self.get_run_record(run_id, ledger)
                if run_record and run_record.slug:
                    slug = run_record.slug
                    topic = slug.replace("-", " ").title()
            except Exception:
                pass

            try:
                completed = self.get_completed_step_outputs(run_id, ledger)
                for step_key in ("plan", "educational_plan", "ingest"):
                    if step_key in completed:
                        step_data = completed[step_key]
                        if "slug" in step_data:
                            slug = step_data["slug"]
                        if "topic" in step_data:
                            topic = step_data["topic"]
                        elif "title" in step_data:
                            topic = step_data["title"]
                        if "difficulty" in step_data:
                            difficulty = step_data["difficulty"]
                        if "problem_description" in step_data:
                            problem_description = step_data["problem_description"]
                        elif "raw_problem" in step_data:
                            problem_description = step_data["raw_problem"]
                        if "constraints" in step_data:
                            constraints = step_data["constraints"]
                        if "code" in step_data:
                            code = step_data["code"]
                        break
            except Exception:
                pass

        return {
            "slug": slug,
            "topic": topic,
            "difficulty": difficulty,
            "problem_description": problem_description,
            "constraints": constraints,
            "code": code,
        }

    def _render_prompt(self, context_data: Dict[str, Any]) -> str:
        """Render prompt template using PromptLoader or fallback text."""
        if self.prompt_loader is not None:
            try:
                return self.prompt_loader.render("script_generation", context=context_data, version="v1")
            except Exception as e:
                logger.warning(f"Failed to render prompt template: {e}. Falling back to inline prompt.")

        return (
            f"Generate a timed YouTube script for topic '{context_data['topic']}' (slug: '{context_data['slug']}').\n"
            f"Difficulty: {context_data['difficulty']}\n"
            f"Problem: {context_data['problem_description']}\n"
            f"Output strictly valid JSON matching YouTubeScript Pydantic schema with hook, context, solution, complexity."
        )

    def _generate_with_retry(self, base_prompt: str, context_data: Dict[str, Any]) -> YouTubeScript:
        """Execute Error-Feedback Retry Loop, appending exact error text on validation failures."""
        prompt_context = base_prompt
        last_exception: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._call_llm(prompt_context)
                script_model = self._parse_and_validate_response(response)
                return script_model
            except (PydanticValidationError, CoreValidationError, json.JSONDecodeError, ValueError) as e:
                last_exception = e
                error_str = str(e)
                logger.warning(f"Attempt {attempt}/{self.max_retries} failed validation: {error_str}")
                if attempt < self.max_retries:
                    feedback = (
                        f"\n\n=== PREVIOUS ATTEMPT FAILED WITH VALIDATION ERROR ===\n"
                        f"Error Details: {error_str}\n"
                        f"Please correct all validation errors and produce valid JSON adhering strictly to the schema."
                    )
                    prompt_context = f"{prompt_context}{feedback}"

        raise ScriptGenerationError(
            f"ScriptGeneratorNode failed after {self.max_retries} attempts. Last error: {last_exception}"
        )

    def _call_llm(self, prompt: str) -> Any:
        """Call LLM provider using available method interface."""
        if self.llm_provider is None:
            raise ScriptGenerationError("No LLM provider configured for ScriptGeneratorNode.")

        if hasattr(self.llm_provider, "generate_structured"):
            try:
                return self.llm_provider.generate_structured(prompt, YouTubeScript)
            except (PydanticValidationError, CoreValidationError, json.JSONDecodeError, ValueError):
                raise
            except Exception as e:
                raise CoreValidationError(str(e))
        elif hasattr(self.llm_provider, "generate"):
            return self.llm_provider.generate(prompt)
        elif hasattr(self.llm_provider, "invoke"):
            return self.llm_provider.invoke(prompt)
        elif callable(self.llm_provider):
            return self.llm_provider(prompt)
        else:
            raise ScriptGenerationError(f"Unsupported LLM provider type: {type(self.llm_provider)}")

    def _parse_and_validate_response(self, response: Any) -> YouTubeScript:
        """Parse raw LLM response (YouTubeScript, dict, or JSON string) into validated YouTubeScript model."""
        if isinstance(response, YouTubeScript):
            return response
        elif isinstance(response, dict):
            return YouTubeScript.model_validate(response)
        elif isinstance(response, str):
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                return YouTubeScript.model_validate(parsed)
            raise CoreValidationError(f"Parsed JSON must be a dict, got {type(parsed).__name__}")
        else:
            raise CoreValidationError(f"Unexpected response type from LLM: {type(response).__name__}")
