"""
Organization Monitoring Daemon.

Subscribes to the EventBus to track exact telemetry of the Knowledge Graph,
Taxonomy Rules, and Curriculum Synthesis.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from src.core.event_bus import EventBus
from src.core.events import Event
from src.core.metrics import MetricsRegistry
from src.core.organization.concept_graph import ConceptGraph
from src.core.organization.taxonomy_manager import TaxonomyManager


class OrganizationMonitor:
    """
    Background daemon that monitors the health and velocity of the Knowledge Organization Engine.
    """
    
    def __init__(
        self, 
        event_bus: EventBus, 
        metrics: MetricsRegistry, 
        graph: ConceptGraph, 
        taxonomy: TaxonomyManager
    ) -> None:
        self._bus = event_bus
        self._metrics = metrics
        self._graph = graph
        self._tax = taxonomy
        self._logger = logging.getLogger(__name__)
        
        # Internal state counters for real-time Prometheus/Grafana polling
        self._validation_failures = 0
        self._paths_generated = 0
        self._taxonomy_updates = 0
        self._indexes_prepared = 0
        
        self._is_running = False
        self._poll_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Hooks into the Event Bus and boots the internal DAG polling loop."""
        if self._is_running:
            return
            
        self._logger.info("Starting Organization Telemetry Daemon...")
        self._is_running = True
        
        # 1. Decoupled Observer Pattern: Safely hook into Phase 10 Events
        self._bus.subscribe("organization.validated", self._handle_validated)
        self._bus.subscribe("organization.path_generated", self._handle_path_generated)
        self._bus.subscribe("organization.taxonomy_updated", self._handle_taxonomy_updated)
        self._bus.subscribe("organization.index_ready", self._handle_index_ready)
        
        # 2. Start DAG size polling loop
        self._poll_task = asyncio.create_task(self._poll_graph_metrics())

    async def stop(self) -> None:
        """Gracefully shuts down the background coroutines."""
        self._is_running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._logger.info("Organization Telemetry Daemon gracefully stopped.")

    # ---------------------------------------------------------
    # Event-Driven Handlers
    # ---------------------------------------------------------
    async def _handle_validated(self, event: Event) -> None:
        # Only track if the diagnostic scan reported a critical failure
        if not event.payload.get("valid", True):
            self._validation_failures += 1
            self._metrics.increment_counter("organization_monitor.validation_failures_total")
            
    async def _handle_path_generated(self, event: Event) -> None:
        self._paths_generated += 1
        self._metrics.increment_counter("organization_monitor.paths_generated_total")
        
    async def _handle_taxonomy_updated(self, event: Event) -> None:
        self._taxonomy_updates += 1
        self._metrics.increment_counter("organization_monitor.taxonomy_updates_total")
        
    async def _handle_index_ready(self, event: Event) -> None:
        self._indexes_prepared += 1
        self._metrics.increment_counter("organization_monitor.indexes_prepared_total")

    # ---------------------------------------------------------
    # RAM State Polling Loop
    # ---------------------------------------------------------
    async def _poll_graph_metrics(self) -> None:
        """
        Periodically polls the ConceptGraph and Taxonomy dictionaries in RAM.
        Runs every 60 seconds without blocking the async event loop.
        """
        while self._is_running:
            try:
                # 1. Track Graph V+E Size (Vertices + Edges)
                concept_count = len(self._graph._nodes)
                edge_count = sum(len(edges) for edges in self._graph._out_edges.values())
                
                self._logger.debug(f"DAG State: {concept_count} Vertices, {edge_count} Edges")
                
                # In Production, we inject these as physical Gauges
                # self._metrics.set_gauge("organization_monitor.graph_nodes", concept_count)
                # self._metrics.set_gauge("organization_monitor.graph_edges", edge_count)
                
                # 2. Track Taxonomy Schema Size
                total_tax = sum(len(cat) for cat in self._tax._cache.values())
                self._logger.debug(f"Taxonomy Dictionary: {total_tax} Canonical IDs tracked.")
                
            except Exception as e:
                self._logger.warning(f"Failed to poll graph metrics (Usually harmless): {e}")
                
            await asyncio.sleep(60.0)

    def get_summary(self) -> Dict[str, Any]:
        """Returns an atomic snapshot of the current organization telemetry."""
        return {
            "concept_count": len(self._graph._nodes),
            "relationship_count": sum(len(edges) for edges in self._graph._out_edges.values()),
            "taxonomy_changes": self._taxonomy_updates,
            "learning_paths_synthesized": self._paths_generated,
            "validation_failures": self._validation_failures,
            "indexes_prepared": self._indexes_prepared
        }
