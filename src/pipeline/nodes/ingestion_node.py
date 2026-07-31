"""Ingestion Workflow Node (Phase 01).

Fetches or normalizes problem description, constraints, and metadata for a run.
"""

import logging
from typing import Any, Dict, Optional

from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node

logger = logging.getLogger(__name__)


class IngestionNode(Node):
    """Workflow Engine Node for Phase 01 Problem Ingestion."""

    @property
    def name(self) -> str:
        """Unique step name identifier in StateLedger."""
        return "ingest"

    def execute(self, run_id: str, ledger: Optional[StateLedger] = None) -> Dict[str, Any]:
        """Execute problem ingestion step for the specified run_id.

        Args:
            run_id: Unique pipeline run identifier.
            ledger: Active StateLedger instance.

        Returns:
            Dict[str, Any]: Problem details payload recorded in StateLedger.
        """
        if ledger is None:
            raise ValueError(f"Node '{self.name}' requires a valid StateLedger instance.")

        run_record = self.get_run_record(run_id, ledger)
        slug = run_record.slug
        metadata = run_record.metadata or {}

        logger.info("Executing IngestionNode for slug=%s (run_id=%s)", slug, run_id)

        title = metadata.get("title") or slug.replace("-", " ").title()
        problem_description = (
            metadata.get("problem_description")
            or f"Given a problem '{title}', write an efficient algorithm to solve it."
        )
        difficulty = metadata.get("difficulty", "Medium")
        code = metadata.get("code", "def solution():\n    pass")
        constraints = metadata.get("constraints", ["1 <= N <= 10^5"])
        examples = metadata.get("examples", [])

        return {
            "slug": slug,
            "problem_id": slug,
            "title": title,
            "problem_description": problem_description,
            "difficulty": difficulty,
            "code": code,
            "constraints": constraints,
            "examples": examples,
            "status": "completed",
        }
