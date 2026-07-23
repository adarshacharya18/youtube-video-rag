"""
Empirical test suite for Challenge Focus 3: Dead Letter Queue (DLQ) Edge Cases
"""
import sys
import unittest
import sqlite3
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Re-implementation from Section 4.2 of 01_Media_Production_Architecture.md
@dataclass(frozen=True)
class SpecDLQEnvelope:
    dlq_id: str
    event_id: str
    correlation_id: str
    event_type: str
    source_plugin: str
    failed_at: datetime
    failure_category: str
    error_id: str
    error_message: str
    stack_trace: str
    retry_count: int
    original_payload: dict[str, Any]
    resolved: bool = False
    resolution_notes: str | None = None

class SpecDeadLetterQueueStore:
    def __init__(self, db_path: Path = Path("/tmp/test_dlq.db")):
        self.db_path = db_path
        if self.db_path.exists():
            self.db_path.unlink()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dlq_messages (
                    dlq_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source_plugin TEXT NOT NULL,
                    failed_at TEXT NOT NULL,
                    failure_category TEXT NOT NULL,
                    error_id TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    stack_trace TEXT NOT NULL,
                    retry_count INTEGER NOT NULL,
                    original_payload TEXT NOT NULL,
                    resolved INTEGER NOT NULL DEFAULT 0,
                    resolution_notes TEXT
                )
            """)

    def push(self, envelope: SpecDLQEnvelope) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO dlq_messages (
                    dlq_id, event_id, correlation_id, event_type, source_plugin,
                    failed_at, failure_category, error_id, error_message, stack_trace,
                    retry_count, original_payload, resolved, resolution_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope.dlq_id, envelope.event_id, envelope.correlation_id,
                    envelope.event_type, envelope.source_plugin, envelope.failed_at.isoformat(),
                    envelope.failure_category, envelope.error_id, envelope.error_message,
                    envelope.stack_trace, envelope.retry_count, json.dumps(envelope.original_payload),
                    1 if envelope.resolved else 0, envelope.resolution_notes,
                ),
            )


class TestDLQEdgeCases(unittest.TestCase):

    def test_non_json_serializable_payload_crashes_dlq_push(self):
        """
        EMPIRICAL BUG PROOF:
        Media production payloads contain pathlib.Path objects (e.g. audio_file_path, video_clip_path).
        SpecDeadLetterQueueStore uses raw `json.dumps(envelope.original_payload)` without custom encoder or default=str.
        Pushing a media event containing Path objects raises TypeError and crashes the DLQ storage engine!
        """
        dlq_store = SpecDeadLetterQueueStore(Path("/tmp/test_dlq_crash.db"))
        
        # Typical media event payload containing Path objects
        payload_with_paths = {
            "slug": "two-sum",
            "section_id": "sec_01",
            "audio_file_path": Path("/data/artifacts/two-sum/voice/sec_01.wav"),
            "video_clip_path": Path("/data/artifacts/two-sum/animation/sec_01.mp4"),
            "render_params": {"resolution": (1920, 1080)}
        }

        envelope = SpecDLQEnvelope(
            dlq_id="dlq-101",
            event_id="evt-202",
            correlation_id="corr-303",
            event_type="animation.render.failed",
            source_plugin="ManimAnimationPlugin",
            failed_at=datetime.now(timezone.utc),
            failure_category="RENDER_ERROR",
            error_id="ERR_MANIM_TIMEOUT",
            error_message="Scene render timed out after 600s",
            stack_trace="Traceback (most recent call last)...",
            retry_count=2,
            original_payload=payload_with_paths
        )

        with self.assertRaises(TypeError) as ctx:
            dlq_store.push(envelope)
        
        self.assertIn("is not JSON serializable", str(ctx.exception),
                      "BUG PROVEN: DLQ crashes when processing payloads containing Path objects!")

    def test_missing_dlq_store_query_and_replay_methods(self):
        """
        EMPIRICAL BUG PROOF:
        The DeadLetterQueueStore class in 01_Media_Production_Architecture.md line 1343 only defines `push()`.
        Methods like `get()`, `list_unresolved()`, `replay()`, `mark_resolved()` are referenced by CLI tools,
        but completely missing from the Python class definition in the architectural spec!
        """
        dlq_store = SpecDeadLetterQueueStore(Path("/tmp/test_dlq_methods.db"))
        
        self.assertFalse(hasattr(dlq_store, "get"), "SpecDeadLetterQueueStore missing 'get' method")
        self.assertFalse(hasattr(dlq_store, "list_unresolved"), "SpecDeadLetterQueueStore missing 'list_unresolved' method")
        self.assertFalse(hasattr(dlq_store, "replay"), "SpecDeadLetterQueueStore missing 'replay' method")
        self.assertFalse(hasattr(dlq_store, "mark_resolved"), "SpecDeadLetterQueueStore missing 'mark_resolved' method")


if __name__ == "__main__":
    unittest.main()
