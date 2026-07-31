"""Plan Generator Workflow Node (Phase 04).

Generates educational strategy and visual plan sections for the problem.
"""

import logging
from typing import Any, Dict, Optional

from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node

logger = logging.getLogger(__name__)


class PlanNode(Node):
    """Workflow Engine Node for Phase 04 Problem Planning & Pedagogical Curation."""

    @property
    def name(self) -> str:
        """Unique step name identifier in StateLedger."""
        return "plan"

    def execute(self, run_id: str, ledger: Optional[StateLedger] = None) -> Dict[str, Any]:
        """Execute planning workflow step for the specified run_id.

        Args:
            run_id: Unique pipeline run identifier.
            ledger: Active StateLedger instance.

        Returns:
            Dict[str, Any]: Educational plan payload recorded in StateLedger.
        """
        if ledger is None:
            raise ValueError(f"Node '{self.name}' requires a valid StateLedger instance.")

        run_record = self.get_run_record(run_id, ledger)
        slug = run_record.slug

        # Look up prior ingest step output if available
        ingest_output: Dict[str, Any] = {}
        try:
            ingest_output = self.get_step_output(run_id, ledger, "ingest")
        except Exception:
            pass

        logger.info("Executing PlanNode for slug=%s (run_id=%s)", slug, run_id)

        topic = ingest_output.get("title") or (run_record.metadata or {}).get("topic") or slug
        difficulty = ingest_output.get("difficulty", "Medium")

        return {
            "slug": slug,
            "topic": topic,
            "difficulty": difficulty,
            "plan_sections": [
                "Hook & Problem Overview",
                "Brute Force & Edge Cases",
                "Optimal Approach Analysis",
                "Visual Code Walkthrough",
                "Complexity & Summary",
            ],
            "teaching_plan": {
                "learning_objectives": [
                    "Understand core algorithmic strategy",
                    "Analyze time and space complexity",
                ],
                "target_audience": "DSA Engineers",
            },
            "status": "completed",
        }
