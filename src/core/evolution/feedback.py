"""
Feedback Manager (Phase 15).

SQLite-backed ledger for collecting quality feedback scores from
automated LLM-as-a-judge evaluators and manual human reviewers.
Scores are associated with a prompt_id so the PromptManager can
compute per-variant moving averages and trigger regression kill-switches.
"""

from dataclasses import dataclass
from typing import Any, Optional

import json
import sqlite3
import threading

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FeedbackEntry:
    """A single quality feedback record.

    Attributes:
        video_id: Identifier for the evaluated video or run.
        source: Origin of the feedback ('judge', 'human', etc.).
        prompt_id: Prompt template variant used to generate the content.
        score: Numeric quality score (e.g. 1.0–10.0).
        metadata: Arbitrary key-value metadata.
        timestamp: ISO-8601 timestamp string.
    """

    video_id: str
    source: str
    prompt_id: str
    score: float
    metadata: dict[str, Any]
    timestamp: str


class FeedbackManager:
    """SQLite-backed feedback ledger.

    Stores :class:`FeedbackEntry` records and exposes aggregate queries
    consumed by the :class:`PromptManager` for regression detection.
    """

    def __init__(self, db_path: str = "data/feedback.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    prompt_id TEXT NOT NULL,
                    score REAL NOT NULL,
                    metadata TEXT,
                    timestamp TEXT NOT NULL
                );
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_prompt
                ON feedback(prompt_id);
            """)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record_feedback(self, entry: FeedbackEntry) -> None:
        """Persist a feedback entry to the ledger.

        Args:
            entry: FeedbackEntry dataclass to store.
        """
        meta_json = json.dumps(entry.metadata) if entry.metadata else None
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO feedback (video_id, source, prompt_id, score, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (entry.video_id, entry.source, entry.prompt_id,
                 entry.score, meta_json, entry.timestamp),
            )
        logger.info(
            "Recorded feedback",
            video_id=entry.video_id,
            prompt_id=entry.prompt_id,
            score=entry.score,
        )

    # ------------------------------------------------------------------
    # Read / Aggregate
    # ------------------------------------------------------------------

    def get_average_score(self, prompt_id: str) -> Optional[float]:
        """Compute the arithmetic mean score for a prompt variant.

        Args:
            prompt_id: Prompt template identifier.

        Returns:
            Average score as float, or None if no feedback exists.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT AVG(score) AS avg_score FROM feedback WHERE prompt_id = ?",
                (prompt_id,),
            ).fetchone()
            return row["avg_score"] if row and row["avg_score"] is not None else None

    def get_feedback_count(self, prompt_id: str) -> int:
        """Return the total number of feedback entries for *prompt_id*."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM feedback WHERE prompt_id = ?",
                (prompt_id,),
            ).fetchone()
            return row["cnt"] if row else 0

    def get_all_feedback(self, prompt_id: Optional[str] = None) -> list[FeedbackEntry]:
        """Retrieve feedback entries, optionally filtered by prompt_id."""
        query = "SELECT * FROM feedback"
        params: tuple = ()
        if prompt_id:
            query += " WHERE prompt_id = ?"
            params = (prompt_id,)
        query += " ORDER BY id ASC"

        with self._lock:
            rows = self._conn.execute(query, params).fetchall()

        entries: list[FeedbackEntry] = []
        for row in rows:
            meta = json.loads(row["metadata"]) if row["metadata"] else {}
            entries.append(FeedbackEntry(
                video_id=row["video_id"],
                source=row["source"],
                prompt_id=row["prompt_id"],
                score=row["score"],
                metadata=meta,
                timestamp=row["timestamp"],
            ))
        return entries

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
