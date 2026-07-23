"""
Prompt Manager (Phase 15)

Manages dynamic selection of system prompts, supporting versioning,
A/B testing, and automatic fallback based on regression data.
"""
import logging
import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from src.core.evolution.feedback import FeedbackManager

logger = logging.getLogger("prompt_manager")

@dataclass
class PromptTemplate:
    prompt_id: str
    template_text: str
    version: str
    is_baseline: bool = False
    experiment_weight: float = 0.0  # 0.0 to 1.0 (probability of being chosen in A/B test)

class PromptManager:
    def __init__(self, feedback_manager: FeedbackManager):
        self._prompts: Dict[str, PromptTemplate] = {}
        self.feedback_manager = feedback_manager
        
        # If an experimental prompt drops 1.0 points below baseline, kill the experiment.
        self.regression_threshold = 1.0 

    def register_prompt(self, prompt: PromptTemplate):
        self._prompts[prompt.prompt_id] = prompt
        logger.info(f"Registered prompt {prompt.prompt_id} (v{prompt.version})")

    def get_baseline_prompt(self) -> PromptTemplate:
        for prompt in self._prompts.values():
            if prompt.is_baseline:
                return prompt
        raise RuntimeError("FATAL: No baseline prompt configured in the Prompt Manager!")

    def select_prompt(self, video_id: str, force_baseline: bool = False) -> PromptTemplate:
        """
        Dynamically selects a prompt for the given video.
        Supports A/B test routing based on `experiment_weight`.
        Automatically falls back to baseline if the experimental prompt has regressed.
        """
        baseline = self.get_baseline_prompt()
        if force_baseline:
            return baseline

        # Locate active experimental prompts
        experiments = [p for p in self._prompts.values() if not p.is_baseline and p.experiment_weight > 0]
        
        for exp in experiments:
            # Check the Feedback Ledger: Has this experiment caused a catastrophic drop in quality?
            if self.feedback_manager.detect_regression(baseline.prompt_id, exp.prompt_id, self.regression_threshold):
                logger.warning(f"Experiment {exp.prompt_id} regressed below threshold! Falling back to baseline.")
                continue  # Skip regressed prompts, treating them as weight = 0.0
            
            # Roll the dice for A/B testing
            if random.random() < exp.experiment_weight:
                logger.info(f"[A/B TEST] Video {video_id} routed to experimental prompt: {exp.prompt_id}")
                return exp

        # Default fallback
        return baseline
