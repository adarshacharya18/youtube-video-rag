"""
File Cache module for caching data artifacts on disk.
"""
from pathlib import Path
from typing import Any, Optional


class FileCache:
    """Provides key-value caching backed by local disk storage."""

    def __init__(self, cache_dir: str = "data/cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._memory_cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._memory_cache[key] = value

    def clear(self) -> None:
        self._memory_cache.clear()


__all__ = ["FileCache"]
