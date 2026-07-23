"""
Artifact Blob Store.

Manages physical File I/O for massive generated binaries (MP4s, WAVs, Scripts).
Implements StoreProtocol. Supports SHA-256 Checksum generation, 
Categorized routing, and automated Time-To-Live (TTL) Pruning.
"""

import asyncio
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Union

from src.core.exceptions import PipelineError


class ArtifactStoreError(PipelineError):
    """Raised during Missing File errors, OS Permission locks, or Disk Full scenarios."""
    pass


class ArtifactStore:
    """
    Physical OS File System abstraction layer.
    """

    def __init__(self, base_dir: str = "storage/artifacts", retention_days: int = 30) -> None:
        self._base_dir = Path(base_dir).resolve()
        self._retention_days = retention_days
        self._logger = logging.getLogger(__name__)

        # Pre-defined strict topologies
        self._categories = ["scripts", "voice", "animation", "videos", "logs", "reports"]

    async def initialize(self) -> None:
        """Boot Sequence: Ensures absolute folder hierarchies physically exist on disk."""
        def _setup() -> None:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            for category in self._categories:
                (self._base_dir / category).mkdir(exist_ok=True)
                
        await asyncio.to_thread(_setup)
        self._logger.info(f"ArtifactStore initialized safely at {self._base_dir}")

    async def shutdown(self) -> None:
        """No persistent socket connections to flush for pure OS I/O."""
        pass

    async def check_health(self) -> bool:
        """
        Proves we have active OS Write/Delete Permissions.
        (Critical if running inside a locked-down Docker Container).
        """
        def _check() -> bool:
            test_file = self._base_dir / ".healthcheck"
            try:
                test_file.touch()
                test_file.unlink()
                return True
            except (PermissionError, OSError):
                return False
                
        return await asyncio.to_thread(_check)

    # ---------------------------------------------------------
    # Blob I/O Operations
    # ---------------------------------------------------------
    async def write_artifact(self, category: str, filename: str, content: Union[bytes, str]) -> str:
        """
        Asynchronously writes massive data blocks to the SSD and returns the Absolute Path.
        """
        target_dir = self._base_dir / category
        if not target_dir.exists():
            raise ArtifactStoreError(f"FATAL: '{category}' is not a rigorously defined storage category.")
            
        file_path = target_dir / filename
        
        def _write() -> str:
            # Dynamically handle text scripts vs binary video/audio streams
            mode = "wb" if isinstance(content, bytes) else "w"
            encoding = None if isinstance(content, bytes) else "utf-8"
            
            with open(file_path, mode, encoding=encoding) as f:
                f.write(content)
            return str(file_path)
            
        path = await asyncio.to_thread(_write)
        self._logger.debug(f"Saved physical artifact: {path}")
        return path

    async def read_artifact(self, category: str, filename: str, as_bytes: bool = True) -> Union[bytes, str]:
        """Loads an artifact from disk."""
        file_path = self._base_dir / category / filename
        if not file_path.exists():
            raise ArtifactStoreError(f"FATAL: Physical artifact missing from disk: {file_path}")
            
        def _read() -> Union[bytes, str]:
            mode = "rb" if as_bytes else "r"
            encoding = None if as_bytes else "utf-8"
            with open(file_path, mode, encoding=encoding) as f:
                return f.read()
                
        return await asyncio.to_thread(_read)
        
    async def get_checksum(self, filepath: str) -> str:
        """
        Calculates SHA-256 Checksums.
        Mathematically verifies that a video render did not suffer silent corruption.
        """
        def _calc() -> str:
            path = Path(filepath)
            if not path.exists():
                raise ArtifactStoreError(f"Cannot checksum missing file: {filepath}")
            
            sha256 = hashlib.sha256()
            
            # Stream into memory in 64kb chunks.
            # If we loaded a 5GB video into RAM using read(), it would instantly trigger an OOM crash.
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
            
        return await asyncio.to_thread(_calc)

    async def cleanup_retention(self) -> int:
        """
        Physically unlinks files older than TTL (retention_days).
        Guarantees O(1) Disk Space Scaling over years of continuous Video Generation.
        """
        deleted_count = 0
        cutoff = time.time() - (self._retention_days * 86400)
        
        def _prune() -> int:
            nonlocal deleted_count
            for root, _, files in os.walk(self._base_dir):
                for name in files:
                    filepath = Path(root) / name
                    if name == ".healthcheck": 
                        continue
                    
                    try:
                        # Fetch the OS Last Modified timestamp
                        mtime = filepath.stat().st_mtime
                        if mtime < cutoff:
                            filepath.unlink()
                            deleted_count += 1
                    except Exception as e:
                        self._logger.warning(f"Retention Pruner failed to delete artifact '{filepath}': {e}")
            return deleted_count
            
        await asyncio.to_thread(_prune)
        if deleted_count > 0:
            self._logger.info(f"Artifact Retention: Safely purged {deleted_count} stale physical OS files.")
        return deleted_count
