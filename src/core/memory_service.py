"""
Memory Service module.
Provides memory storage and retrieval over StorageManager.
"""
from typing import Any, Optional
from src.core.storage_manager import StorageManager


class MemoryService:
    """Manages short-term and long-term memory records for pipeline components."""

    def __init__(self, storage_manager: Optional[StorageManager] = None) -> None:
        self.storage_manager = storage_manager or StorageManager()
        self._store: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def exists(self, key: str) -> bool:
        return key in self._store


__all__ = ["MemoryService"]
