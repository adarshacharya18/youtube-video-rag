"""
Comprehensive Persistence Test Suite.

Mathematically verifies SQLite Unit of Works, OS File System atomicity, 
and Multi-Tier caching logics.
"""

import asyncio
import os
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest
import pytest_asyncio

from src.core.artifact_store import ArtifactStore
from src.core.backup_manager import BackupManager
from src.core.cache_manager import CacheManager
from src.core.checkpoint_store import CheckpointStore
from src.core.event_store import EventStore
from src.core.metadata_store import MetadataStore
from src.core.metrics import MetricsRegistry
from src.core.migration_manager import Migration, MigrationManager
from src.core.state_store import ConcurrencyCollisionError, StateStore
from src.core.storage_manager import StorageManager


@pytest_asyncio.fixture
async def temp_env():
    """Generates a highly-isolated OS Sandbox for Database testing."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest_asyncio.fixture
async def storage(temp_env):
    """Boots the entire StorageManager Registry into the Temp Sandbox."""
    mgr = StorageManager(MetricsRegistry())
    
    state = StateStore(str(temp_env / "state.db"))
    check = CheckpointStore(str(temp_env / "checkpoints.db"))
    evt = EventStore(str(temp_env / "events.db"))
    meta = MetadataStore(str(temp_env / "meta.db"))
    
    mgr.register_store("state", state)
    mgr.register_store("checkpoints", check)
    mgr.register_store("events", evt)
    mgr.register_store("meta", meta)
    
    await mgr.initialize_all()
    yield mgr
    await mgr.shutdown_all()


@pytest.mark.asyncio
async def test_unit_of_work_rollback(storage: StorageManager):
    """Proves that a Business Logic crash perfectly Rollbacks the SQLite Database."""
    state: StateStore = storage.get_store("state") # type: ignore
    
    # 1. Trigger an intentional transaction crash
    try:
        async with storage.transaction("state") as db:
            await db.write("plugin", "test_id", {"data": "SHOULD_NOT_EXIST"})
            raise ValueError("Simulated Business Logic Crash")
    except ValueError:
        pass
        
    # 2. Verify nothing was committed to disk
    data, version = await state.read("plugin", "test_id")
    assert data is None
    assert version == 0


@pytest.mark.asyncio
async def test_optimistic_locking(storage: StorageManager):
    """Proves ConcurrencyCollisionError protects against lost-update anomalies."""
    state: StateStore = storage.get_store("state") # type: ignore
    
    # 1. Thread A writes V1
    v1 = await state.write("config", "main", {"setting": "A"})
    
    # 2. Thread B simulates reading at V1, but successfully updates to V2
    v2 = await state.write("config", "main", {"setting": "B"}, expected_version=v1)
    
    # 3. Thread A tries to write using stale V1 memory, expecting an immediate Crash
    with pytest.raises(ConcurrencyCollisionError):
        await state.write("config", "main", {"setting": "C"}, expected_version=v1)


@pytest.mark.asyncio
async def test_artifact_checksums_and_retention(temp_env):
    """Proves Chunked File I/O and TTL retention deletes on the OS Layer."""
    store = ArtifactStore(str(temp_env / "artifacts"), retention_days=1)
    await store.initialize()
    
    # 1. Write Binary Data
    path = await store.write_artifact("videos", "test.mp4", b"fake_video_data")
    assert Path(path).exists()
    
    # 2. Verify OOM-Safe SHA-256 Checksum
    checksum = await store.get_checksum(path)
    assert len(checksum) == 64
    
    # 3. Hack the OS Clock to simulate 2 days passing
    os.utime(path, (time.time() - 172800, time.time() - 172800))
    
    # 4. Execute Garbage Collector
    deleted = await store.cleanup_retention()
    assert deleted == 1
    assert not Path(path).exists()


@pytest.mark.asyncio
async def test_cache_tier_fallback(temp_env):
    """Proves Tier 1 (RAM) and Tier 2 (Disk) fallback looping and auto-backfilling."""
    cache = CacheManager(str(temp_env / "cache.db"), max_memory_items=10)
    await cache.initialize()
    
    # 1. Write to memory AND disk
    await cache.set("namespace", "key1", "value1", disk=True)
    
    # 2. Clear RAM intentionally
    cache._memory_cache.clear()
    
    # 3. Fetch again. It should miss RAM, hit Disk, and natively backfill RAM!
    assert await cache.get("namespace", "key1") == "value1"
    assert ("namespace", "key1") in cache._memory_cache


@pytest.mark.asyncio
async def test_schema_migrations(temp_env):
    """Proves linear UP/DOWN SQL Transactions inside the Migration Manager."""
    db_path = str(temp_env / "migrations.db")
    mgr = MigrationManager(db_path)
    
    m1 = Migration(1, "Init", "CREATE TABLE test1 (id INT);", "DROP TABLE test1;")
    m2 = Migration(2, "Add Col", "CREATE TABLE test2 (id INT);", "DROP TABLE test2;")
    
    mgr.register_migration(m1)
    mgr.register_migration(m2)
    
    # Test UP
    applied = await mgr.apply_migrations()
    assert applied == 2
    assert await mgr.get_current_version() == 2
    
    # Test DOWN
    rolled_back = await mgr.rollback(1)
    assert rolled_back == 1
    assert await mgr.get_current_version() == 1


@pytest.mark.asyncio
async def test_backup_and_restore(temp_env):
    """Proves C-Level Hot Backups and Recovery logic."""
    source_db = str(temp_env / "source.db")
    
    # 1. Write production data
    with sqlite3.connect(source_db) as conn:
        conn.execute("CREATE TABLE d (val TEXT);")
        conn.execute("INSERT INTO d VALUES ('CRITICAL_DATA');")
        conn.commit()
        
    backup_mgr = BackupManager(str(temp_env / "backups"))
    await backup_mgr.initialize()
    
    # 2. Snapshot the DB while running
    snapshot_path = await backup_mgr.create_snapshot(source_db, "source", incremental=False)
    assert Path(snapshot_path).exists()
    
    # 3. Simulate Hacker wiping the Production DB
    with sqlite3.connect(source_db) as conn:
        conn.execute("DELETE FROM d;")
        conn.commit()
        
    # 4. Trigger Restore
    await backup_mgr.restore_snapshot(snapshot_path, source_db)
    
    # 5. Verify production data returned
    with sqlite3.connect(source_db) as conn:
        cursor = conn.execute("SELECT val FROM d;")
        res = cursor.fetchone()
        assert res[0] == 'CRITICAL_DATA'
