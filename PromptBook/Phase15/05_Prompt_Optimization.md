# Phase 15 / 05: Prompt Optimization

**Author:** Principal Data Scientist / Prompt Engineer  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/evolution/prompt_manager.py`](#2-source-code-srccoreevolutionprompt_managerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

As new LLMs are released (e.g., transitioning from GPT-4 to GPT-5), the static system prompts written in Phase 13 will naturally degrade or become suboptimal. The **Prompt Optimization Framework** introduces versioned Prompt Templates, A/B testing routing logic, and a feedback-loop-aware auto-fallback mechanism.

This allows Prompt Engineers to push a new `prompt_v2_experimental` into the pipeline, configure it to run on 10% of videos, and mathematically guarantee that if the LLM-as-a-Judge detects a regression in quality, the system will automatically kill the A/B test and revert to the `baseline` prompt without human intervention.

---

# 2. Source Code: `src/core/evolution/prompt_manager.py`

```python
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
```

---

# 3. Design Decisions

1. **Stochastic A/B Routing:** The `select_prompt` method utilizes `random.random() < exp.experiment_weight` to automatically route a percentage of the video generation batch to experimental prompts. For example, an `experiment_weight` of `0.1` means 10% of videos will use the new prompt, isolating the "blast radius" of a bad prompt.
2. **Automated Regression Kill-Switch:** Before rolling the dice, the Prompt Manager consults the `FeedbackManager` (implemented in 15/03). If it detects that `prompt_v2_experimental` has dropped below the baseline by more than 1.0 points over its last N runs, it instantly ignores the experiment weight and falls back to the baseline. This creates a self-healing pipeline.
3. **Template Independence:** The Orchestrator is no longer tightly coupled to hardcoded Python strings. The Prompt Manager can dynamically load templates from markdown files or a CMS, register them as `PromptTemplate` objects, and serve them to the LLM generation phase on demand.
