"""
Runtime Configuration Manager.

Wraps the static Pydantic models to provide dynamic features:
Profiles, Hot Reloading, Runtime Overrides, and Immutable Snapshots.
"""

import logging
import threading
from typing import Any

from src.core.config import PipelineConfig, load_config
from src.core.exceptions import PipelineError


class ConfigValidationError(PipelineError):
    """Raised when a hot-reload or override fails Pydantic validation."""
    pass


class ConfigManager:
    """
    Thread-safe manager for dynamic application configuration.
    Handles runtime overrides and ensures active configurations are immutable.
    """

    def __init__(self, profile: str = "default") -> None:
        self._lock = threading.RLock()
        self._profile = profile
        self._overrides: dict[str, Any] = {}
        self._logger = logging.getLogger(__name__)
        
        # Build the initial configuration during initialization
        self._active_config: PipelineConfig = self._build_config()

    def _build_config(self) -> PipelineConfig:
        """
        Loads base config from disk, applies profiles, applies overrides, 
        and re-runs Pydantic validation.
        """
        # 1. Load base configuration from .env / os.environ
        base_kwargs = load_config().model_dump()
        
        # 2. Apply profile-specific defaults
        if self._profile == "test":
            base_kwargs["log_level"] = "DEBUG"
        elif self._profile == "prod":
            base_kwargs["log_level"] = "INFO"
            
        # 3. Apply runtime overrides (highest precedence)
        base_kwargs.update(self._overrides)
        
        # 4. Re-validate via Pydantic model initialization
        try:
            return PipelineConfig(**base_kwargs)
        except Exception as e:
            raise ConfigValidationError(f"Configuration validation failed: {e}") from e

    @property
    def snapshot(self) -> PipelineConfig:
        """
        Returns the active, immutable configuration snapshot.
        Because PipelineConfig is frozen=True, plugins cannot mutate it.
        """
        with self._lock:
            return self._active_config

    def set_override(self, key: str, value: Any) -> PipelineConfig:
        """
        Applies a runtime override and forces a hot-reload.
        Example: set_override("log_level", "DEBUG")
        """
        with self._lock:
            self._logger.info(f"Applying runtime config override: {key}={value}")
            self._overrides[key] = value
            return self.hot_reload()

    def clear_override(self, key: str) -> PipelineConfig:
        """Removes a runtime override and forces a hot-reload."""
        with self._lock:
            if key in self._overrides:
                self._logger.info(f"Clearing runtime config override: {key}")
                del self._overrides[key]
            return self.hot_reload()

    def set_profile(self, profile: str) -> PipelineConfig:
        """Switches the active environment profile and forces a hot-reload."""
        with self._lock:
            self._logger.info(f"Switching configuration profile to: {profile}")
            self._profile = profile
            return self.hot_reload()

    def hot_reload(self) -> PipelineConfig:
        """
        Forces a rebuild of the configuration from disk and memory.
        If validation fails, the old configuration is perfectly preserved.
        """
        with self._lock:
            self._logger.debug("Executing configuration hot-reload...")
            old_config = self._active_config
            try:
                new_config = self._build_config()
                self._active_config = new_config
                self._logger.info("Configuration hot-reload successful.")
                return new_config
            except ConfigValidationError as e:
                # Rollback on validation failure guarantees the system never crashes
                # into an invalid state during runtime.
                self._active_config = old_config
                self._logger.error("Hot-reload failed. Reverting to previous configuration.", exc_info=True)
                raise
