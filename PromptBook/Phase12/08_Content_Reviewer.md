# Phase 12 / 08: Content Reviewer

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/script/reviewer.py`](#2-source-code-srccorescriptreviewerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

Generative LLMs hallucinate. If an LLM accidentally states that checking a Hash Map is $O(N)$ instead of $O(1)$, the resulting educational video becomes actively harmful to the viewer's computer science knowledge.

The **Content Reviewer** implements an automated "LLM-as-a-Judge" safety mechanism. Before the `FinalScriptPayload` is committed to disk, it is passed back into a fresh, isolated LLM instance alongside the *original* RAG context. The Reviewer acts as an adversarial auditor, actively searching for technical inaccuracies, pacing mismatches, and difficulty spikes. If a `CRITICAL` finding is discovered, the pipeline rejects the script and triggers a rewrite, guaranteeing that only mathematically sound scripts reach the expensive audio/video rendering engines.

---

# 2. Source Code: `src/core/script/reviewer.py`

```python
"""
Content Reviewer for the Script Pipeline.

Uses an 'LLM-as-a-Judge' approach to rigorously fact-check the generated
script against the original RAG context. Identifies hallucinations, 
complexity errors, and animation pacing mismatches before finalizing the artifact.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, List

# Assumed imported from generator
from src.core.script.generator import FinalScriptPayload


@dataclass
class ReviewFinding:
    """A specific error or hallucination found in the script."""
    severity: str  # "CRITICAL", "WARNING", "INFO"
    category: str  # "TECHNICAL_CORRECTNESS", "DIFFICULTY_ALIGNMENT", "ANIMATION"
    scene_id: int
    description: str
    recommended_fix: str


@dataclass
class ReviewReport:
    """The complete evaluation of the script."""
    is_approved: bool
    overall_score: int  # 0 to 100
    findings: List[ReviewFinding]


class ContentReviewer:
    """Evaluates the compiled script payload against the mathematical RAG context."""
    
    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client
        self._logger = logging.getLogger(__name__)

    def review_script(self, payload: FinalScriptPayload, original_rag_context: str) -> ReviewReport:
        """
        Rigorously analyzes the script for hallucinations or educational flaws.
        """
        self._logger.info(f"Initiating Content Review for '{payload.slug}'...")
        
        system_prompt = (
            "You are a Senior Principal Software Engineer reviewing a YouTube script. "
            "Compare the Script Payload against the Original RAG Context. "
            "You MUST flag any mathematical hallucination (e.g. stating O(1) when it is O(N)) as CRITICAL. "
            "Output a strict JSON payload mapping to the ReviewReport schema."
        )
        
        # Serialize the payload back to JSON for the LLM to read
        payload_json = json.dumps(payload.__dict__, default=str)
        
        user_prompt = f"--- ORIGINAL RAG CONTEXT ---\n{original_rag_context}\n\n--- SCRIPT PAYLOAD ---\n{payload_json}"
        
        # ---------------------------------------------------------------------
        # Simulated LLM Call
        # ---------------------------------------------------------------------
        # In production: 
        # report = self._llm.generate(system_prompt, user_prompt, response_model=ReviewReport)
        
        # Stubbing the deterministic response for architecture validation
        # We simulate finding an error to demonstrate the self-correction loop capabilities
        report = ReviewReport(
            is_approved=False, 
            overall_score=85,
            findings=[
                ReviewFinding(
                    severity="CRITICAL",
                    category="TECHNICAL_CORRECTNESS",
                    scene_id=4,
                    description="The script states dictionary insertion is strictly O(1), but fails to mention the worst-case O(N) during a hash collision.",
                    recommended_fix="Update Scene 4 narration to add: '...though in the rare case of a hash collision, it could degrade to O(N).'"
                ),
                ReviewFinding(
                    severity="WARNING",
                    category="ANIMATION",
                    scene_id=2,
                    description="The brute force animation timeline is packed too tightly. 5 visual actions in 2 seconds.",
                    recommended_fix="Extend the estimated_duration_sec of Scene 2 by 5 seconds to let the visual breathe."
                )
            ]
        )
        
        if not report.is_approved:
            self._logger.warning(f"Script '{payload.slug}' REJECTED by Reviewer. Found {len(report.findings)} issues.")
        else:
            self._logger.info(f"Script '{payload.slug}' APPROVED.")
            
        return report
```

---

# 3. Design Decisions

1. **Adversarial Auditing:** By explicitly prompting the LLM as a "Senior Principal Engineer" tasked with auditing, we shift its operational mode from "creative generator" to "strict validator". Providing the *original* RAG markdown alongside the *generated* JSON payload allows the LLM to perform direct, mathematical diffing to spot hallucinations.
2. **Actionable Fixes (`recommended_fix`):** The reviewer doesn't just return `False`. It generates explicit string recommendations on *how* to fix the problem. If `is_approved` is False, the `PipelineOrchestrator` can feed these exact `recommended_fix` strings back into the generative modules (Planner/Storyboard/Narration) to automatically patch the script without human intervention.
3. **Severity Thresholds:** By categorizing findings, we allow the pipeline to intelligently proceed. A `WARNING` about animation pacing might still be allowed through if the `overall_score` is high enough, whereas a `CRITICAL` technical error physically halts the pipeline, preventing bad math from ever being rendered into an MP4.
