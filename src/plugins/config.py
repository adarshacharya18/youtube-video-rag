"""
Plugin Configuration Engine.

Manages dynamic configuration payloads for individual plugins.
Handles JSON schema validation, environment variable overrides, profiles,
and immutable snapshots.
"""

import copy
import logging
import os
from typing import Any

from src.core.exceptions import PipelineError
from src.plugins.manifest import PluginManifest


class PluginConfigError(PipelineError):
    """Raised when a plugin configuration fails schema validation."""
    pass


class PluginConfigManager:
    """
    Handles the configuration lifecycle for a specific plugin instance.
    Validates runtime updates against the plugin's declarative manifest schema.
    """

    def __init__(self, manifest: PluginManifest, profile: str = "default") -> None:
        self.manifest = manifest
        self.profile = profile
        self._logger = logging.getLogger(f"plugin.config.{manifest.id}")
        
        # The immutable snapshot of the currently active configuration
        self._current_snapshot: dict[str, Any] = {}
        
        self._build_initial_snapshot()

    def _build_initial_snapshot(self) -> None:
        """
        Constructs the baseline configuration by merging:
        1. Manifest JSON Schema Defaults
        2. Environment Variables
        """
        base: dict[str, Any] = {}
        
        # 1. Load schema defaults if defined
        schema = self.manifest.config_schema
        if schema and "properties" in schema:
            for key, meta in schema["properties"].items():
                if isinstance(meta, dict) and "default" in meta:
                    base[key] = meta["default"]
                    
        # 2. Apply Environment Variables (e.g., PLUGIN_CORE_VOICE_ELEVENLABS_API_KEY)
        prefix = f"PLUGIN_{self.manifest.id.upper().replace('.', '_')}_"
        for env_k, env_v in os.environ.items():
            if env_k.startswith(prefix):
                key = env_k[len(prefix):].lower()
                
                # Basic string casting
                if env_v.lower() in ("true", "1", "yes"):
                    base[key] = True
                elif env_v.lower() in ("false", "0", "no"):
                    base[key] = False
                elif env_v.isdigit():
                    base[key] = int(env_v)
                else:
                    base[key] = env_v
                    
        self._current_snapshot = self._validate_and_freeze(base)
        self._logger.debug(f"Baseline configuration built for profile '{self.profile}'.")

    def _validate_and_freeze(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Validates the dictionary against the plugin's config_schema.
        Returns a deep-copied snapshot to prevent accidental reference mutations.
        """
        schema = self.manifest.config_schema
        if not schema:
            # If the plugin didn't define a schema, accept anything.
            return copy.deepcopy(payload)
            
        try:
            import jsonschema
            jsonschema.validate(instance=payload, schema=schema)
        except ImportError:
            self._logger.warning("jsonschema module not found. Skipping strict schema validation.")
        except Exception as e:
            raise PluginConfigError(f"Configuration validation failed: {e}") from e
            
        return copy.deepcopy(payload)

    @property
    def snapshot(self) -> dict[str, Any]:
        """
        Returns a deep copy of the active configuration.
        This guarantees Plugins cannot mutate their config dictionary directly.
        """
        return copy.deepcopy(self._current_snapshot)

    def update(self, overrides: dict[str, Any]) -> dict[str, Any]:
        """
        Applies a runtime configuration update (e.g., triggered via API).
        Validates the new payload against the schema before committing it to memory.
        """
        new_payload = copy.deepcopy(self._current_snapshot)
        new_payload.update(overrides)
        
        self._current_snapshot = self._validate_and_freeze(new_payload)
        self._logger.info(f"Runtime configuration updated successfully.")
        
        return self.snapshot

    def get(self, key: str, default: Any = None) -> Any:
        """Convenience accessor for fetching specific configuration flags."""
        return self._current_snapshot.get(key, default)
