#!/usr/bin/env python3
"""
Release Manager (Phase 14)

Automates the packaging, versioning, and checksum generation of the pipeline
source code prior to deployment. Creates immutable rollback tarballs.
"""
import os
import sys
import json
import hashlib
import tarfile
from datetime import datetime
import subprocess

class ReleaseManager:
    def __init__(self, project_root: str, release_dir: str):
        self.project_root = project_root
        self.release_dir = release_dir
        self.version = self._generate_version()
        self.release_history_file = os.path.join(self.release_dir, "release_history.json")

    def _generate_version(self) -> str:
        """Generates a Semantic Version based on git commit and timestamp."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        try:
            commit_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=self.project_root).decode("utf-8").strip()
            return f"v1.0.0-{timestamp}-{commit_hash}"
        except Exception:
            return f"v1.0.0-{timestamp}-local"

    def _calculate_checksum(self, filepath: str) -> str:
        """Generates a SHA-256 checksum for artifact integrity validation."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def package_release(self) -> str:
        """Compresses the source code into a gzip tarball, excluding junk files."""
        os.makedirs(self.release_dir, exist_ok=True)
        archive_name = f"dsa_pipeline_{self.version}.tar.gz"
        archive_path = os.path.join(self.release_dir, archive_name)
        
        def exclude_files(tarinfo):
            # Exclude massive local caches and git histories to keep the tarball < 10MB
            excludes = [".git", "__pycache__", ".pytest_cache", ".venv", "tmp", "PromptBook", "releases"]
            for ex in excludes:
                if ex in tarinfo.name:
                    return None
            return tarinfo

        print(f"Packaging release {self.version}...")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(self.project_root, arcname=f"dsa_pipeline_{self.version}", filter=exclude_files)
            
        print(f"Package created: {archive_path}")
        return archive_path

    def update_history(self, archive_path: str, checksum: str):
        """Maintains an append-only JSON ledger of all releases for rollback routing."""
        history = []
        if os.path.exists(self.release_history_file):
            with open(self.release_history_file, "r") as f:
                history = json.load(f)
                
        # Auto-generate basic release notes from the latest git commit
        try:
            latest_commit = subprocess.check_output(["git", "log", "-1", "--pretty=%B"], cwd=self.project_root).decode("utf-8").strip()
        except Exception:
            latest_commit = "Manual release trigger."

        entry = {
            "version": self.version,
            "timestamp": datetime.utcnow().isoformat(),
            "archive": os.path.basename(archive_path),
            "sha256_checksum": checksum,
            "release_notes": latest_commit
        }
        
        history.append(entry)
        
        with open(self.release_history_file, "w") as f:
            json.dump(history, f, indent=4)
            
        print("Release history updated.")

    def run(self):
        print(f"--- Starting Release Manager ({self.version}) ---")
        archive_path = self.package_release()
        checksum = self._calculate_checksum(archive_path)
        print(f"Checksum (SHA-256): {checksum}")
        self.update_history(archive_path, checksum)
        print("--- Release Complete ---")


if __name__ == "__main__":
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    release_dir = os.path.join(project_root, "releases")
    manager = ReleaseManager(project_root, release_dir)
    manager.run()
