"""
Analytics Dashboard (Phase 15).

Generates a JSON report aggregating pipeline execution metrics,
feedback scores, storage usage, and model health — designed for
headless extraction via ``src/cli/evolve.py analytics``.
"""

import json
import os
import sqlite3
from typing import Any, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


class AnalyticsDashboard:
    """Headless analytics dashboard for pipeline telemetry extraction.

    Reads from the production StateLedger and optional feedback database
    to compute success rates, error trends, and storage utilisation.
    """

    def __init__(
        self,
        prod_db_path: str = "data/state_ledger.db",
        feedback_db_path: str = "data/feedback.db",
        storage_dir: str = "data/artifacts",
    ) -> None:
        """
        Args:
            prod_db_path: Path to the production StateLedger SQLite database.
            feedback_db_path: Path to the feedback ledger SQLite database.
            storage_dir: Directory whose total byte size is reported.
        """
        self._prod_db_path = prod_db_path
        self._feedback_db_path = feedback_db_path
        self._storage_dir = storage_dir

    def generate_dashboard_report(self) -> str:
        """Generate a JSON-formatted analytics report.

        Returns:
            JSON string with keys: pipeline_stats, feedback_stats,
            storage_bytes, model_health.
        """
        report: dict[str, Any] = {
            "pipeline_stats": self._get_pipeline_stats(),
            "feedback_stats": self._get_feedback_stats(),
            "storage_bytes": self._get_storage_bytes(),
        }

        return json.dumps(report, indent=2)

    # ------------------------------------------------------------------
    # Pipeline stats from StateLedger
    # ------------------------------------------------------------------

    def _get_pipeline_stats(self) -> dict[str, Any]:
        """Query pipeline run statistics from the production StateLedger."""
        if not os.path.exists(self._prod_db_path):
            return {"total_runs": 0, "completed": 0, "failed": 0, "pending": 0}

        try:
            conn = sqlite3.connect(self._prod_db_path)
            conn.row_factory = sqlite3.Row

            total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM pipeline_runs"
            ).fetchone()["cnt"]

            completed = conn.execute(
                "SELECT COUNT(*) AS cnt FROM pipeline_runs WHERE status = 'COMPLETED'"
            ).fetchone()["cnt"]

            failed = conn.execute(
                "SELECT COUNT(*) AS cnt FROM pipeline_runs WHERE status = 'FAILED'"
            ).fetchone()["cnt"]

            conn.close()

            return {
                "total_runs": total,
                "completed": completed,
                "failed": failed,
                "pending": total - completed - failed,
                "success_rate": round(completed / total, 4) if total > 0 else 0.0,
            }
        except Exception as exc:
            logger.warning("Failed to read pipeline stats", error=str(exc))
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Feedback stats
    # ------------------------------------------------------------------

    def _get_feedback_stats(self) -> dict[str, Any]:
        """Query aggregate feedback statistics from the feedback ledger."""
        if not os.path.exists(self._feedback_db_path):
            return {"total_entries": 0, "per_prompt": {}}

        try:
            conn = sqlite3.connect(self._feedback_db_path)
            conn.row_factory = sqlite3.Row

            total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM feedback"
            ).fetchone()["cnt"]

            rows = conn.execute(
                "SELECT prompt_id, COUNT(*) AS cnt, AVG(score) AS avg_score "
                "FROM feedback GROUP BY prompt_id"
            ).fetchall()

            per_prompt = {}
            for row in rows:
                per_prompt[row["prompt_id"]] = {
                    "count": row["cnt"],
                    "avg_score": round(row["avg_score"], 4) if row["avg_score"] else None,
                }

            conn.close()

            return {"total_entries": total, "per_prompt": per_prompt}
        except Exception as exc:
            logger.warning("Failed to read feedback stats", error=str(exc))
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Storage usage
    # ------------------------------------------------------------------

    def _get_storage_bytes(self) -> int:
        """Recursively compute total byte size of the artifacts directory."""
        if not os.path.exists(self._storage_dir):
            return 0

        total = 0
        for dirpath, _dirnames, filenames in os.walk(self._storage_dir):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                try:
                    total += os.path.getsize(fpath)
                except OSError:
                    pass
        return total
