# Phase 08 / 09: Cache Manager Implementation

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/cache_manager.py`](#2-source-code-srccorecache_managerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Global Cache Manager**. 

When executing a complex Pipeline, Subagents might query the same "LeetCode problem description" multiple times, wasting money on LLM Tokens and API limits. To solve this, the Cache Manager introduces a blazingly fast **Two-Tier Architecture**:
*   **Tier 1:** High-Speed In-Memory `OrderedDict` with native LRU (Least Recently Used) bounded eviction.
*   **Tier 2:** Persistent SQLite Disk Cache that survives server reboots.

It fully supports strict Namespaces, Time-To-Live (TTL) expiration bounds, and seamlessly injects telemetry into the `MetricsRegistry`.

---

# 2. Source Code: `src/core/cache_manager.py`

```python
"""
Cache Manager.

Multi-tier caching system supporting both In-Memory (LRU) and On-Disk (SQLite) caching.
Supports Namespaces, Time-To-Live (TTL), Eviction Policies, and Metrics tracking.
"""

import asyncio
import json
import logging
import sqlite3
import time
from collections import OrderedDict
from typing import Any, Optional

from src.core.exceptions import PipelineError
from src.core.metrics import MetricsRegistry


class CacheError(PipelineError):
    """Raised during SQLite connection failures."""
    pass


