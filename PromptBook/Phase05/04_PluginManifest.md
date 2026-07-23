# Phase05/04_PluginManifest.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/plugins/manifest.py`](#2-source-code-srcpluginsmanifestpy)
3. [Source Code Update: `src/plugins/base.py`](#3-source-code-update-srcpluginsbasepy)
4. [Design Decisions](#4-design-decisions)

---

# 1. Executive Summary

This document specifies the **Plugin Manifest Definition**. Instead of hardcoding metadata directly into Python class properties, professional architectures (like VS Code or Obsidian) use declarative `manifest.json` or `manifest.yaml` files. 

This enables the Plugin Runtime to parse metadata, resolve dependencies, and check minimum version requirements *without executing a single line of the Plugin's Python code*. This is a massive security and performance gain; the system can reject an outdated or hostile plugin before loading its modules into memory.

---

# 2. Source Code: `src/plugins/manifest.py`

```python
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
```

---

# 3. Source Code Update: `src/plugins/base.py`

*(The base plugin interfaces have been upgraded to utilize the new `PluginManifest` instead of the old `PluginMetadata` dataclass).*

```python
# Updated snippet for src/plugins/base.py

from src.plugins.manifest import PluginManifest

@runtime_checkable
class PluginProtocol(Protocol):
    @property
    def manifest(self) -> PluginManifest: ...
    # ...

class AbstractBasePlugin(abc.ABC):
    @property
    @abc.abstractmethod
    def manifest(self) -> PluginManifest:
        pass
        
    async def initialize(self, context: PluginContext) -> None:
        self._context = context
        self._state = ModuleState.INITIALIZED
        self._logger.info(f"[{self.manifest.name}] Initialized v{self.manifest.version}")
```

---

# 4. Design Decisions

1. **Static Analysis over Runtime Execution:** By offloading metadata to a JSON/YAML manifest, the `PluginLoader` doesn't have to `import` a plugin to figure out what it is. It simply parses the folder for `manifest.yaml`. If the `min_runtime_version` exceeds the current application version, the system safely ignores the folder without ever risking a Python crash or infinite loop from a hostile `__init__.py`.
2. **Pydantic Validation:** The manifest utilizes strict Pydantic `Field` regex validations (e.g., `pattern=r"^\d+\.\d+\.\d+$"`). If a developer typos their plugin version as `v1.2` instead of `1.2.0`, it fails parsing instantly with a crystal clear `ValidationError`, preventing downstream logic from breaking during SemVer comparisons.
3. **Configuration Schema:** I included a `config_schema` field. This enables a future capability where the CLI or Web UI can read the plugin manifest and automatically generate a dynamic settings form (e.g., showing an input box for "OpenAI API Key") purely from the JSON schema.
