"""
Artifact Store module for blob/file artifact persistence.
"""
from pathlib import Path
from typing import Any, Optional


class ArtifactStore:
    """Manages blob artifact persistence."""

    def __init__(self, base_path: str = "data/artifacts") -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, data: bytes) -> Path:
        target = self.base_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def load(self, name: str) -> Optional[bytes]:
        target = self.base_path / name
        if target.exists():
            return target.read_bytes()
        return None


__all__ = ["ArtifactStore"]
