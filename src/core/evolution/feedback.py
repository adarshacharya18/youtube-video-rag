"""
Feedback Loop Management (Phase 15)

Manages the ingestion, storage, and retrieval of automatic quality scores,
manual reviewer feedback, and future end-user signals (e.g., YouTube metrics).
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class FeedbackEntry:
    video_id: str
    source: str         # 'automatic_judge', 'manual_review', 'youtube_metrics'
    experiment_id: str  # 'baseline', 'prompt_v2_ab_test', etc.
    score: float        # 0.0 to 10.0
    payload: dict       # Detailed JSON feedback
    timestamp: str

class FeedbackManager:
    def __init__(self, db_path: str = "/var/lib/dsa_pipeline/feedback_ledger.sqlite"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initializes the feedback ledger."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    score REAL NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    def record_feedback(self, entry: FeedbackEntry) -> int:
        """Stores a new feedback signal."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO feedback (video_id, source, experiment_id, score, payload, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entry.video_id,
                entry.source,
                entry.experiment_id,
                entry.score,
                json.dumps(entry.payload),
                entry.timestamp
            ))
            conn.commit()
            return cursor.lastrowid

    def get_experiment_average(self, experiment_id: str) -> Optional[float]:
        """Calculates the average score for a specific A/B test cohort."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT AVG(score) FROM feedback WHERE experiment_id = ?
            """, (experiment_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def detect_regression(self, baseline_id: str, experiment_id: str, threshold: float = 1.0) -> bool:
        """
        Compares an experimental cohort to a baseline cohort.
        Returns True if the experiment score drops below the baseline by the given threshold.
        """
        baseline_score = self.get_experiment_average(baseline_id)
        experiment_score = self.get_experiment_average(experiment_id)

        if baseline_score is None or experiment_score is None:
            return False  # Not enough data to declare a regression

        return (baseline_score - experiment_score) > threshold

    def export_improvement_history(self, video_id: str) -> List[Dict]:
        """Retrieves all feedback for a specific video to analyze prompt iterations over time."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT source, experiment_id, score, payload, timestamp 
                FROM feedback 
                WHERE video_id = ? 
                ORDER BY timestamp ASC
            """, (video_id,))
            return [dict(row) for row in cursor.fetchall()]
