# Phase 15 / 10: Compatibility Manager

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/evolution/compatibility_manager.py`](#2-source-code-srccoreevolutioncompatibility_managerpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

As the platform evolves, components will inevitably fall out of sync. A new AI model might lack `json_mode`, a third-party plugin might require Core `v2.0` when the system is running `v1.5`, or the SQLite database schema might be missing a column required by the latest Python deployment. 

The **Compatibility Manager** enforces strict semantic versioning (SemVer) checks across the entire ecosystem. By running these validations as a preflight check *before* kicking off a 12-hour batch process, the system prevents catastrophic runtime errors that would otherwise corrupt data midway through a render.

---

# 2. Source Code: `src/core/evolution/compatibility_manager.py`

```python
"""
Compatibility Manager (Phase 15)

Enforces versioning constraints across plugins, workflows, configurations,
database schemas, and AI models to ensure safe pipeline execution.
"""
import logging
from packaging import version
from typing import Dict, Any, List

logger = logging.getLogger("compatibility_manager")

class CompatibilityManager:
    def __init__(self, core_version: str):
        self.core_version = version.parse(core_version)
        
    def validate_plugin_compatibility(self, plugin_min_core: str, plugin_id: str) -> bool:
        """Ensures the plugin supports the currently running Core architecture."""
        try:
            req_version = version.parse(plugin_min_core)
            if self.core_version < req_version:
                logger.error(f"Plugin {plugin_id} requires Core {plugin_min_core}, but running {self.core_version}")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to parse version for plugin {plugin_id}: {e}")
            return False

    def validate_schema_compatibility(self, db_schema_version: str, required_schema_version: str) -> bool:
        """Ensures the SQLite ledger schema matches the code's expectations."""
        try:
            current = version.parse(db_schema_version)
            required = version.parse(required_schema_version)
            
            # Schema must exactly match major version.
            if current.major != required.major:
                logger.error(f"Schema Major mismatch: DB is {current}, Code requires {required}")
                return False
                
            # If DB is older than code, migrations must be run first.
            if current < required:
                logger.error(f"Schema is outdated: DB is {current}, Code requires {required}. Run migrations.")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Schema version parsing error: {e}")
            return False

    def validate_model_compatibility(self, model_id: str, capabilities: List[str], required_capabilities: List[str]) -> bool:
        """Ensures the selected LLM/TTS model possesses the required features (e.g., 'json_mode')."""
        missing = [cap for cap in required_capabilities if cap not in capabilities]
        if missing:
            logger.error(f"Model {model_id} lacks required capabilities: {missing}")
            return False
        return True

    def validate_workflow_compatibility(self, workflow_version: str) -> bool:
        """Ensures the workflow JSON definition is compatible with the orchestrator."""
        try:
            wf_ver = version.parse(workflow_version)
            # Only support workflows designed for the current major architecture.
            if wf_ver.major != self.core_version.major:
                logger.error(f"Workflow version {workflow_version} is incompatible with Core {self.core_version}")
                return False
            return True
        except Exception as e:
            logger.error(f"Workflow version parsing error: {e}")
            return False
            
    def run_preflight_checks(self, 
                             db_version: str, 
                             req_db_version: str, 
                             workflow_version: str,
                             plugins: List[Dict[str, str]]) -> bool:
        """
        Executes a comprehensive compatibility audit before starting a 12-hour batch.
        Returns True if the entire ecosystem is compatible, otherwise False.
        """
        logger.info("Running ecosystem compatibility preflight checks...")
        
        is_valid = True
        
        if not self.validate_schema_compatibility(db_version, req_db_version):
            is_valid = False
            
        if not self.validate_workflow_compatibility(workflow_version):
            is_valid = False
            
        for plugin in plugins:
            if not self.validate_plugin_compatibility(plugin["min_core"], plugin["id"]):
                is_valid = False
                
        if is_valid:
            logger.info("All compatibility checks passed.")
        else:
            logger.error("FATAL: Compatibility checks failed. Aborting pipeline startup.")
            
        return is_valid
```

---

# 3. Design Decisions

1. **Semantic Versioning (SemVer) Enforcement:** By utilizing the `packaging.version` library, the manager can perform mathematically accurate comparisons (e.g., correctly understanding that `v1.10.0` is greater than `v1.9.0`). It strictly enforces major-version lock-ins, preventing `v2.0` plugins from running on a `v1.0` core architecture.
2. **Capability-Based Model Validation:** Instead of hardcoding checks like `if model == 'gpt-4o'`, the system uses feature-flag capabilities (`validate_model_compatibility`). If a generation step strictly requires `"json_mode"`, the pipeline can safely route to *any* model (OpenAI or Anthropic) as long as it exposes that capability, preventing runtime JSON parsing errors later in the pipeline.
3. **Fail-Fast Preflight:** The `run_preflight_checks()` method is designed to be injected directly into the `deploy.py` or startup routine from Phase 14. If a schema is outdated, the pipeline instantly aborts and alerts DevOps to run database migrations *before* it spins up expensive GPU instances for Manim rendering.
