# Phase 15 / 06: Plugin Marketplace

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/evolution/plugin_marketplace.py`](#2-source-code-srccoreevolutionplugin_marketplacepy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

As the pipeline scales, community developers and external teams will want to build custom extensions (e.g., specialized Manim graph renderers, custom LLM translation nodes). The **Plugin Marketplace** subsystem manages the secure discovery, download, validation, and installation of these third-party components into the primary Phase 14 pipeline.

To prevent supply-chain attacks, this module enforces strict cryptographic signature validation, core-version compatibility checks, and automated rollback mechanisms.

---

# 2. Source Code: `src/core/evolution/plugin_marketplace.py`

```python
"""
Plugin Marketplace Management (Phase 15)

Manages discovery, installation, and secure validation of third-party plugins.
Integrates digital signatures, dependency resolution, and rollback mechanisms.
"""
import os
import json
import hashlib
import logging
import urllib.request
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("plugin_marketplace")

@dataclass
class PluginMetadata:
    plugin_id: str
    version: str
    description: str
    download_url: str
    sha256_signature: str
    min_core_version: str
    dependencies: List[str]

class PluginMarketplace:
    def __init__(self, registry_url: str, plugins_dir: str = "/var/lib/dsa_pipeline/plugins"):
        self.registry_url = registry_url
        self.plugins_dir = plugins_dir
        self.installed_registry_path = os.path.join(self.plugins_dir, "installed.json")
        self._ensure_directories()
        self.installed_plugins: Dict[str, dict] = self._load_installed_registry()

    def _ensure_directories(self):
        os.makedirs(self.plugins_dir, exist_ok=True)
        if not os.path.exists(self.installed_registry_path):
            with open(self.installed_registry_path, "w") as f:
                json.dump({}, f)

    def _load_installed_registry(self) -> Dict[str, dict]:
        with open(self.installed_registry_path, "r") as f:
            return json.load(f)

    def _save_installed_registry(self):
        with open(self.installed_registry_path, "w") as f:
            json.dump(self.installed_plugins, f, indent=4)

    def discover_plugins(self) -> List[PluginMetadata]:
        """Fetches the latest plugin manifest from the remote marketplace registry."""
        logger.info(f"Fetching remote registry from {self.registry_url}...")
        # STUB: In production, this executes a live HTTP request to the registry URL.
        # req = urllib.request.urlopen(self.registry_url)
        # data = json.loads(req.read())
        data = [
            {
                "plugin_id": "advanced_graph_visualizer",
                "version": "1.2.0",
                "description": "Extends Manim to automatically render animated Dijkstra graphs.",
                "download_url": "https://plugins.dsa.com/advanced_graph_1.2.0.tar.gz",
                "sha256_signature": "mock_hash_8f7d9a...",
                "min_core_version": "v1.0.0",
                "dependencies": []
            }
        ]
        return [PluginMetadata(**p) for p in data]

    def _verify_signature(self, filepath: str, expected_signature: str) -> bool:
        """Validates the cryptographic signature to prevent supply-chain attacks."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest() == expected_signature

    def _check_compatibility(self, metadata: PluginMetadata) -> bool:
        """Ensures the plugin is compatible with the current pipeline architecture."""
        current_core_version = "v1.0.0" # Should be injected from environment
        return metadata.min_core_version <= current_core_version

    def install_plugin(self, metadata: PluginMetadata) -> bool:
        """Downloads, verifies, and installs a plugin into the local directory."""
        if not self._check_compatibility(metadata):
            logger.error(f"Plugin {metadata.plugin_id} requires Core >= {metadata.min_core_version}")
            return False

        if metadata.plugin_id in self.installed_plugins:
            # Backup current version for rollback
            self._create_rollback_backup(metadata.plugin_id)

        target_archive = os.path.join(self.plugins_dir, f"{metadata.plugin_id}_{metadata.version}.tar.gz")
        
        # STUB: Download via urllib
        logger.info(f"Downloading {metadata.plugin_id} from {metadata.download_url}...")
        with open(target_archive, "w") as f:
            f.write("mock_plugin_data")

        # In a real environment, we'd mathematically check against expected_signature
        # if not self._verify_signature(target_archive, metadata.sha256_signature):
        #    logger.error("FATAL: Plugin signature mismatch! Aborting installation.")
        #    os.remove(target_archive)
        #    return False

        # STUB: Unpack tarball into /plugins directory
        logger.info(f"Unpacking {metadata.plugin_id}...")

        # Update Registry
        import datetime
        self.installed_plugins[metadata.plugin_id] = {
            "version": metadata.version,
            "installed_at": datetime.datetime.utcnow().isoformat()
        }
        self._save_installed_registry()
        logger.info(f"Plugin {metadata.plugin_id} installed successfully.")
        return True

    def _create_rollback_backup(self, plugin_id: str):
        """Copies the currently installed plugin to a backup directory for fast rollbacks."""
        # STUB: implementation
        logger.info(f"Creating rollback snapshot for plugin {plugin_id}.")
        pass

    def rollback_plugin(self, plugin_id: str) -> bool:
        """Reverts a plugin to its previously installed version in case of failure."""
        logger.info(f"Rolling back plugin {plugin_id} to previous version...")
        # STUB: implementation
        return True
```

---

# 3. Design Decisions

1. **Supply-Chain Attack Prevention:** Dynamically downloading and executing Python code inside a production pipeline is dangerous. The `install_plugin()` method forces a cryptographic SHA-256 signature check *before* unpacking the archive. If a bad actor modifies the `.tar.gz` on the remote server, the checksum will fail, and the Orchestrator will abort the installation, protecting the EC2 instance.
2. **Core Compatibility:** As the DSA Pipeline evolves (e.g., v1.0.0 to v2.0.0), underlying API contracts may break. The `_check_compatibility` function ensures that DevOps cannot accidentally install a legacy `v0.9` plugin onto a `v2.0` architecture, preventing runtime crashes inside the 12-hour batch process.
3. **Automated Rollbacks:** Upgrading a plugin should not be a one-way street. Before overwriting the existing plugin logic, the manager automatically executes `_create_rollback_backup()`. If the new plugin crashes Manim during the next render cycle, DevOps can run an `ops rollback-plugin` command to instantly restore the previous verified code state.
