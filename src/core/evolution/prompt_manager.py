"""
Prompt Manager with A/B Testing and Regression Kill-Switch (Phase 15).

Routes pipeline traffic between a baseline prompt and one or more
experimental variants.  After each run the FeedbackManager's scores
are queried to compute a moving average.  If the experimental variant's
average score drops below ``baseline_avg - regression_threshold`` the
kill-switch fires and all traffic is immediately reverted to the
baseline prompt.
"""

from dataclasses import dataclass, field
import random
from typing import Optional

from src.core.evolution.feedback import FeedbackManager
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PromptTemplate:
    """A versioned prompt template for A/B testing.

    Attributes:
        prompt_id: Unique identifier (e.g. 'baseline_v1', 'exp_v2').
        text: The prompt text content.
        version: Semantic version string.
        is_baseline: Whether this is the safe baseline variant.
        experiment_weight: Traffic fraction routed to this variant (0.0–1.0).
        killed: Whether the kill-switch has been triggered for this variant.
    """

    prompt_id: str
    text: str
    version: str
    is_baseline: bool = False
    experiment_weight: float = 0.0
    killed: bool = False


class PromptManager:
    """A/B testing prompt router with regression kill-switch.

    The kill-switch compares the experimental variant's average quality
    score against the baseline's.  If the difference exceeds
    ``regression_threshold`` the variant is permanently killed for the
    current session and all traffic reverts to the baseline.
    """

    def __init__(
        self,
        feedback_manager: FeedbackManager,
        regression_threshold: float = 1.0,
    ) -> None:
        """
        Args:
            feedback_manager: FeedbackManager instance for score lookups.
            regression_threshold: Maximum allowed score drop before kill-switch fires.
        """
        self._prompts: dict[str, PromptTemplate] = {}
        self._feedback: FeedbackManager = feedback_manager
        self.regression_threshold: float = regression_threshold

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_prompt(self, template: PromptTemplate) -> None:
        """Register a prompt template for A/B testing.

        Args:
            template: PromptTemplate dataclass to register.
        """
        self._prompts[template.prompt_id] = template
        logger.info(
            "Registered prompt template",
            prompt_id=template.prompt_id,
            version=template.version,
            is_baseline=template.is_baseline,
            experiment_weight=template.experiment_weight,
        )

    # ------------------------------------------------------------------
    # Selection with kill-switch
    # ------------------------------------------------------------------

    def select_prompt(self, run_id: str) -> PromptTemplate:
        """Select a prompt template for *run_id*, applying the regression kill-switch.

        The method first checks if any experimental variant has regressed
        beyond the threshold.  If so it is killed and the baseline is
        returned.  Otherwise standard weighted random selection applies.

        Args:
            run_id: Current pipeline run identifier (used for logging).

        Returns:
            The selected PromptTemplate.

        Raises:
            RuntimeError: If no baseline prompt is registered.
        """
        baseline = self._get_baseline()
        if baseline is None:
            raise RuntimeError("No baseline prompt registered in PromptManager.")

        # --- Kill-switch evaluation ---
        self._evaluate_kill_switches(baseline)

        # --- Weighted selection among surviving candidates ---
        candidates = [
            pt for pt in self._prompts.values()
            if not pt.killed and pt.experiment_weight > 0.0
        ]

        if not candidates:
            logger.info(
                "No experimental candidates available, using baseline",
                run_id=run_id,
                baseline_id=baseline.prompt_id,
            )
            return baseline

        # Weighted random selection
        total_weight = sum(c.experiment_weight for c in candidates)
        roll = random.random() * total_weight
        cumulative = 0.0
        for candidate in candidates:
            cumulative += candidate.experiment_weight
            if roll <= cumulative:
                logger.info(
                    "Selected experimental prompt",
                    run_id=run_id,
                    prompt_id=candidate.prompt_id,
                )
                return candidate

        return baseline

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_prompt_report(self) -> list[dict]:
        """Return a list of dicts summarising each registered prompt's state."""
        report = []
        for prompt_id, pt in self._prompts.items():
            avg = self._feedback.get_average_score(prompt_id)
            count = self._feedback.get_feedback_count(prompt_id)
            report.append({
                "prompt_id": prompt_id,
                "version": pt.version,
                "is_baseline": pt.is_baseline,
                "experiment_weight": pt.experiment_weight,
                "killed": pt.killed,
                "avg_score": round(avg, 4) if avg is not None else None,
                "feedback_count": count,
            })
        return report

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_baseline(self) -> Optional[PromptTemplate]:
        for pt in self._prompts.values():
            if pt.is_baseline:
                return pt
        return None

    def _evaluate_kill_switches(self, baseline: PromptTemplate) -> None:
        """Compare each experimental variant against the baseline and kill
        any that have regressed beyond the configured threshold."""
        baseline_avg = self._feedback.get_average_score(baseline.prompt_id)
        if baseline_avg is None:
            return  # No baseline data yet — cannot evaluate

        for pt in list(self._prompts.values()):
            if pt.is_baseline or pt.killed:
                continue

            exp_avg = self._feedback.get_average_score(pt.prompt_id)
            if exp_avg is None:
                continue  # No data for this variant yet

            delta = baseline_avg - exp_avg
            if delta >= self.regression_threshold:
                pt.killed = True
                logger.error(
                    "Kill-switch triggered — experimental prompt disabled",
                    prompt_id=pt.prompt_id,
                    baseline_avg=round(baseline_avg, 4),
                    experimental_avg=round(exp_avg, 4),
                    delta=round(delta, 4),
                    threshold=self.regression_threshold,
                )
