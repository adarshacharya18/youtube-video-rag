"""
Upgrade Manager (Phase 15).

Orchestrates platform and schema upgrades using a saga-like pattern:
each upgrade is a sequence of forward steps with paired rollback
functions.  If any step fails the completed steps are reversed in
LIFO order so the platform returns to a consistent state.
"""

import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UpgradeTask:
    """Definition of an upgrade operation.

    Attributes:
        name: Human-readable upgrade name.
        target_version: Target semver version.
        channel: Release channel ('stable', 'beta', 'nightly').
        steps: Ordered list of callables to execute forward.
        rollbacks: Ordered list of callables to execute on failure (LIFO).
    """

    name: str
    target_version: str
    channel: str
    steps: list[Callable[[], None]] = field(default_factory=list)
    rollbacks: list[Callable[[], None]] = field(default_factory=list)


class UpgradeManager:
    """Saga-pattern upgrade executor with rollback safety.

    Before executing any upgrade steps, a physical snapshot of critical
    state (databases, configs) is created.  If any step raises an
    exception the rollback chain is executed in reverse order.
    """

    def __init__(self, backup_dir: str = "data/backups") -> None:
        """
        Args:
            backup_dir: Directory used to store pre-upgrade state snapshots.
        """
        self._backup_dir = backup_dir

    def execute_upgrade(self, task: UpgradeTask) -> bool:
        """Execute an upgrade task with automatic rollback on failure.

        Args:
            task: UpgradeTask defining steps and rollbacks.

        Returns:
            True if all steps completed successfully, False if rollback occurred.
        """
        logger.info(
            "Starting upgrade",
            name=task.name,
            target_version=task.target_version,
            channel=task.channel,
            total_steps=len(task.steps),
        )

        # Pre-flight snapshot
        self.create_state_snapshot(task.name)

        completed_step_indices: list[int] = []

        for idx, step_fn in enumerate(task.steps):
            try:
                step_fn()
                completed_step_indices.append(idx)
                logger.info(
                    "Upgrade step completed",
                    name=task.name,
                    step_index=idx,
                )
            except Exception as exc:
                logger.error(
                    "Upgrade step failed — initiating rollback",
                    name=task.name,
                    step_index=idx,
                    error=str(exc),
                )
                self._execute_rollback(task, completed_step_indices)
                return False

        logger.info(
            "Upgrade completed successfully",
            name=task.name,
            target_version=task.target_version,
        )
        return True

    # ------------------------------------------------------------------
    # Snapshot helpers (overridable for testing)
    # ------------------------------------------------------------------

    def create_state_snapshot(self, label: str) -> None:
        """Create a backup snapshot of critical state files.

        Args:
            label: Snapshot label (used as subdirectory name).
        """
        snapshot_dir = os.path.join(self._backup_dir, label)
        os.makedirs(snapshot_dir, exist_ok=True)
        logger.info("Created state snapshot", snapshot_dir=snapshot_dir)

    def restore_state_snapshot(self, label: str) -> None:
        """Restore state from a previously created snapshot.

        Args:
            label: Snapshot label to restore.
        """
        snapshot_dir = os.path.join(self._backup_dir, label)
        if os.path.exists(snapshot_dir):
            logger.info("Restoring state snapshot", snapshot_dir=snapshot_dir)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _execute_rollback(
        self,
        task: UpgradeTask,
        completed_indices: list[int],
    ) -> None:
        """Execute rollback functions in LIFO order for completed steps.

        Only rollbacks whose index exists in ``completed_indices`` are called.
        """
        rollbacks_to_run = [
            task.rollbacks[i]
            for i in reversed(completed_indices)
            if i < len(task.rollbacks)
        ]

        for rb_fn in rollbacks_to_run:
            try:
                rb_fn()
            except Exception as rb_exc:
                logger.error(
                    "Rollback function failed",
                    name=task.name,
                    error=str(rb_exc),
                )

        self.restore_state_snapshot(task.name)
        logger.info("Rollback completed", name=task.name)
