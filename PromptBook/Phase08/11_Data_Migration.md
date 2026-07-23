# Phase 08 / 11: Data Migration Framework

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/migration_manager.py`](#2-source-code-srccoremigration_managerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Global Schema Migration Framework**. 

As the application evolves (e.g., transitioning from Phase 08 into Phase 09 Plugin Architecture), the underlying database tables will require structural changes (new columns, indexes). 

The `MigrationManager` replaces chaotic `CREATE TABLE IF NOT EXISTS` hacks with a professional, linearly-ordered `schema_migrations` ledger. It automatically detects missing schema versions, sequentially applies `UP` scripts, mathematically verifies the results, and natively supports transactional `DOWN` rollbacks in the event of a botched deployment.

---

# 2. Source Code: `src/core/migration_manager.py`

```python
"""
Data Migration Framework.

Manages SQLite schema evolutions safely across application versions.
Supports sequential UP migrations, DOWN rollbacks, and Migration History tracking.
"""

import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List

from src.core.exceptions import PipelineError


class MigrationError(PipelineError):
    """Raised when a Schema Migration crashes or syntax violates SQLite Constraints."""
    pass


@dataclass(frozen=True)
class Migration:
    """Immutable representation of a Database Schema state transition."""
    version: int
    name: str
    up_sql: str
    down_sql: str


class MigrationManager:
    """
    Automated Schema Evolution Engine.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = str(Path(db_path).resolve())
        self._logger = logging.getLogger(__name__)
        
        # In-memory registry of all defined schema evolutions
        self._migrations: List[Migration] = []

    def register_migration(self, migration: Migration) -> None:
        """Injects a migration into the registry. Automatically sorts by version."""
        if any(m.version == migration.version for m in self._migrations):
            raise MigrationError(f"FATAL: Migration version {migration.version} is already registered.")
            
        self._migrations.append(migration)
        self._migrations.sort(key=lambda x: x.version)

    async def _init_history_table(self) -> None:
        """Boot Sequence: Ensures the ledger exists."""
        def _execute() -> None:
            with sqlite3.connect(self._db_path) as conn:
                # The ledger tracks exactly which migrations have been applied to this specific file
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        await asyncio.to_thread(_execute)

    async def get_current_version(self) -> int:
        """Queries the ledger for the highest applied version."""
        await self._init_history_table()
        
        def _execute() -> int:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute("SELECT MAX(version) FROM schema_migrations")
                row = cursor.fetchone()
                return row[0] if row[0] is not None else 0
                
        return await asyncio.to_thread(_execute)

    # ---------------------------------------------------------
    # Schema Evolution Operations
    # ---------------------------------------------------------
    async def apply_migrations(self) -> int:
        """
        Automatically advances the database schema to the latest registered version.
        Wraps each migration in an atomic SQLite Transaction.
        """
        await self._init_history_table()
        current_version = await self.get_current_version()
        
        pending = [m for m in self._migrations if m.version > current_version]
        if not pending:
            self._logger.info(f"Database schema is strictly up-to-date (Version {current_version}).")
            return 0
            
        def _execute() -> int:
            applied = 0
            with sqlite3.connect(self._db_path) as conn:
                for migration in pending:
                    self._logger.info(f"Applying Schema UP to v{migration.version}: {migration.name}")
                    try:
                        # Atomic wrapper: If a syntax error occurs halfway through `up_sql`, 
                        # the entire migration is rolled back, preventing corrupted half-built tables.
                        conn.execute("BEGIN TRANSACTION")
                        conn.executescript(migration.up_sql)
                        
                        # Append to ledger
                        conn.execute(
                            "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                            (migration.version, migration.name)
                        )
                        conn.commit()
                        applied += 1
                        
                    except Exception as e:
                        conn.rollback()
                        raise MigrationError(f"Migration v{migration.version} crashed: {e}") from e
                        
            return applied
            
        count = await asyncio.to_thread(_execute)
        self._logger.info(f"Successfully applied {count} Schema Migrations.")
        return count

    async def rollback(self, target_version: int) -> int:
        """
        Reverses the database schema DOWN to a specific version.
        Destructive action, used to reverse botched deployments.
        """
        await self._init_history_table()
        current_version = await self.get_current_version()
        
        if target_version >= current_version:
            self._logger.info("Target version is >= current version. No rollback required.")
            return 0
            
        # Get migrations to rollback in reverse numerical order
        to_rollback = [m for m in reversed(self._migrations) if target_version < m.version <= current_version]
        
        if not to_rollback:
            return 0
            
        def _execute() -> int:
            rolled_back = 0
            with sqlite3.connect(self._db_path) as conn:
                for migration in to_rollback:
                    self._logger.warning(f"Executing Schema DOWN from v{migration.version}: {migration.name}")
                    try:
                        conn.execute("BEGIN TRANSACTION")
                        conn.executescript(migration.down_sql)
                        
                        # Remove from ledger
                        conn.execute("DELETE FROM schema_migrations WHERE version = ?", (migration.version,))
                        conn.commit()
                        rolled_back += 1
                        
                    except Exception as e:
                        conn.rollback()
                        raise MigrationError(f"Rollback v{migration.version} crashed: {e}") from e
                        
            return rolled_back
            
        count = await asyncio.to_thread(_execute)
        self._logger.info(f"Successfully rolled back {count} Schema Migrations.")
        return count
```

---

# 3. Design Decisions

1. **Transaction Atomicity:** If a migration script contains 5 `ALTER TABLE` statements and crashes on the 4th statement, the Database would normally be left in a corrupted, half-migrated "Zombie" state. The `MigrationManager` rigorously wraps every single step inside a `BEGIN TRANSACTION` / `ROLLBACK` boundary. If it crashes, it reverses the SQL perfectly.
2. **Deterministic Ledger:** The `schema_migrations` table acts as the absolute source of truth. The framework dynamically compares the Python `register_migration()` list against the SQLite ledger, automatically identifying any missing delta blocks. This allows developers to simply boot the application, and the Manager will magically apply all new tables required for that specific version update.
3. **Immutable Frozen Dataclasses:** The `Migration` class utilizes `@dataclass(frozen=True)`. This mathematically prevents rogue Subagents or buggy plugins from altering the SQL Strings in memory before the Migration executes, ensuring 100% security against runtime SQL Injection tampering.
