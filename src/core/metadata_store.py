"""
Metadata Store module for structured metadata persistence.
"""
from typing import Any, Dict, Optional


class MetadataStore:
    """Manages structured metadata persistence."""

    def __init__(self) -> None:
        self._metadata: Dict[str, Any] = {}

    def save(self, key: str, metadata: Dict[str, Any]) -> None:
        self._metadata[key] = metadata

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._metadata.get(key)


__all__ = ["MetadataStore"]
