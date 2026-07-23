"""
Plugin Discovery Engine.

Scans the filesystem for plugin manifests, validates dependencies,
resolves version conflicts, and returns a topologically sorted list of
valid plugins ready for memory loading.
"""

import logging
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Optional

from src.core.exceptions import PipelineError
from src.plugins.manifest import PluginManifest
from src.plugins.resolver import PluginDependencyResolver, parse_semver


class PluginDiscoveryError(PipelineError):
    """Raised when plugins have circular dependencies or missing requirements."""
    pass


class PluginDiscoverer:
    """
    Scans the filesystem, parses manifests declaratively, and delegates
    mathematical DAG sorting to the DependencyResolver.
    """

    def __init__(self, plugin_dir: Path) -> None:
        self.plugin_dir = plugin_dir
        self._logger = logging.getLogger(__name__)
        self.resolver = PluginDependencyResolver()
        
        # Cache of parsed manifests to accelerate rapid hot-reloads
        self._cache: dict[str, PluginManifest] = {}

    def discover(self, force_rescan: bool = False) -> list[PluginManifest]:
        """
        Executes the discovery pipeline: Scan -> Deduplicate -> Sort (DAG).
        Returns a perfectly ordered list of manifests safe for loading.
        """
        if not self.plugin_dir.exists():
            self._logger.warning(f"Plugin directory {self.plugin_dir} does not exist.")
            return []

        if self._cache and not force_rescan:
            self._logger.debug("Returning cached discovery graph.")
            return self.resolver.resolve(self._cache)
            
        raw_manifests = self._scan_filesystem()
        valid_manifests = self._resolve_duplicates(raw_manifests)
        sorted_manifests = self.resolver.resolve(valid_manifests)
        
        # Update cache on successful DAG generation
        self._cache = valid_manifests
        return sorted_manifests
        
    def _scan_filesystem(self) -> list[PluginManifest]:
        """Recursively scans the directory for valid manifest files."""
        manifests = []
        for path in self.plugin_dir.rglob("manifest.*"):
            if path.suffix not in [".json", ".yaml", ".yml"]:
                continue
                
            try:
                manifest = PluginManifest.load_from_file(path)
                manifest._source_path = path.parent  # Dynamically attach the directory path
                manifests.append(manifest)
                self._logger.debug(f"Discovered manifest: {manifest.id} v{manifest.version}")
            except Exception as e:
                # Log the error but do NOT crash the discovery process.
                # A malformed 3rd party manifest should just be ignored.
                self._logger.error(f"Malformed manifest at {path}: {e}")
                
        return manifests

    def _resolve_duplicates(self, manifests: list[PluginManifest]) -> dict[str, PluginManifest]:
        """
        Detects duplicate plugin IDs.
        If a collision occurs, it mathematically keeps the highest SemVer.
        """
        resolved: dict[str, PluginManifest] = {}
        
        for m in manifests:
            if m.id in resolved:
                existing = resolved[m.id]
                self._logger.warning(f"Duplicate plugin ID found: {m.id}")
                
                if parse_semver(m.version) > parse_semver(existing.version):
                    self._logger.info(f"Upgrading {m.id} to {m.version} and dropping {existing.version}")
                    resolved[m.id] = m
                else:
                    self._logger.info(f"Ignoring older duplicate {m.id} v{m.version}")
            else:
                resolved[m.id] = m
                        return resolved
