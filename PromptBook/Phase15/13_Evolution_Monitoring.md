# Phase 15 / 13: Evolution Monitoring

**Author:** Principal Operations Engineer  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/evolution/evolution_monitoring.py`](#2-source-code-srccoreevolutionevolution_monitoringpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

Where the Analytics Dashboard (Phase 15/08) passively aggregates data, the **Evolution Monitoring** module actively scans that data to trigger proactive alerts. 

When running continuous A/B tests on prompts, dynamically swapping models, and installing third-party plugins, the complexity of the platform increases exponentially. This monitor sweeps the Model Manager circuit breakers, verifies Prompt A/B test regression boundaries, and checks the Plugin Registry for available updates, consolidating all warnings into a single diagnostic report that can be piped to Slack, PagerDuty, or Grafana.

---

# 2. Source Code: `src/core/evolution/evolution_monitoring.py`

```python
"""
Evolution Monitoring (Phase 15)

Proactively monitors the evolution subsystems (models, prompts, plugins, upgrades)
and triggers alerts if automated experiments regress or models become unhealthy.
"""
import logging
from typing import Dict, Any, List
from src.core.evolution.analytics_dashboard import AnalyticsDashboard

logger = logging.getLogger("evolution_monitoring")

class EvolutionMonitor:
    def __init__(self, analytics: AnalyticsDashboard):
        self.analytics = analytics
        self.alert_thresholds = {
            "quality_drop_threshold": 1.0,  # Alert if moving average drops by 1.0
            "error_rate_threshold": 0.05,   # Alert if > 5% of pipeline runs fail
        }

    def check_model_health(self, model_manager) -> List[str]:
        """Scans the circuit breakers across all models to detect API outages."""
        alerts = []
        if not model_manager:
            return alerts
            
        health_report = model_manager.generate_health_report()
        for model_id, is_healthy in health_report["status"].items():
            if not is_healthy:
                alerts.append(f"CRITICAL: Model {model_id} circuit breaker is OPEN (Unhealthy).")
                
        for model_id, metrics in health_report["metrics"].items():
            calls = metrics.get("calls", 0)
            errors = metrics.get("errors", 0)
            if calls > 0 and (errors / calls) > self.alert_thresholds["error_rate_threshold"]:
                alerts.append(f"WARNING: Model {model_id} experiencing high error rate ({errors}/{calls}).")
                
        return alerts

    def check_experiment_progress(self, prompt_manager) -> List[str]:
        """Monitors active A/B tests for dangerous quality regressions."""
        alerts = []
        if not prompt_manager:
            return alerts
            
        baseline = prompt_manager.get_baseline_prompt()
        experiments = [p for p in prompt_manager._prompts.values() if not p.is_baseline and p.experiment_weight > 0]
        
        for exp in experiments:
            if prompt_manager.feedback_manager.detect_regression(
                baseline.prompt_id, exp.prompt_id, self.alert_thresholds["quality_drop_threshold"]
            ):
                alerts.append(f"ACTION REQUIRED: Experiment {exp.prompt_id} regressed significantly. Auto-fallback engaged.")
            else:
                logger.info(f"Experiment {exp.prompt_id} is operating within normal quality bounds.")
                
        return alerts

    def check_plugin_updates(self, plugin_marketplace) -> List[str]:
        """Checks remote registry for newer, compatible versions of installed plugins."""
        alerts = []
        if not plugin_marketplace:
            return alerts
            
        try:
            available_plugins = plugin_marketplace.discover_plugins()
            installed = plugin_marketplace.installed_plugins
            
            for metadata in available_plugins:
                plugin_id = metadata.plugin_id
                if plugin_id in installed:
                    current_ver = installed[plugin_id]["version"]
                    # STUB: Simplistic version string comparison (should use SemVer in prod)
                    if metadata.version > current_ver:
                        alerts.append(f"NOTICE: Plugin update available: {plugin_id} (v{current_ver} -> v{metadata.version}).")
        except Exception as e:
            logger.error(f"Failed to check for plugin updates: {e}")
            
        return alerts

    def run_full_diagnostic(self, model_manager=None, prompt_manager=None, plugin_marketplace=None) -> Dict[str, Any]:
        """
        Executes a complete sweep of the evolution platform, aggregating all alerts.
        Ideal for injecting into a CRON job or CI/CD pipeline.
        """
        logger.info("Initiating Evolution Platform Diagnostic Sweep...")
        
        alerts = []
        alerts.extend(self.check_model_health(model_manager))
        alerts.extend(self.check_experiment_progress(prompt_manager))
        alerts.extend(self.check_plugin_updates(plugin_marketplace))
        
        # Check overall pipeline duration and failures from Analytics Dashboard
        pipeline_metrics = self.analytics.get_pipeline_metrics()
        failures = pipeline_metrics.get("failures", 0)
        total = pipeline_metrics.get("content_generated", 1) # Prevent div/0
        
        if (failures / total) > self.alert_thresholds["error_rate_threshold"]:
             alerts.append(f"WARNING: Overall pipeline failure rate exceeded threshold.")
             
        diagnostic_report = {
            "status": "UNHEALTHY" if len(alerts) > 0 else "HEALTHY",
            "active_alerts": alerts,
            "metrics_snapshot": json.loads(self.analytics.generate_dashboard_report(model_manager=model_manager))
        }
        
        return diagnostic_report
```

---

# 3. Design Decisions

1. **Active vs Passive Validation:** The Analytics Dashboard (15/08) is passive; it just calculates averages and counts. The `EvolutionMonitor` is active. It parses those averages against mathematically defined thresholds (e.g., `error_rate_threshold = 0.05`) to determine if human intervention is required.
2. **Unified Incident Generation:** By aggregating `check_model_health`, `check_experiment_progress`, and `check_plugin_updates` into a single `run_full_diagnostic()` call, a DevOps engineer can run one command to instantly see if an LLM is offline, if an A/B test is ruining video quality, or if a critical plugin patch is available.
3. **CI/CD Integration Ready:** The output of `run_full_diagnostic` is a highly structured dictionary containing an explicit `"status": "HEALTHY" | "UNHEALTHY"` key. This makes it trivial to hook into GitHub Actions or GitLab CI; if the sweep returns "UNHEALTHY", the CI pipeline can immediately fail the deployment build and alert the team on Slack.
