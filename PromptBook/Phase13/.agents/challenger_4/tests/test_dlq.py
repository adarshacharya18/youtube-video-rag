"""
Empirical test harness for DLQ JSON serialization with PosixPath objects and store query methods.
"""

import sys
import unittest
import tempfile
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Copy of DLQEnvelope and DeadLetterQueueStore from 01_Media_Production_Architecture.md Section 4.2
@dataclass(frozen=True)
class DLQEnvelope:
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


class DeadLetterQueueStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
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

    def push(self, envelope: DLQEnvelope) -> None:
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
                    envelope.stack_trace, envelope.retry_count, json.dumps(envelope.original_payload, default=str),
                    1 if envelope.resolved else 0, envelope.resolution_notes,
                ),
            )

    def list_unresolved(self) -> list[DLQEnvelope]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM dlq_messages WHERE resolved = 0 ORDER BY failed_at DESC"
            )
            rows = cursor.fetchall()
            return [self._row_to_envelope(row) for row in rows]

    def get_by_id(self, dlq_id: str) -> DLQEnvelope | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM dlq_messages WHERE dlq_id = ?", (dlq_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_envelope(row)
            return None

    def mark_resolved(self, dlq_id: str, notes: str = "Resolved via CLI") -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE dlq_messages SET resolved = 1, resolution_notes = ? WHERE dlq_id = ?",
                (notes, dlq_id),
            )

    def _row_to_envelope(self, row: sqlite3.Row) -> DLQEnvelope:
        return DLQEnvelope(
            dlq_id=row["dlq_id"],
            event_id=row["event_id"],
            correlation_id=row["correlation_id"],
            event_type=row["event_type"],
            source_plugin=row["source_plugin"],
            failed_at=datetime.fromisoformat(row["failed_at"]),
            failure_category=row["failure_category"],
            error_id=row["error_id"],
            error_message=row["error_message"],
            stack_trace=row["stack_trace"],
            retry_count=row["retry_count"],
            original_payload=json.loads(row["original_payload"]),
            resolved=bool(row["resolved"]),
            resolution_notes=row["resolution_notes"],
        )


class TestDLQ(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_dlq.db"
        self.store = DeadLetterQueueStore(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_posix_path_serialization_in_dlq_push(self):
        payload_with_paths = {
            "slug": "two-sum",
            "audio_file": Path("/data/artifacts/two-sum/voice/sec_01.wav"),
            "nested": {
                "output_dir": Path("/data/artifacts/two-sum/render"),
                "frame_count": 600,
            },
            "timestamp": datetime.now(timezone.utc),
        }

        envelope = DLQEnvelope(
            dlq_id="dlq_123",
            event_id="evt_456",
            correlation_id="corr_789",
            event_type="media.failed",
            source_plugin="manim_plugin",
            failed_at=datetime.now(timezone.utc),
            failure_category="RENDER_ERROR",
            error_id="ERR_MANIM_TIMEOUT",
            error_message="Manim timed out",
            stack_trace="Traceback...",
            retry_count=3,
            original_payload=payload_with_paths,
        )

        # 1. Push envelope with Path objects into DLQ store
        # Should not raise TypeError: Object of type PosixPath is not JSON serializable
        self.store.push(envelope)

        # 2. Retrieve envelope back
        retrieved = self.store.get_by_id("dlq_123")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.dlq_id, "dlq_123")
        self.assertEqual(retrieved.original_payload["audio_file"], "/data/artifacts/two-sum/voice/sec_01.wav")
        self.assertEqual(retrieved.original_payload["nested"]["output_dir"], "/data/artifacts/two-sum/render")

    def test_list_unresolved_and_mark_resolved(self):
        envelope = DLQEnvelope(
            dlq_id="dlq_999",
            event_id="evt_999",
            correlation_id="corr_999",
            event_type="media.failed",
            source_plugin="voice_plugin",
            failed_at=datetime.now(timezone.utc),
            failure_category="VOICE_SYNTHESIS_ERROR",
            error_id="ERR_AUDIO_CORRUPT",
            error_message="Corrupted wave header",
            stack_trace="Traceback...",
            retry_count=1,
            original_payload={"file": Path("/tmp/audio.wav")},
        )

        self.store.push(envelope)

        unresolved = self.store.list_unresolved()
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0].dlq_id, "dlq_999")

        self.store.mark_resolved("dlq_999", "Fixed corrupted wave file")

        unresolved_after = self.store.list_unresolved()
        self.assertEqual(len(unresolved_after), 0)

        resolved_item = self.store.get_by_id("dlq_999")
        self.assertTrue(resolved_item.resolved)
        self.assertEqual(resolved_item.resolution_notes, "Fixed corrupted wave file")


if __name__ == "__main__":
    unittest.main()
