"""Ingestion Workflow Node (Phase 01).

Fetches real problem data and the user's accepted solution from LeetCode,
then normalizes it into the pipeline's internal format. Falls back to
generic metadata if LeetCode is unreachable or no session cookie is set.
"""

import logging
import os
from typing import Any, Dict, Optional

from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node

logger = logging.getLogger(__name__)


class IngestionNode(Node):
    """Workflow Engine Node for Phase 01 Problem Ingestion.

    Data flow:
        1. Read slug from StateLedger run record.
        2. Attempt to fetch from LeetCode (problem metadata + accepted solution).
        3. Fall back to metadata dict / generic placeholders if fetch fails.
    """

    def __init__(self, session_cookie: Optional[str] = None) -> None:
        """
        Args:
            session_cookie: LeetCode LEETCODE_SESSION cookie value.
                            Defaults to the LEETCODE_SESSION env var.
        """
        self._session_cookie = session_cookie or os.getenv("LEETCODE_SESSION", "")

    @property
    def name(self) -> str:
        """Unique step name identifier in StateLedger."""
        return "ingest"

    def execute(self, run_id: str, ledger: Optional[StateLedger] = None) -> Dict[str, Any]:
        """Execute problem ingestion step for the specified run_id.

        Tries to fetch the user's accepted solution from LeetCode.
        If that fails (no cookie, network error, no submissions),
        falls back to any metadata provided at run creation time,
        or generates minimal placeholder data from the slug.

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

        # ── Attempt LeetCode fetch ────────────────────────────────────
        leetcode_data = self._fetch_from_leetcode(slug)

        if leetcode_data:
            logger.info(
                "Successfully fetched from LeetCode: title='%s', has_accepted_code=%s",
                leetcode_data.get("title"),
                bool(leetcode_data.get("accepted_code")),
            )
            # LeetCode data takes priority, metadata overrides if explicitly set
            result = {
                "slug": slug,
                "problem_id": leetcode_data.get("frontend_id", slug),
                "title": metadata.get("title") or leetcode_data["title"],
                "problem_description": leetcode_data.get("description_html", ""),
                "difficulty": metadata.get("difficulty") or leetcode_data["difficulty"],
                "tags": leetcode_data.get("tags", []),
                "hints": leetcode_data.get("hints", []),
                "constraints": leetcode_data.get("constraints", []),
                "examples": leetcode_data.get("examples", []),
                "code_snippets": leetcode_data.get("code_snippets", {}),
                # ── The user's accepted solution (legal content base) ──
                "code": leetcode_data.get("accepted_code") or metadata.get("code", ""),
                "code_language": leetcode_data.get("accepted_lang", ""),
                "accepted_runtime": leetcode_data.get("accepted_runtime", ""),
                "accepted_memory": leetcode_data.get("accepted_memory", ""),
                "submission_id": leetcode_data.get("submission_id"),
                "data_source": "leetcode_api",
                "status": "completed",
            }

            # If no accepted code was found, try code_snippets as fallback
            if not result["code"] and result["code_snippets"]:
                # Prefer C++, then Python, then whatever's first
                for lang_pref in ["cpp", "python3", "python", "java"]:
                    if lang_pref in result["code_snippets"]:
                        result["code"] = result["code_snippets"][lang_pref]
                        result["code_language"] = lang_pref
                        logger.warning(
                            "No accepted submission found — using %s starter template",
                            lang_pref,
                        )
                        break

            return result

        # ── Fallback: metadata or generic ─────────────────────────────
        logger.warning("LeetCode fetch failed — using fallback metadata for slug=%s", slug)

        title = metadata.get("title") or slug.replace("-", " ").title()
        problem_description = (
            metadata.get("problem_description")
            or f"Given a problem '{title}', write an efficient algorithm to solve it."
        )

        return {
            "slug": slug,
            "problem_id": slug,
            "title": title,
            "problem_description": problem_description,
            "difficulty": metadata.get("difficulty", "Medium"),
            "code": metadata.get("code", "def solution():\n    pass"),
            "code_language": metadata.get("code_language", "python3"),
            "constraints": metadata.get("constraints", ["1 <= N <= 10^5"]),
            "examples": metadata.get("examples", []),
            "tags": metadata.get("tags", []),
            "hints": [],
            "data_source": "fallback",
            "status": "completed",
        }

    # ── LeetCode integration ──────────────────────────────────────────

    def _fetch_from_leetcode(self, slug: str) -> Optional[Dict[str, Any]]:
        """Attempt to fetch problem + accepted submission from LeetCode.

        Returns:
            Dict with problem fields, or None on failure.
        """
        try:
            from src.core.ingestion.leetcode_fetcher import LeetCodeFetcher

            fetcher = LeetCodeFetcher(session_cookie=self._session_cookie)
            problem = fetcher.fetch_problem(slug)

            return {
                "title": problem.title,
                "frontend_id": problem.frontend_id,
                "difficulty": problem.difficulty,
                "description_html": problem.description_html,
                "tags": problem.tags,
                "hints": problem.hints,
                "constraints": problem.constraints,
                "examples": problem.examples,
                "code_snippets": problem.code_snippets,
                "accepted_code": problem.accepted_code,
                "accepted_lang": problem.accepted_lang,
                "accepted_runtime": problem.accepted_runtime,
                "accepted_memory": problem.accepted_memory,
                "submission_id": problem.submission_id,
            }

        except ImportError:
            logger.error("leetcode_fetcher module not found")
            return None
        except Exception as exc:
            logger.error("LeetCode fetch failed: %s", exc)
            return None
