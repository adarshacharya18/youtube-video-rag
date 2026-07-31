"""
Compatibility Manager (Phase 15).

Enforces semantic versioning constraints between the core platform
and third-party plugins to prevent illegal upgrades that could break
the pipeline at runtime.
"""

from typing import Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


class CompatibilityManager:
    """Semantic versioning compatibility checker.

    Compares a plugin's *required* core version against the actual
    ``core_version`` to decide whether the plugin is safe to load.
    A plugin is compatible if its required version is ≤ the core version
    (major.minor.patch comparison).
    """

    def __init__(self, core_version: str) -> None:
        """
        Args:
            core_version: Current platform core version (e.g. '2.0.0').
        """
        self.core_version = core_version
        self._core_tuple = self._parse_semver(core_version)

    def validate_plugin_compatibility(
        self,
        required_version: str,
        plugin_name: str,
    ) -> bool:
        """Check whether *plugin_name* requiring *required_version* is compatible.

        A plugin is compatible when its required version ≤ core_version.

        Args:
            required_version: Minimum core version the plugin requires.
            plugin_name: Human-readable plugin name (for logging).

        Returns:
            True if compatible, False otherwise.
        """
        required_tuple = self._parse_semver(required_version)

        compatible = required_tuple <= self._core_tuple

        if compatible:
            logger.info(
                "Plugin compatibility check passed",
                plugin_name=plugin_name,
                required=required_version,
                core=self.core_version,
            )
        else:
            logger.warning(
                "Plugin compatibility check FAILED",
                plugin_name=plugin_name,
                required=required_version,
                core=self.core_version,
            )

        return compatible

    @staticmethod
    def _parse_semver(version: str) -> tuple[int, int, int]:
        """Parse a 'major.minor.patch' string into a comparable tuple."""
        parts = version.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
