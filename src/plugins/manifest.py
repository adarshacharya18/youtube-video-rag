"""
Plugin Manifest Parser.

Defines the declarative configuration schemas for plugins.
Supports loading and validating from JSON or YAML files via Pydantic.
"""

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class PluginDependency(BaseModel):
    """Represents a strict or optional dependency on another plugin."""
    plugin_id: str
    min_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    optional: bool = False


class PluginPermissions(BaseModel):
    """Flags for security capabilities the plugin is requesting."""
    network_access: bool = False
    filesystem_access: bool = False
    database_access: bool = False


class PluginManifest(BaseModel):
    """
    The master declaration of a plugin's identity, requirements, and capabilities.
    Parsed directly from the file system before any Python code is evaluated.
    """
    
    # Identity
    id: str = Field(..., description="Unique string ID (e.g., core.scraper.leetcode)")
    name: str = Field(..., description="Human readable display name")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    author: str
    description: str
    
    # Relationships
    dependencies: list[PluginDependency] = Field(default_factory=list)
    optional_dependencies: list[PluginDependency] = Field(default_factory=list)
    
    # Engine Meta
    capabilities: list[str] = Field(default_factory=list)
    priority: int = Field(default=100, description="Lower number loads earlier")
    permissions: PluginPermissions = Field(default_factory=PluginPermissions)
    min_runtime_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    
    # Dynamic Configuration
    config_schema: dict[str, Any] = Field(
        default_factory=dict, 
        description="JSON Schema defining what custom config this plugin accepts"
    )

    @classmethod
    def load_from_file(cls, path: Path) -> "PluginManifest":
        """
        Safely parses and validates a manifest from disk.
        Supports both JSON and YAML extensions.
        """
        if not path.exists():
            raise FileNotFoundError(f"Manifest not found at {path}")
            
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix == ".json":
                data = json.load(f)
            elif path.suffix in (".yaml", ".yml"):
                data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported manifest format: {path.suffix}. Use .json or .yaml")
                
        # Pydantic automatically validates all fields and regex patterns here
        return cls(**data)
