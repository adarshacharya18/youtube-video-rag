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