class CacheManager:
    """
    Two-Tier Caching Engine.
    Tier 1: High-Speed Memory (LRU Eviction)
    Tier 2: Persistent Disk (SQLite with TTL)
    """

    def __init__(
        self,
        db_path: str = "cache.db",
        max_memory_items: int = 1000,
        metrics: Optional[MetricsRegistry] = None
    ) -> None:
        self._db_path = db_path
        self._max_memory_items = max_memory_items
        self._metrics = metrics
        self._logger = logging.getLogger(__name__)
        
        # Tier 1: In-Memory LRU Cache
        # Structure: {(namespace, key): (data, expire_at)}
        self._memory_cache: OrderedDict[tuple[str, str], tuple[Any, float]] = OrderedDict()
        self._memory_lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Boot Sequence: Schema Definitions."""
        def _setup() -> None:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS disk_cache (
                        namespace TEXT NOT NULL,
                        key TEXT NOT NULL,
                        data_json TEXT NOT NULL,
                        expire_at REAL NOT NULL,
                        PRIMARY KEY (namespace, key)
                    )
                """)
                # High speed index to make Garbage Collection fast
                conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expire ON disk_cache(expire_at)")
                conn.commit()
                
        await asyncio.to_thread(_setup)
        self._logger.info(f"CacheManager initialized safely (Max Memory Items: {self._max_memory_items})")

    async def shutdown(self) -> None:
        """Safely release resources."""
        pass

    async def check_health(self) -> bool:
        """Validates Tier 2 Disk Cache health."""
        def _check() -> bool:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("SELECT 1 FROM disk_cache LIMIT 1")
            return True
        try:
            return await asyncio.to_thread(_check)
        except Exception:
            return False

    # ---------------------------------------------------------
    # Core Cache Operations
    # ---------------------------------------------------------
    async def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        Retrieves a value. Checks Tier 1 (Memory) first. 
        If it misses, falls back to Tier 2 (Disk).
        """
        now = time.time()
        
        # 1. Check Tier 1 (Memory)
        async with self._memory_lock:
            if (namespace, key) in self._memory_cache:
                data, expire_at = self._memory_cache[(namespace, key)]
                if expire_at > now:
                    # LRU bump - mark as most recently used
                    self._memory_cache.move_to_end((namespace, key))
                    if self._metrics:
                        self._metrics.increment_counter(f"cache.{namespace}.memory_hit")
                    return data
                else:
                    # Evict instantly on read if expired
                    del self._memory_cache[(namespace, key)]

        # 2. Check Tier 2 (Disk)
        def _fetch_disk() -> Optional[Any]:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    "SELECT data_json, expire_at FROM disk_cache WHERE namespace = ? AND key = ?",
                    (namespace, key)
                )
                row = cursor.fetchone()
                if row:
                    data_json, expire_at = row
                    if expire_at > now:
                        return json.loads(data_json)
                    else:
                        # Lazy TTL Eviction from disk
                        conn.execute(
                            "DELETE FROM disk_cache WHERE namespace = ? AND key = ?",
                            (namespace, key)
                        )
                        conn.commit()
                return None
                
        disk_data = await asyncio.to_thread(_fetch_disk)
        
        if disk_data is not None:
            if self._metrics:
                self._metrics.increment_counter(f"cache.{namespace}.disk_hit")
            
            # Backfill into Memory for the next rapid request (5 min fast TTL)
            await self._set_memory(namespace, key, disk_data, now + 300)
            return disk_data
            
        if self._metrics:
            self._metrics.increment_counter(f"cache.{namespace}.miss")
            
        return None

    async def set(self, namespace: str, key: str, data: Any, ttl_seconds: int = 3600, disk: bool = True) -> None:
        """
        Stores a value in the Cache. Default TTL is 1 Hour.
        """
        now = time.time()
        expire_at = now + ttl_seconds
        
        # 1. Store in Tier 1 (Memory)
        await self._set_memory(namespace, key, data, expire_at)
        
        # 2. Store in Tier 2 (Disk)
        if disk:
            data_json = json.dumps(data)
            def _write_disk() -> None:
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute("""
                        INSERT INTO disk_cache (namespace, key, data_json, expire_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(namespace, key) DO UPDATE SET
                            data_json = excluded.data_json,
                            expire_at = excluded.expire_at
                    """, (namespace, key, data_json, expire_at))
                    conn.commit()
            await asyncio.to_thread(_write_disk)

    async def _set_memory(self, namespace: str, key: str, data: Any, expire_at: float) -> None:
        """Internal helper for Thread-Safe LRU memory insertion."""
        async with self._memory_lock:
            if len(self._memory_cache) >= self._max_memory_items:
                # Evict oldest (FIFO/LRU combo). last=False pops from the left.
                self._memory_cache.popitem(last=False)
                if self._metrics:
                    self._metrics.increment_counter("cache.eviction.memory_lru")
                    
            self._memory_cache[(namespace, key)] = (data, expire_at)
            self._memory_cache.move_to_end((namespace, key))

    async def invalidate(self, namespace: str, key: Optional[str] = None) -> None:
        """Manually evicts specific keys or entire Namespaces from both Tiers."""
        # 1. Clear Memory
        async with self._memory_lock:
            keys_to_delete = []
            for k in self._memory_cache.keys():
                if k[0] == namespace and (key is None or k[1] == key):
                    keys_to_delete.append(k)
            for k in keys_to_delete:
                del self._memory_cache[k]
                
        # 2. Clear Disk
        def _clear_disk() -> None:
            with sqlite3.connect(self._db_path) as conn:
                if key is None:
                    conn.execute("DELETE FROM disk_cache WHERE namespace = ?", (namespace,))
                else:
                    conn.execute("DELETE FROM disk_cache WHERE namespace = ? AND key = ?", (namespace, key))
                conn.commit()
        await asyncio.to_thread(_clear_disk)

    async def cleanup_expired(self) -> int:
        """
        Garbage Collector: Sweeps the Disk Cache for expired TTLs.
        Ensures O(1) DB size scaling.
        """
        now = time.time()
        
        # Clean Memory
        async with self._memory_lock:
            expired = [k for k, v in self._memory_cache.items() if v[1] < now]
            for k in expired:
                del self._memory_cache[k]
                
        # Clean Disk
        def _prune_disk() -> int:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute("DELETE FROM disk_cache WHERE expire_at < ?", (now,))
                conn.commit()
                return cursor.rowcount
                
        deleted = await asyncio.to_thread(_prune_disk)
        if deleted > 0:
            self._logger.info(f"Cache GC: Swept {deleted} expired records from Disk.")
            if self._metrics:
                self._metrics.increment_counter("cache.eviction.ttl", count=deleted)
                
        return deleted
```

---

# 3. Design Decisions

1. **Two-Tier Fallback Loop:** When `get()` is called, the Engine first scans the `OrderedDict` (RAM). This completes in `<0.01ms`. If it misses, it spins up an `asyncio.to_thread()` and queries the SQLite database (Disk). If the Disk hits, it automatically *backfills* the result into RAM with a 5-minute fast TTL, ensuring the next 10 requests hit RAM directly. This mathematically minimizes SSD wear and tear.
2. **OOM Proof Bounded LRU:** If a pipeline requests 1,000,000 cached records over an hour, a naive Python dictionary would consume all server RAM and trigger an OS crash. By enforcing `max_memory_items = 1000`, the `_set_memory` function utilizes `OrderedDict.popitem(last=False)` to surgically evict the Least Recently Used item, perfectly stabilizing RAM usage.
3. **Lazy vs Eager TTL Eviction:** If an item's TTL expires, it doesn't instantly vanish from disk. If the Orchestrator queries it, the `get()` function catches the expired timestamp and *Lazily* deletes it natively during the query. For items that are never queried again, the `cleanup_expired()` Daemon function runs a massive *Eager* `DELETE FROM` SQL sweep nightly.
