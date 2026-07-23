"""
Filesystem caching and SHA-256 hashing utility.
"""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.core.paths import ensure_dir
from src.core.serialization import deserialize_json, serialize_json


class FileCache:
    """
    A robust, JSON-backed file cache. Perfect for caching API responses 
    (like LeetCode problems or Gemini tag extractions) to save bandwidth and tokens.
    """

    def __init__(self, cache_dir: Path | str, default_ttl_hours: int = 24 * 7) -> None:
        self._dir = ensure_dir(cache_dir)
        self._default_ttl = timedelta(hours=default_ttl_hours)

    def _hash_key(self, identifier: str) -> str:
        """Generate a deterministic SHA-256 hash for the identifier."""
        return hashlib.sha256(identifier.encode("utf-8")).hexdigest()

    def get(self, identifier: str) -> Any | None:
        """Retrieve data from cache if it has not expired."""
        path = self._dir / f"{self._hash_key(identifier)}.json"
        if not path.exists():
            return None
            
        envelope = deserialize_json(path)
        expires_at_str = envelope.get("expires_at")
        
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now(timezone.utc) > expires_at:
                path.unlink()
                return None
                
        return envelope.get("data")

    def put(self, identifier: str, data: Any, ttl: timedelta | None = None) -> None:
        """Serialize and store data in the cache with an expiration."""
        path = self._dir / f"{self._hash_key(identifier)}.json"
        ttl_to_use = ttl or self._default_ttl
        expires_at = datetime.now(timezone.utc) + ttl_to_use
        
        envelope = {
            "expires_at": expires_at.isoformat(),
            "data": data
        }
        serialize_json(envelope, path)

    async def async_get(self, identifier: str) -> Any | None:
        """Non-blocking async wrapper for get()."""
        return await asyncio.to_thread(self.get, identifier)

    async def async_put(self, identifier: str, data: Any, ttl: timedelta | None = None) -> None:
        """Non-blocking async wrapper for put()."""
        await asyncio.to_thread(self.put, identifier, data, ttl)

    def invalidate(self, identifier: str) -> None:
        """Remove a specific identifier from the cache."""
        path = self._dir / f"{self._hash_key(identifier)}.json"
        if path.exists():
            path.unlink()

    def invalidate_all(self) -> None:
        """Clear the entire cache directory."""
        for file in self._dir.glob("*.json"):
            file.unlink()
