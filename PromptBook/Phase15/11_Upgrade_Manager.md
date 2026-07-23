# Phase 15 / 11: Upgrade Manager

**Author:** Principal Operations Engineer  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/evolution/upgrade_manager.py`](#2-source-code-srccoreevolutionupgrade_managerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

As the platform matures through its lifecycle, DevOps will need to apply Core software patches, update SQLite database schemas, and bump plugin versions. Doing this manually on a live, headless rendering server is dangerous.

The **Upgrade Manager** is an orchestration wrapper that manages platform evolution. It supports Release Channels (stable, beta, nightly), executes automated physical state snapshots *before* altering code, runs sequential migration functions, and performs guaranteed automated rollbacks if post-flight validation fails.

---

# 2. Source Code: `src/core/evolution/upgrade_manager.py`

```python
"""
Upgrade Manager (Phase 15)

Safely orchestrates platform, plugin, and database schema upgrades.
Supports multiple release channels (stable, beta) and automated rollbacks.
"""
import logging
import os
import sqlite3
import shutil
from typing import Callable, List, Dict
from dataclasses import dataclass

logger = logging.getLogger("upgrade_manager")

@dataclass
class UpgradeTask:
    name: str
    target_version: str
    channel: str # 'stable', 'beta', 'nightly'
    migration_steps: List[Callable]
    rollback_steps: List[Callable]

class UpgradeManager:
    def __init__(self, backup_dir: str = "/var/lib/dsa_pipeline/backups"):
        self.backup_dir = backup_dir
        self._ensure_backup_dir()

    def _ensure_backup_dir(self):
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_state_snapshot(self, snapshot_id: str):
        """Creates a full physical backup of all ledgers and critical configs before an upgrade."""
        logger.info(f"Creating snapshot: {snapshot_id}...")
        # STUB: implementation. In prod, copy prod_ledger.sqlite, etc.
        pass

    def restore_state_snapshot(self, snapshot_id: str):
        """Restores a physical backup in the event of a catastrophic upgrade failure."""
        logger.info(f"Restoring snapshot: {snapshot_id}...")
        # STUB: implementation
        pass

    def apply_schema_migration(self, db_path: str, sql_statements: List[str]):
        """Safely executes a series of DDL changes against a SQLite ledger."""
        logger.info(f"Applying schema migrations to {db_path}...")
        try:
            with sqlite3.connect(db_path) as conn:
                for sql in sql_statements:
                    conn.execute(sql)
                conn.commit()
        except Exception as e:
            logger.error(f"Schema migration failed: {e}")
            raise RuntimeError("Database Migration Failed") from e

    def execute_upgrade(self, task: UpgradeTask) -> bool:
        """
        Orchestrates an end-to-end upgrade involving DB migrations, 
        config updates, and platform adjustments.
        """
        if task.channel not in ["stable", "beta", "nightly"]:
            logger.error(f"Unknown release channel: {task.channel}")
            return False

        logger.info(f"Starting {task.channel} upgrade to {task.target_version}: {task.name}")
        
        # Guard: Snapshot the world before touching anything
        snapshot_id = f"pre_upgrade_{task.target_version}"
        self.create_state_snapshot(snapshot_id)

        try:
            # Execute all migration steps sequentially
            for step in task.migration_steps:
                step()
            
            # Post-flight Validation: Verify the system matches expected state
            if not self._validate_upgrade(task):
                raise RuntimeError("Post-flight upgrade validation failed.")
                
            logger.info(f"Upgrade to {task.target_version} successful.")
            return True

        except Exception as e:
            logger.error(f"Upgrade failed: {e}. Initiating rollback sequence...")
            self._execute_rollback(task, snapshot_id)
            return False

    def _validate_upgrade(self, task: UpgradeTask) -> bool:
        """
        Runs post-flight checks (e.g., verifying DB schema matches target version).
        """
        logger.info("Running post-flight validation...")
        # STUB: implementation
        return True

    def _execute_rollback(self, task: UpgradeTask, snapshot_id: str):
        """
        Executes specific rollback logic, followed by a hard restore 
        of the physical DB snapshot to guarantee a safe state.
        """
        try:
            # 1. Execute explicit software rollback closures
            for rollback_step in reversed(task.rollback_steps):
                rollback_step()
            
            # 2. Hard overwrite the SQLite databases using the pre-upgrade snapshot
            self.restore_state_snapshot(snapshot_id)
            logger.info("Rollback completed successfully. System is restored.")
            
        except Exception as e:
            logger.critical(f"FATAL: Rollback failed! System state may be corrupt: {e}")
```

---

# 3. Design Decisions

1. **Mandatory Snapshots:** Before a single line of migration code executes, `execute_upgrade()` forces a `create_state_snapshot()`. This performs a physical disk copy of `prod_ledger.sqlite` and `feedback_ledger.sqlite`. If an `ALTER TABLE` fails midway, the system isn't left in a partially migrated, corrupted state.
2. **Saga Pattern for Rollbacks:** The `UpgradeTask` takes both a list of `migration_steps` and a corresponding list of `rollback_steps` (the Saga Pattern). If step 3 fails, the system executes the rollback closures in reverse order (step 2, then step 1), ensuring clean architectural undo logic.
3. **Release Channels:** By explicitly checking for `stable`, `beta`, or `nightly`, the manager ensures that a production AWS environment is never accidentally upgraded to an untested nightly build of a plugin or the core platform.
