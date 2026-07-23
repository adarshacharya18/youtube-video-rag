"""
Analytics Dashboard (Phase 15)

Aggregates operational metrics, quality trends, pipeline performance,
and model usage across the entire platform. Designed to export
to a local JSON payload or interact with a UI framework.
"""
import sqlite3
import os
import json
from typing import Dict, Any

class AnalyticsDashboard:
    def __init__(self, 
                 prod_db_path: str = "/var/lib/dsa_pipeline/prod_ledger.sqlite",
                 feedback_db_path: str = "/var/lib/dsa_pipeline/feedback_ledger.sqlite",
                 storage_dir: str = "/var/lib/dsa_pipeline/artifacts"):
        self.prod_db = prod_db_path
        self.feedback_db = feedback_db_path
        self.storage_dir = storage_dir

    def _get_storage_size_bytes(self) -> int:
        """Calculates total disk space consumed by the artifacts directory."""
        total_size = 0
        if not os.path.exists(self.storage_dir):
            return 0
        for dirpath, _, filenames in os.walk(self.storage_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return total_size

    def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Aggregates metrics from the production ledger."""
        metrics = {
            "videos_published": 0,
            "content_generated": 0,
            "failures": 0,
            "recoveries": 0,
            "avg_pipeline_duration_sec": 0
        }
        if not os.path.exists(self.prod_db):
            return metrics

        # STUB: In production, these run actual SELECT statements against the DB
        # e.g., SELECT count(*) FROM state_ledger WHERE status = 'COMPLETED'
        with sqlite3.connect(self.prod_db) as conn:
            pass 

        # Mocking data for implementation scaffolding
        metrics["videos_published"] = 125
        metrics["content_generated"] = 450 # Includes supplementary content (Phase 15/07)
        metrics["failures"] = 12
        metrics["recoveries"] = 12 # 100% recovery rate via Saga patterns
        metrics["avg_pipeline_duration_sec"] = 43200 # 12 hours

        return metrics

    def get_quality_trends(self) -> Dict[str, float]:
        """Aggregates LLM-as-a-Judge and manual review trends."""
        metrics = {
            "overall_quality_avg": 0.0,
            "technical_correctness_avg": 0.0,
            "engagement_score_avg": 0.0
        }
        if not os.path.exists(self.feedback_db):
            return metrics
            
        # Mocking data for implementation scaffolding
        metrics["overall_quality_avg"] = 8.7
        metrics["technical_correctness_avg"] = 9.5
        metrics["engagement_score_avg"] = 8.1
        return metrics
        
    def get_ecosystem_metrics(self, model_manager) -> Dict[str, Any]:
        """Extracts model telemetry and plugin registry usage."""
        metrics = {
            "model_health": model_manager.generate_health_report() if model_manager else {},
            "active_plugins": 3 # Stubbed
        }
        return metrics

    def generate_dashboard_report(self, model_manager=None) -> str:
        """
        Compiles a comprehensive JSON report covering the entire platform.
        """
        report = {
            "pipeline": self.get_pipeline_metrics(),
            "quality": self.get_quality_trends(),
            "ecosystem": self.get_ecosystem_metrics(model_manager),
            "storage_bytes": self._get_storage_size_bytes()
        }
        return json.dumps(report, indent=4)
