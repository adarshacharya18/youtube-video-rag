"""
Evolution Monitoring (Phase 15)

Proactively monitors the evolution subsystems (models, prompts, plugins, upgrades)
and triggers alerts if automated experiments regress or models become unhealthy.
"""
import logging
import json
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
