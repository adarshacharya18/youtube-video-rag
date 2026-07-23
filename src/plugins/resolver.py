"""
Plugin Dependency Resolver.

Extracts Directed Acyclic Graph (DAG) sorting and SemVer validation logic
into a standalone, highly testable module.
"""

import logging
from graphlib import CycleError, TopologicalSorter

from src.core.exceptions import PipelineError
from src.plugins.manifest import PluginManifest


class DependencyResolutionError(PipelineError):
    """Raised when plugins have circular dependencies or missing requirements."""
    pass


def parse_semver(version: str) -> tuple[int, int, int]:
    """
    Parses a strict SemVer string into a comparable tuple.
    (e.g., '1.2.14' -> (1, 2, 14)). 
    Safe to use because PluginManifest regex guarantees strict formatting.
    """
    return tuple(map(int, version.split(".")))


class PluginDependencyResolver:
    """
    Mathematically sorts plugins via a DAG to guarantee safe initialization orders.
    Enforces SemVer contracts.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def resolve(self, manifest_dict: dict[str, PluginManifest]) -> list[PluginManifest]:
        """
        Takes a dictionary of discovered manifests and returns them as a 
        list sorted in the exact order they must be initialized.
        """
        sorter = TopologicalSorter()
        
        for m_id, m in manifest_dict.items():
            deps = []
            
            # Combine strict and optional dependencies for processing
            all_dependencies = m.dependencies + m.optional_dependencies
            
            for dep in all_dependencies:
                is_optional = getattr(dep, "optional", False)
                
                # 1. Missing Dependency Check
                if dep.plugin_id not in manifest_dict:
                    if is_optional:
                        self._logger.debug(f"[{m_id}] Optional dep '{dep.plugin_id}' not found. Skipping.")
                        continue
                    else:
                        raise DependencyResolutionError(f"[{m_id}] Missing required dependency: '{dep.plugin_id}'")
                
                target = manifest_dict[dep.plugin_id]
                
                # 2. Version Conflict Check
                if parse_semver(target.version) < parse_semver(dep.min_version):
                    if is_optional:
                        self._logger.warning(
                            f"[{m_id}] Optional dep '{dep.plugin_id}' is v{target.version}, "
                            f"but requires >={dep.min_version}. Skipping."
                        )
                        continue
                    else:
                        raise DependencyResolutionError(
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
            raise DependencyResolutionError(f"Fatal circular dependency detected in plugins: {e}")
            
        return [manifest_dict[pid] for pid in order]
