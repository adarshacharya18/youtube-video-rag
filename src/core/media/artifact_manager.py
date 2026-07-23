"""
Media Artifact Manager Subsystem (Phase 13)

Provides deterministic tracking, checksum validation, and retention lifecycle 
management for all massive binary files generated throughout the pipeline.
"""
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional


@dataclass
class ArtifactRecord:
    """Metadata for a single physical file artifact."""
    artifact_id: str
    artifact_type: str  # ENUM: script, audio, animation, video, subtitle, thumbnail
    file_path: str
    checksum_sha256: str
    size_bytes: int
    created_at: datetime
    version: int


class ArtifactManager:
    """
    Manages the lifecycle and integrity of pipeline artifacts on disk.
    Allows the pipeline to safely resume from crashes by validating existing files.
    """
    
    def __init__(self, base_storage_dir: str = "/tmp/youtube_pipeline/artifacts"):
        self._logger = logging.getLogger(__name__)
        self.base_dir = Path(base_storage_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.base_dir / "artifact_registry.json"
        
        # In-memory index of tracked artifacts
        self._registry: Dict[str, ArtifactRecord] = self._load_registry()

    def _load_registry(self) -> Dict[str, ArtifactRecord]:
        """Loads the JSON ledger from disk to persist state across process restarts."""
        if not self.registry_file.exists():
            return {}
        try:
            with open(self.registry_file, "r") as f:
                data = json.load(f)
                return {
                    k: ArtifactRecord(
                        **{**v, "created_at": datetime.fromisoformat(v["created_at"])}
                    ) for k, v in data.items()
                }
        except Exception as e:
            self._logger.error(f"Failed to load artifact registry ledger: {e}")
            return {}

    def _save_registry(self) -> None:
        """Flushes the in-memory ledger to disk atomically."""
        with open(self.registry_file, "w") as f:
            serializable = {
                k: {**asdict(v), "created_at": v.created_at.isoformat()}
                for k, v in self._registry.items()
            }
            json.dump(serializable, f, indent=2)

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculates a SHA-256 hash of a physical file for corruption detection."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in 4K chunks to prevent MemoryErrors on 50GB video files
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def register_artifact(self, artifact_type: str, file_path: str) -> ArtifactRecord:
        """
        Ingests a new file into the tracking system, calculating its checksum
        and versioning it against previous iterations.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Cannot register missing artifact: {file_path}")
            
        self._logger.debug(f"Calculating SHA-256 for {path.name}...")
        checksum = self._calculate_checksum(path)
        size = path.stat().st_size
        
        # Determine version based on existing artifacts of the same ID
        artifact_id = f"{artifact_type}_{path.stem}"
        existing = self._registry.get(artifact_id)
        version = existing.version + 1 if existing else 1
        
        record = ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            file_path=str(path.absolute()),
            checksum_sha256=checksum,
            size_bytes=size,
            created_at=datetime.utcnow(),
            version=version
        )
        
        self._registry[artifact_id] = record
        self._save_registry()
        self._logger.info(f"Registered {artifact_type.upper()} artifact: {artifact_id} (v{version})")
        return record

    def validate_artifact(self, artifact_id: str) -> bool:
        """
        Cryptographically verifies that a file has not been corrupted on disk.
        Critical for allowing the Pipeline Orchestrator to safely resume operations.
        """
        record = self._registry.get(artifact_id)
        if not record:
            self._logger.error(f"Artifact {artifact_id} not found in registry.")
            return False
            
        path = Path(record.file_path)
        if not path.exists():
            self._logger.error(f"Artifact {artifact_id} physical file is missing.")
            return False
            
        self._logger.debug(f"Verifying SHA-256 integrity for {artifact_id}...")
        current_checksum = self._calculate_checksum(path)
        if current_checksum != record.checksum_sha256:
            self._logger.critical(f"CORRUPTION DETECTED: {artifact_id} checksum mismatch!")
            return False
            
        return True

    def execute_retention_policy(self, max_age_days: int = 30) -> int:
        """
        Deletes physical files and registry entries older than max_age_days
        to prevent the server's disk from filling up with old video renders.
        """
        self._logger.info(f"Executing Artifact Retention Policy (Max Age: {max_age_days} days)")
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        deleted_count = 0
        to_remove = []
        
        for artifact_id, record in self._registry.items():
            if record.created_at < cutoff:
                path = Path(record.file_path)
                if path.exists():
                    path.unlink()  # Physically delete the file from the OS
                to_remove.append(artifact_id)
                deleted_count += 1
                
        # Purge from the JSON ledger
        for aid in to_remove:
            del self._registry[aid]
            
        if deleted_count > 0:
            self._save_registry()
            self._logger.info(f"Retention policy successfully purged {deleted_count} stale artifacts.")
        else:
            self._logger.info("Disk is clean. No stale artifacts found.")
            
        return deleted_count
