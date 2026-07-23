# Phase 15 / 03: Feedback Loop

**Author:** Principal Data Scientist / Quality Lead  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/evolution/feedback.py`](#2-source-code-srccoreevolutionfeedbackpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

A core tenet of the Platform Evolution Architecture (Phase 15) is that the system must continuously improve. The **Feedback Loop** module provides a structured, SQLite-backed ledger to ingest signals from three primary sources:
1. **Automatic Quality Scores** (from the LLM-as-a-Judge mechanism)
2. **Manual Reviews** (human SRE/Educator overrides)
3. **Future User Feedback** (future hook for YouTube Comments or Watch Time retention metrics).

By centralizing these signals into a single data structure, the pipeline can programmatically detect regressions across A/B test cohorts.

---

# 2. Source Code: `src/core/evolution/feedback.py`

```python
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
```

---

# 3. Design Decisions

1. **Independent Persistence:** The feedback loop utilizes a separate SQLite database (`feedback_ledger.sqlite`) rather than modifying the core Orchestrator state ledger (`prod_ledger.sqlite`). This architectural isolation ensures that running heavy analytical aggregate queries (like `get_experiment_average`) does not cause database lock contention with the main video generation process.
2. **Unified Data Interface:** By funneling `automatic_judge`, `manual_review`, and `youtube_metrics` through the exact same `FeedbackEntry` structure, the `detect_regression` logic can easily compute aggregate moving averages across disparate sources.
3. **Automated Regression Detection:** The `detect_regression` method is designed to be called programmatically by the `PipelineOrchestrator` before starting a new batch. If the experiment drops more than 1.0 points below the baseline, the system can automatically halt the A/B test and fallback to the safe baseline prompt.
