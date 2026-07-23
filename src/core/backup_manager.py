"""
Backup and Recovery Manager.

Performs hot-snapshots of live SQLite databases without locking out Writer threads.
Validates database integrity via PRAGMA checks and enforces retention policies.
"""

import asyncio
import logging
import shutil
import sqlite3
import time
from pathlib import Path

from src.core.exceptions import PipelineError


class BackupError(PipelineError):
    """Raised during failed backups, restores, or corruption detections."""
    pass


class BackupManager:
    """
    Physical OS File System abstraction layer for SQLite Snapshots.
    """

    def __init__(self, target_dir: str = "storage/backups", retention_days: int = 14) -> None:
        self._target_dir = Path(target_dir).resolve()
        self._retention_days = retention_days
        self._logger = logging.getLogger(__name__)

    async def initialize(self) -> None:
        """Ensures the secure backup folder hierarchy exists."""
        def _setup() -> None:
            self._target_dir.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(_setup)
        self._logger.info(f"BackupManager initialized at {self._target_dir}")

    # ---------------------------------------------------------
    # Backup & Snapshot Operations
    # ---------------------------------------------------------
    async def create_snapshot(self, db_path: str, db_name: str, incremental: bool = True) -> str:
        """
        Creates a Hot Backup of a live SQLite database.
        
        incremental=True: Updates an existing backup file page-by-page (extremely fast).
        incremental=False: Creates a hard timestamped full-copy snapshot for Long-Term Storage.
        """
        source_path = Path(db_path).resolve()
        if not source_path.exists():
            raise BackupError(f"FATAL: Cannot backup missing database: {source_path}")

        timestamp = int(time.time())
        if incremental:
            target_path = self._target_dir / f"{db_name}_incremental.db"
        else:
            target_path = self._target_dir / f"{db_name}_snapshot_{timestamp}.db"

        def _backup() -> str:
            with sqlite3.connect(source_path) as source, sqlite3.connect(target_path) as target:
                # The backup() C-method copies pages in the background.
                # It yields control every 250 pages and sleeps, allowing the main
                # pipeline to continue writing to the source database without Table Locks!
                source.backup(target, pages=250, sleep=0.01)
            return str(target_path)

        try:
            snapshot_path = await asyncio.to_thread(_backup)
            self._logger.info(f"Successfully generated Hot Backup: {snapshot_path}")
            return snapshot_path
        except Exception as e:
            raise BackupError(f"Snapshot failed for {db_name}: {e}") from e

    async def validate_integrity(self, db_path: str) -> bool:
        """
        Runs rigorous C-Level PRAGMA checks on a database to verify structural integrity.
        """
        def _verify() -> bool:
            path = Path(db_path).resolve()
            if not path.exists():
                return False
            try:
                with sqlite3.connect(path) as conn:
                    cursor = conn.execute("PRAGMA integrity_check;")
                    result = cursor.fetchone()
                    return result[0] == "ok"
            except Exception:
                return False
                
        is_valid = await asyncio.to_thread(_verify)
        if not is_valid:
            self._logger.error(f"SEVERE CORRUPTION DETECTED in Database: {db_path}")
        return is_valid

    # ---------------------------------------------------------
    # Restore Operations
    # ---------------------------------------------------------
    async def restore_snapshot(self, backup_path: str, target_db_path: str) -> None:
        """
        Restores a corrupted database from a Snapshot.
        WARNING: This instantly overwrites the active database.
        """
        source = Path(backup_path).resolve()
        target = Path(target_db_path).resolve()

        if not source.exists():
            raise BackupError(f"Backup file missing from OS: {source}")

        # Step 1: Pre-Flight Integrity Check
        # If the backup file itself is corrupted, abort the restore.
        is_valid = await self.validate_integrity(str(source))
        if not is_valid:
            raise BackupError(f"Refusing to restore a Corrupted Backup File: {source}")

        def _restore() -> None:
            # Step 2: Automated Safety Net
            # Backup the broken target to a `.bak` just in case the Restore crashes halfway
            if target.exists():
                safety_net = str(target) + ".bak"
                shutil.copy2(target, safety_net)
                
            # Step 3: Perform C-Level page-by-page overwrite
            with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
                src.backup(dst)
                
        try:
            await asyncio.to_thread(_restore)
            self._logger.info(f"Database successfully restored to {target_db_path}")
        except Exception as e:
            raise BackupError(f"Failed to restore database: {e}") from e

    # ---------------------------------------------------------
    # Maintenance Operations
    # ---------------------------------------------------------
    async def cleanup_retention(self) -> int:
        """
        Garbage Collector: Deletes Snapshots older than retention_days.
        Ensures O(1) Disk Scaling over years of operation.
        """
        cutoff = time.time() - (self._retention_days * 86400)
        deleted = 0
        
        def _prune() -> int:
            nonlocal deleted
            for item in self._target_dir.glob("*.db"):
                # Never delete the rolling incremental target
                if "incremental" in item.name:
                    continue
                try:
                    if item.stat().st_mtime < cutoff:
                        item.unlink()
                        deleted += 1
                except Exception as e:
                    self._logger.warning(f"Retention Pruner failed to delete backup '{item}': {e}")
            return deleted
            
        await asyncio.to_thread(_prune)
        if deleted > 0:
            self._logger.info(f"Backup Retention: Purged {deleted} stale snapshots.")
        return deleted
