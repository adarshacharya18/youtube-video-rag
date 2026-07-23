# Phase05/06_PluginDiscovery.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/plugins/discovery.py`](#2-source-code-srcpluginsdiscoverypy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document specifies the **Plugin Discoverer**. Before the Plugin Loader attempts to `import` raw Python code, the Discoverer safely scans the filesystem for `manifest.yaml` files. 

It acts as a strict firewall:
- **Dependency Resolution:** It mathematically builds a Directed Acyclic Graph (DAG) using Python's native `graphlib`.
- **Circular Dependency Prevention:** Instantly catches loops (e.g., Scraper needs DB, DB needs Scraper) before runtime.
- **Version Conflict Detection:** Ensures that if a plugin requests `core.rag >= 2.0.0`, the system aborts if only `1.0.0` is present.
- **Duplicate Detection:** Automatically drops older versions of a plugin if a newer manifest is discovered in the same directory.

---

# 2. Source Code: `src/plugins/discovery.py`

```python
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


class PluginDiscoveryError(PipelineError):
    """Raised when plugins have circular dependencies or missing requirements."""
    pass


def parse_semver(version: str) -> tuple[int, int, int]:
    """
    Parses a strict SemVer string into a comparable tuple.
    (e.g., '1.2.14' -> (1, 2, 14)). 
    Safe to use because PluginManifest regex guarantees strict formatting.
    """
    return tuple(map(int, version.split(".")))


class PluginDiscoverer:
    """
    Scans the filesystem, parses manifests declaratively, and mathematically
    sorts plugins via a DAG to guarantee safe initialization orders.
    """

    def __init__(self, plugin_dir: Path) -> None:
        self.plugin_dir = plugin_dir
        self._logger = logging.getLogger(__name__)
        
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
            return self._build_dag(self._cache)
            
        raw_manifests = self._scan_filesystem()
        valid_manifests = self._resolve_duplicates(raw_manifests)
        sorted_manifests = self._build_dag(valid_manifests)
        
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

    def _build_dag(self, manifest_dict: dict[str, PluginManifest]) -> list[PluginManifest]:
        """
        Performs Topological Sorting using native graphlib.
        Validates missing requirements and strict version boundaries.
        """
        sorter = TopologicalSorter()
        
        for m_id, m in manifest_dict.items():
            deps = []
            for dep in m.dependencies:
                # 1. Missing Dependency Check
                if dep.plugin_id not in manifest_dict:
                    if dep.optional:
                        self._logger.debug(f"Optional dep '{dep.plugin_id}' missing for '{m_id}'")
                        continue
                    else:
                        raise PluginDiscoveryError(f"[{m_id}] Missing required dependency: '{dep.plugin_id}'")
                
                target = manifest_dict[dep.plugin_id]
                
                # 2. Version Conflict Check
                if parse_semver(target.version) < parse_semver(dep.min_version):
                    raise PluginDiscoveryError(
                        f"[{m_id}] Version conflict! Requires '{dep.plugin_id}' >= {dep.min_version}, "
                        f"but found v{target.version}"
                    )
                    
                deps.append(dep.plugin_id)
                
            # Add node to DAG: target node, followed by predecessors it depends on
            sorter.add(m_id, *deps)
            
        try:
            # Returns the exact order they must be initialized in
            order = list(sorter.static_order())
        except CycleError as e:
            raise PluginDiscoveryError(f"Fatal circular dependency detected in plugins: {e}")
            
        return [manifest_dict[pid] for pid in order]
```

---

# 3. Design Decisions

1. **Native Dependency-Free SemVer:** Because `PluginManifest` forces versions to match `r"^\d+\.\d+\.\d+$"` via Pydantic regex during Phase 05/04, we don't need heavy external libraries like `packaging`. A simple `tuple(map(int, v.split(".")))` guarantees mathematically perfect version comparisons (`(2, 0, 0) > (1, 9, 14)`).
2. **Topological Sorting (`graphlib`):** By utilizing Python's built-in `graphlib.TopologicalSorter`, we get C-optimized, mathematically proven DAG resolution. If `A` needs `B`, `graphlib` ensures `B` is always placed before `A` in the final output list.
3. **Graceful Malform Handling:** In `_scan_filesystem()`, if a JSON manifest is corrupt, we catch the exception, log it as an error, and *continue scanning*. The application must not crash entirely just because a user dropped a broken `manifest.yaml` text file into the plugin directory.
