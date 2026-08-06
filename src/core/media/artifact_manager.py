"""
Artifact Manager module.
"""
from pathlib import Path
from typing import Any, Optional


class ArtifactManager:
    """Manages disk space and artifact tracking for media generation."""

    def __init__(self, base_dir: str = "data/artifacts") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_path(self, name: str) -> Path:
        return self.base_dir / name


__all__ = ["ArtifactManager"]
