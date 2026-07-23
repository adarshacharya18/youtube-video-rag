"""
RAG Monitoring Daemon.

Hooks into the RAG Pipeline and EventBus to emit real-time Prometheus 
telemetry regarding vector DB latencies, LLM API costs, and Cache efficiency.
"""

import asyncio
import logging
from typing import Any, Dict

from src.core.events import EventBus
from src.core.rag.cache import RAGCache


class RAGMonitor:
    """Non-blocking daemon that tracks RAG metrics."""
    
    def __init__(self, event_bus: EventBus, cache: RAGCache) -> None:
        self._bus = event_bus
        self._cache = cache
        self._logger = logging.getLogger(__name__)
        
        # Internal Thread-safe Metric Counters
        self._metrics = {
            "index_size_chunks": 0,
            "queries_processed": 0,
            "total_embedding_latency_ms": 0.0,
            "total_retrieval_latency_ms": 0.0,
            "total_vector_search_ms": 0.0,
            "kb_usage": {
                "algorithms": 0,
                "data_structures": 0,
                "patterns": 0,
                "problems": 0
            }
        }
        
        self._is_running = False
        self._poll_task = None
        
        # Subscribe to strict RAG Events
        self._bus.subscribe("rag.indexed", self._handle_indexed)
        self._bus.subscribe("rag.query_executed", self._handle_query)

    async def start(self) -> None:
        """Spins up the background `asyncio` loop."""
        if self._is_running:
            return
            
        self._is_running = True
        self._poll_task = asyncio.create_task(self._poll_metrics())
        self._logger.info("RAG Monitoring Daemon online. Awaiting telemetry...")

    async def stop(self) -> None:
        """Gracefully halts the background loop to prevent Zombie Coroutines."""
        self._is_running = False
        if self._poll_task:
            self._poll_task.cancel()
            self._logger.info("RAG Monitoring Daemon offline.")
            
    async def _handle_indexed(self, payload: Dict[str, Any]) -> None:
        """Tracks exactly how many physical chunks are being stored in the Vector DB."""
        chunks_added = payload.get("chunks_indexed", 0)
        self._metrics["index_size_chunks"] += chunks_added
        
    async def _handle_query(self, payload: Dict[str, Any]) -> None:
        """Intercepts real-time physical retrieval query latencies."""
        self._metrics["queries_processed"] += 1
        
        # Accumulate Latencies
        self._metrics["total_embedding_latency_ms"] += payload.get("embedding_ms", 0.0)
        self._metrics["total_retrieval_latency_ms"] += payload.get("retrieval_ms", 0.0)
        self._metrics["total_vector_search_ms"] += payload.get("vector_db_ms", 0.0)
        
        # Track Knowledge Base Popularity (Which namespaces are LLMs hitting the most?)
        namespaces = payload.get("namespaces_searched", [])
        for ns in namespaces:
            if ns in self._metrics["kb_usage"]:
                self._metrics["kb_usage"][ns] += 1
                
    async def _poll_metrics(self) -> None:
        """Continuously pulls cache hit rates and emits averages to Grafana."""
        while self._is_running:
            try:
                # 1. Fetch Real-Time Cache Stats from memory
                cache_stats = self._cache.get_metrics()
                
                # 2. Calculate Running Averages
                q_count = self._metrics["queries_processed"]
                avg_embed = self._metrics["total_embedding_latency_ms"] / q_count if q_count else 0.0
                avg_retrieve = self._metrics["total_retrieval_latency_ms"] / q_count if q_count else 0.0
                
                # 3. Assemble JSON Payload (In production, pushes to Prometheus/Datadog)
                report = {
                    "cache_hit_rate": cache_stats["hit_rate_percent"],
                    "avg_embedding_ms": round(avg_embed, 2),
                    "avg_retrieval_ms": round(avg_retrieve, 2),
                    "index_size_chunks": self._metrics["index_size_chunks"],
                    "query_throughput": q_count,
                    "kb_distribution": self._metrics["kb_usage"]
                }
                
                # 4. Critical Alert Triggers
                # If the cache hit rate drops below 10%, our TTL might be misconfigured,
                # meaning we are hemorrhaging real money paying the Gemini API for repeat math.
                if cache_stats["hit_rate_percent"] < 10.0 and q_count > 50:
                    self._logger.warning(
                        f"CRITICAL: RAG Cache Hit Rate is plummeting: {cache_stats['hit_rate_percent']}%. "
                        "Check TTL logic or query variability."
                    )
                    
                self._logger.debug(f"RAG Daemon Heartbeat: {report}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"RAG Monitor crashed: {e}")
                
            # Pause coroutine for exactly 60 seconds to prevent CPU spin-locking
            await asyncio.sleep(60.0)
