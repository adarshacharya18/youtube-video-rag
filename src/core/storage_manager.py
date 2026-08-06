"""
Storage Manager module.
Provides connection and transaction management for persistent storage.
"""
import sqlite3
from typing import Any, Optional


class StorageManager:
    """Manages database connection and persistence storage."""

    def __init__(self, connection_url: str = "sqlite:///:memory:") -> None:
        self.connection_url = connection_url
        if connection_url.startswith("sqlite:///"):
            path = connection_url.replace("sqlite:///", "")
            self.conn = sqlite3.connect(path if path else ":memory:")
        else:
            self.conn = sqlite3.connect(":memory:")

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor

    def close(self) -> None:
        self.conn.close()


__all__ = ["StorageManager"]
