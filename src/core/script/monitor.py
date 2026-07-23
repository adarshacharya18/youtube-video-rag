"""
Telemetry Daemon for the Script Pipeline.

Listens to fire-and-forget telemetry events emitted by the Content Generation
modules. Accumulates metrics in memory for external dashboards (Grafana/Prometheus).
"""

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List

# Assumed imported from events
from src.core.script.events import (ContentEvent, ContentExported,
                                    ContentReviewed, ScriptGenerated)


class ScriptMonitor:
    """Non-blocking metric accumulator for Generative AI operations."""
    
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        
        # In-memory accumulators
        self._generation_latencies: Dict[str, float] = {}
        self._prompt_usage_counts: Dict[str, int] = defaultdict(int)
        self._total_exports: int = 0
        self._total_failures: int = 0
        self._total_retries: int = 0
        
        # Reviewer Scores
        self._review_scores: List[int] = []
        
        # Start time tracking for end-to-end latency measurement
        self._start_times: Dict[str, float] = {}

    def track_start(self, slug: str, module_name: str) -> None:
        """Mark the exact start time of a specific LLM generative task."""
        self._start_times[f"{slug}_{module_name}"] = time.time()
        self._prompt_usage_counts[module_name] += 1

    def track_end(self, slug: str, module_name: str) -> None:
        """Calculate the physical latency of the completed LLM network task."""
        start_key = f"{slug}_{module_name}"
        if start_key in self._start_times:
            latency = time.time() - self._start_times[start_key]
            self._generation_latencies[start_key] = latency
            del self._start_times[start_key]

    def handle_event(self, event: ContentEvent) -> None:
        """Intercepts telemetry events and extracts mathematical insight."""
        
        if isinstance(event, ContentReviewed):
            self._review_scores.append(event.overall_score)
            
            # If the LLM-as-a-Judge flags a hallucination, we track it as a failure
            if not event.is_approved:
                self._total_failures += 1
                self._logger.warning(f"Telemetry Alert: Script '{event.slug}' rejected. Score: {event.overall_score}")
                
        elif isinstance(event, ScriptGenerated):
            self._logger.info(f"Telemetry: Final Script generated for '{event.slug}'. Size: {event.payload_size_bytes} bytes.")
            
        elif isinstance(event, ContentExported):
            self._total_exports += 1
            
    def record_retry(self) -> None:
        """Called when the LLM-as-a-Judge forces an automated prompt rewrite."""
        self._total_retries += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Returns the accumulated telemetry payload for Grafana scraping."""
        avg_score = sum(self._review_scores) / len(self._review_scores) if self._review_scores else 0.0
        
        return {
            "total_exports": self._total_exports,
            "total_failures": self._total_failures,
            "total_retries": self._total_retries,
            "average_review_score": round(avg_score, 2),
            "prompt_usage": dict(self._prompt_usage_counts),
            "generation_latencies_sec": self._generation_latencies
        }
