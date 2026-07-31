"""
State Ledger implementation for Phase 04 Runtime Architecture.

Provides thread-safe, crash-safe SQLite-backed execution tracking
and idempotency/recovery logic for the video generation pipeline.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any
import uuid

from src.core.exceptions import PipelineError
from src.core.logger import get_logger

logger = get_logger(__name__)


class StepStatus(str, Enum):
    """Execution status states for pipeline runs and step executions."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Standard status aliases for consumer compatibility
PipelineStatus = StepStatus
RunStatus = StepStatus
Status = StepStatus


@dataclass
class PipelineRunRecord:
    """State representation for a pipeline run."""
    pipeline_run_id: str
    slug: str
    status: StepStatus
    created_at: str
    updated_at: str
    metadata: dict[str, Any] | None = None


@dataclass
class StepExecutionRecord:
    """State representation for an individual step execution."""
    step_execution_id: str
    pipeline_run_id: str
    step_name: str
    status: StepStatus
    created_at: str
    updated_at: str
    input_payload: dict[str, Any] | None = None
    output_payload: dict[str, Any] | None = None
    error_message: str | None = None
    error_details: dict[str, Any] | None = None


class StateLedger:
    """
    SQLite-backed State Ledger for pipeline execution tracking and crash recovery.
    Thread-safe implementation with explicit WAL mode and transactional integrity.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

        db_str = str(self.db_path)
        if db_str != ":memory:" and not db_str.startswith("file::memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._conn = sqlite3.connect(db_str, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

            # Configure explicit PRAGMA settings for performance and concurrency
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._conn.execute("PRAGMA busy_timeout=5000;")

            logger.info("Initialized StateLedger database connection", db_path=db_str)
        except Exception as e:
            logger.error("Failed to connect to SQLite database", db_path=db_str, error=str(e))
            raise PipelineError(f"Failed to connect to SQLite database at {db_str}: {e}") from e

        self.init_db()

    def init_db(self) -> None:
        """Create pipeline_runs and step_executions tables if they do not exist."""
        if not self._conn:
            raise PipelineError("Database connection is closed")

        with self._lock:
            try:
                with self._conn:
                    self._conn.execute("""
                        CREATE TABLE IF NOT EXISTS pipeline_runs (
                            pipeline_run_id TEXT PRIMARY KEY,
                            slug TEXT NOT NULL,
                            status TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            metadata TEXT
                        );
                    """)
                    self._conn.execute("""
                        CREATE TABLE IF NOT EXISTS step_executions (
                            step_execution_id TEXT PRIMARY KEY,
                            pipeline_run_id TEXT NOT NULL,
                            step_name TEXT NOT NULL,
                            status TEXT NOT NULL,
                            input_payload TEXT,
                            output_payload TEXT,
                            error_message TEXT,
                            error_details TEXT,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            FOREIGN KEY (pipeline_run_id) REFERENCES pipeline_runs (pipeline_run_id) ON DELETE CASCADE
                        );
                    """)
                    self._conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_step_executions_run_id
                        ON step_executions(pipeline_run_id);
                    """)
                    self._conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_pipeline_runs_slug
                        ON pipeline_runs(slug);
                    """)
                logger.info("Database schema initialized successfully")
            except Exception as e:
                logger.error("Failed to initialize database schema", error=str(e))
                raise PipelineError(f"Failed to initialize state ledger database: {e}") from e

    def create_run(self, slug: str, metadata: dict | None = None) -> str:
        """
        Create a new pipeline run record.

        Args:
            slug: Problem or workflow identifier.
            metadata: Optional metadata dictionary.

        Returns:
            The generated pipeline_run_id.
        """
        if not self._conn:
            raise PipelineError("Database connection is closed")

        pipeline_run_id = f"run_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()
        status_str = StepStatus.PENDING.value
        metadata_json = json.dumps(metadata) if metadata is not None else None

        with self._lock:
            try:
                with self._conn:
                    self._conn.execute(
                        """
                        INSERT INTO pipeline_runs (pipeline_run_id, slug, status, created_at, updated_at, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (pipeline_run_id, slug, status_str, now, now, metadata_json)
                    )
                logger.info("Created pipeline run", pipeline_run_id=pipeline_run_id, slug=slug)
                return pipeline_run_id
            except Exception as e:
                logger.error("Failed to create pipeline run", slug=slug, error=str(e))
                raise PipelineError(f"Failed to create pipeline run for slug '{slug}': {e}") from e

    def get_run(self, pipeline_run_id: str) -> PipelineRunRecord | None:
        """Retrieve a pipeline run record by ID."""
        if not self._conn:
            raise PipelineError("Database connection is closed")

        with self._lock:
            try:
                cursor = self._conn.execute(
                    "SELECT * FROM pipeline_runs WHERE pipeline_run_id = ?",
                    (pipeline_run_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_pipeline_run_record(row)
            except Exception as e:
                logger.error("Failed to fetch pipeline run", pipeline_run_id=pipeline_run_id, error=str(e))
                raise PipelineError(f"Failed to fetch pipeline run '{pipeline_run_id}': {e}") from e

    def get_run_by_slug(self, slug: str) -> PipelineRunRecord | None:
        """Retrieve the most recent pipeline run record by slug."""
        if not self._conn:
            raise PipelineError("Database connection is closed")

        with self._lock:
            try:
                cursor = self._conn.execute(
                    "SELECT * FROM pipeline_runs WHERE slug = ? ORDER BY created_at DESC LIMIT 1",
                    (slug,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_pipeline_run_record(row)
            except Exception as e:
                logger.error("Failed to fetch pipeline run by slug", slug=slug, error=str(e))
                raise PipelineError(f"Failed to fetch pipeline run for slug '{slug}': {e}") from e

    def record_step_start(self, pipeline_run_id: str, step_name: str, input_payload: dict | None = None) -> str:
        """
        Record the start of a step execution.

        Args:
            pipeline_run_id: Parent pipeline run ID.
            step_name: Name of the step starting.
            input_payload: Optional step input dictionary.

        Returns:
            The generated step_execution_id.
        """
        if not self._conn:
            raise PipelineError("Database connection is closed")

        step_execution_id = f"step_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()
        status_str = StepStatus.IN_PROGRESS.value
        input_json = json.dumps(input_payload) if input_payload is not None else None

        with self._lock:
            try:
                with self._conn:
                    # Update pipeline run status to IN_PROGRESS if it is PENDING
                    self._conn.execute(
                        "UPDATE pipeline_runs SET status = ?, updated_at = ? WHERE pipeline_run_id = ? AND status = ?",
                        (StepStatus.IN_PROGRESS.value, now, pipeline_run_id, StepStatus.PENDING.value)
                    )

                    self._conn.execute(
                        """
                        INSERT INTO step_executions 
                        (step_execution_id, pipeline_run_id, step_name, status, input_payload, output_payload, error_message, error_details, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (step_execution_id, pipeline_run_id, step_name, status_str, input_json, None, None, None, now, now)
                    )
                logger.info("Recorded step start", step_execution_id=step_execution_id, step_name=step_name, pipeline_run_id=pipeline_run_id)
                return step_execution_id
            except sqlite3.IntegrityError as e:
                logger.error("Foreign key violation recording step start", pipeline_run_id=pipeline_run_id, error=str(e))
                raise PipelineError(f"Pipeline run '{pipeline_run_id}' does not exist: {e}") from e
            except Exception as e:
                logger.error("Failed to record step start", pipeline_run_id=pipeline_run_id, step_name=step_name, error=str(e))
                raise PipelineError(f"Failed to record step start for '{step_name}': {e}") from e

    def record_step_completion(self, step_execution_id: str, output_payload: dict | None = None) -> None:
        """Record the successful completion of a step execution."""
        if not self._conn:
            raise PipelineError("Database connection is closed")

        now = datetime.now(timezone.utc).isoformat()
        output_json = json.dumps(output_payload) if output_payload is not None else None

        with self._lock:
            try:
                with self._conn:
                    cursor = self._conn.execute(
                        """
                        UPDATE step_executions
                        SET status = ?, output_payload = ?, updated_at = ?
                        WHERE step_execution_id = ?
                        """,
                        (StepStatus.COMPLETED.value, output_json, now, step_execution_id)
                    )
                    if cursor.rowcount == 0:
                        raise PipelineError(f"Step execution ID '{step_execution_id}' not found")
                logger.info("Recorded step completion", step_execution_id=step_execution_id)
            except PipelineError:
                raise
            except Exception as e:
                logger.error("Failed to record step completion", step_execution_id=step_execution_id, error=str(e))
                raise PipelineError(f"Failed to record step completion for '{step_execution_id}': {e}") from e

    def record_step_failure(self, step_execution_id: str, error_message: str, error_details: dict | None = None) -> None:
        """Record the failure of a step execution."""
        if not self._conn:
            raise PipelineError("Database connection is closed")

        now = datetime.now(timezone.utc).isoformat()
        details_json = json.dumps(error_details) if error_details is not None else None

        with self._lock:
            try:
                with self._conn:
                    cursor = self._conn.execute(
                        """
                        UPDATE step_executions
                        SET status = ?, error_message = ?, error_details = ?, updated_at = ?
                        WHERE step_execution_id = ?
                        """,
                        (StepStatus.FAILED.value, error_message, details_json, now, step_execution_id)
                    )
                    if cursor.rowcount == 0:
                        raise PipelineError(f"Step execution ID '{step_execution_id}' not found")

                    # Mark the parent pipeline run as FAILED
                    self._conn.execute(
                        """
                        UPDATE pipeline_runs
                        SET status = ?, updated_at = ?
                        WHERE pipeline_run_id = (
                            SELECT pipeline_run_id FROM step_executions WHERE step_execution_id = ?
                        )
                        """,
                        (StepStatus.FAILED.value, now, step_execution_id)
                    )
                logger.info("Recorded step failure", step_execution_id=step_execution_id, error_message=error_message)
            except PipelineError:
                raise
            except Exception as e:
                logger.error("Failed to record step failure", step_execution_id=step_execution_id, error=str(e))
                raise PipelineError(f"Failed to record step failure for '{step_execution_id}': {e}") from e

    def record_run_completion(self, pipeline_run_id: str, status: StepStatus = StepStatus.COMPLETED) -> None:
        """Record the completion status of a pipeline run."""
        if not self._conn:
            raise PipelineError("Database connection is closed")

        now = datetime.now(timezone.utc).isoformat()
        status_str = status.value if hasattr(status, "value") else str(status)

        with self._lock:
            try:
                with self._conn:
                    self._conn.execute(
                        "UPDATE pipeline_runs SET status = ?, updated_at = ? WHERE pipeline_run_id = ?",
                        (status_str, now, pipeline_run_id)
                    )
                logger.info("Recorded pipeline run completion", pipeline_run_id=pipeline_run_id, status=status_str)
            except Exception as e:
                logger.error("Failed to record pipeline run completion", pipeline_run_id=pipeline_run_id, error=str(e))
                raise PipelineError(f"Failed to record run completion for '{pipeline_run_id}': {e}") from e

    def update_run_status(self, pipeline_run_id: str, status: StepStatus) -> None:
        """Alias for record_run_completion."""
        self.record_run_completion(pipeline_run_id, status)

    def get_completed_steps(self, pipeline_run_id: str) -> dict[str, StepExecutionRecord]:
        """
        Get a dictionary mapping step_name -> StepExecutionRecord for all completed steps in a run.
        """
        if not self._conn:
            raise PipelineError("Database connection is closed")

        with self._lock:
            try:
                cursor = self._conn.execute(
                    """
                    SELECT * FROM step_executions
                    WHERE pipeline_run_id = ? AND status = ?
                    ORDER BY created_at ASC
                    """,
                    (pipeline_run_id, StepStatus.COMPLETED.value)
                )
                rows = cursor.fetchall()
                completed_steps: dict[str, StepExecutionRecord] = {}
                for row in rows:
                    record = self._row_to_step_execution_record(row)
                    completed_steps[record.step_name] = record
                return completed_steps
            except Exception as e:
                logger.error("Failed to get completed steps", pipeline_run_id=pipeline_run_id, error=str(e))
                raise PipelineError(f"Failed to get completed steps for pipeline run '{pipeline_run_id}': {e}") from e

    def get_step_execution(self, step_execution_id: str) -> StepExecutionRecord | None:
        """Retrieve a step execution record by ID."""
        if not self._conn:
            raise PipelineError("Database connection is closed")

        with self._lock:
            try:
                cursor = self._conn.execute(
                    "SELECT * FROM step_executions WHERE step_execution_id = ?",
                    (step_execution_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_step_execution_record(row)
            except Exception as e:
                logger.error("Failed to fetch step execution", step_execution_id=step_execution_id, error=str(e))
                raise PipelineError(f"Failed to fetch step execution '{step_execution_id}': {e}") from e

    def close(self) -> None:
        """Close the SQLite database connection."""
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()
                    logger.info("Closed StateLedger database connection")
                except Exception as e:
                    logger.error("Error closing SQLite database connection", error=str(e))
                finally:
                    self._conn = None

    def __enter__(self) -> "StateLedger":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _row_to_pipeline_run_record(self, row: sqlite3.Row) -> PipelineRunRecord:
        metadata = json.loads(row["metadata"]) if row["metadata"] is not None else None
        status_val = row["status"]
        try:
            status_enum = StepStatus(status_val)
        except ValueError:
            status_enum = status_val  # Fallback if non-standard status
        return PipelineRunRecord(
            pipeline_run_id=row["pipeline_run_id"],
            slug=row["slug"],
            status=status_enum,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=metadata,
        )

    def _row_to_step_execution_record(self, row: sqlite3.Row) -> StepExecutionRecord:
        input_payload = json.loads(row["input_payload"]) if row["input_payload"] is not None else None
        output_payload = json.loads(row["output_payload"]) if row["output_payload"] is not None else None
        error_details = json.loads(row["error_details"]) if row["error_details"] is not None else None
        status_val = row["status"]
        try:
            status_enum = StepStatus(status_val)
        except ValueError:
            status_enum = status_val
        return StepExecutionRecord(
            step_execution_id=row["step_execution_id"],
            pipeline_run_id=row["pipeline_run_id"],
            step_name=row["step_name"],
            status=status_enum,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            input_payload=input_payload,
            output_payload=output_payload,
            error_message=row["error_message"],
            error_details=error_details,
        )
