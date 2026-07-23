"""
Knowledge Ingestion Pipeline.

The Orchestration layer that wires the Connector, Normalizer, Enricher, and Deduplicator
together into a cohesive, fault-tolerant execution graph.
Publishes telemetry to the Event Bus and metrics to the Metrics Registry.
"""

import json
import logging
from typing import Optional

from src.core.event_bus import EventBus
from src.core.events import Event
from src.core.exceptions import PipelineError
from src.core.memory_service import MemoryService
from src.core.metrics import MetricsRegistry
from src.plugins.ingestion.connector_base import BaseSourceConnector
from src.plugins.ingestion.deduplicator import DeduplicationAction, DeduplicationEngine
from src.plugins.ingestion.enricher import MetadataEnricher
from src.plugins.ingestion.normalizer import ProblemNormalizer


class IngestionError(PipelineError):
    """Raised when the Pipeline completely halts due to an unrecoverable failure."""
    pass


class IngestionPipeline:
    """
    Coordinates the rigid 6-Step Ingestion Finite State Machine.
    """
    def __init__(
        self,
        event_bus: EventBus,
        memory_service: MemoryService,
        metrics: MetricsRegistry,
        normalizer: Optional[ProblemNormalizer] = None,
        enricher: Optional[MetadataEnricher] = None,
        deduplicator: Optional[DeduplicationEngine] = None
    ) -> None:
        # Core Infrastructure
        self._bus = event_bus
        self._memory = memory_service
        self._metrics = metrics
        
        # Sub-Engines
        self._normalizer = normalizer or ProblemNormalizer()
        self._enricher = enricher or MetadataEnricher()
        self._deduplicator = deduplicator or DeduplicationEngine(memory_service)
        
        self._logger = logging.getLogger(__name__)

    async def run_single(self, connector: BaseSourceConnector, uri: str, correlation_id: str) -> None:
        """Executes the pipeline for a single target URI."""
        self._logger.info(f"Starting Ingestion Pipeline for URI: {uri}")
        
        await self._bus.publish(Event(
            topic="ingestion.started",
            payload={"uri": uri, "source": connector.name},
            correlation_id=correlation_id
        ))
        
        # Wraps the entire operation in a metrics timer to track execution latency
        try:
            async with self._metrics.measure_time(f"ingestion.{connector.name}.latency"):
                
                # Step 1 & 2: Fetch & Validate (Validation happens inside connector.fetch)
                raw_content = await connector.fetch(uri)
                self._metrics.increment_counter(f"ingestion.{connector.name}.fetch_success")
                
                # Step 3: Normalize (HTML -> Markdown)
                normalized = self._normalizer.normalize(raw_content)
                
                # Step 4: Enrich (Heuristic Data Structure inference)
                enriched = self._enricher.enrich(normalized)
                
                # Step 5: Deduplicate (SHA-256 Hashing)
                action, final_doc = await self._deduplicator.evaluate(enriched)
                
                # Step 6: Persist (Atomic SQLite UoW)
                if action == DeduplicationAction.SKIP:
                    self._logger.info(f"Skipping identical document: {uri}")
                    self._metrics.increment_counter(f"ingestion.{connector.name}.skipped")
                    
                    await self._bus.publish(Event(
                        topic="ingestion.skipped",
                        payload={"uri": uri, "reason": "DUPLICATE_HASH"},
                        correlation_id=correlation_id
                    ))
                
                elif action in (DeduplicationAction.INSERT, DeduplicationAction.UPDATE):
                    self._logger.info(f"Persisting document: {uri} (Action: {action.value})")
                    
                    # Execute physical persistence via MemoryService Façade
                    await self._memory.store_knowledge_reference(
                        entity_id=final_doc.id,
                        data={
                            "title": final_doc.title, 
                            "markdown": final_doc.markdown, 
                            "metadata": final_doc.metadata
                        },
                        tags=final_doc.tags
                    )
                    
                    self._metrics.increment_counter(f"ingestion.{connector.name}.persisted")
                    await self._bus.publish(Event(
                        topic="ingestion.completed",
                        payload={"uri": uri, "action": action.value},
                        correlation_id=correlation_id
                    ))
                    
                elif action == DeduplicationAction.CONFLICT:
                    self._logger.warning(f"Unresolvable version conflict for: {uri}")
                    self._metrics.increment_counter(f"ingestion.{connector.name}.conflict")
                    
                    await self._bus.publish(Event(
                        topic="ingestion.conflict",
                        payload={"uri": uri},
                        correlation_id=correlation_id
                    ))
                    
        except Exception as e:
            self._logger.error(f"Ingestion Pipeline completely crashed for {uri}: {e}")
            self._metrics.increment_counter(f"ingestion.{connector.name}.error")
            
            # Pushes the crash to the DLQ for automatic retries
            await self._bus.publish(Event(
                topic="ingestion.failed",
                payload={"uri": uri, "error": str(e)},
                correlation_id=correlation_id
            ))
            raise IngestionError(f"Pipeline failed for {uri}") from e

    async def run_stream(self, connector: BaseSourceConnector, stream_uri: str, correlation_id: str) -> None:
        """
        Executes the pipeline for a massive stream (e.g., Pulling 3,000 LeetCode problems).
        Tolerates individual record failures without crashing the entire stream loop.
        """
        self._logger.info(f"Starting Streaming Ingestion Pipeline via {connector.name}")
        count = 0
        
        try:
            # Yields paginated blocks of raw content natively respecting IP Rate Limits
            async for raw_page in connector.fetch_stream(stream_uri):
                
                # LeetCode stream yields a JSON list of slugs inside the content body
                body_str = raw_page.content_body.decode('utf-8') if isinstance(raw_page.content_body, bytes) else raw_page.content_body
                slugs = json.loads(body_str) if isinstance(body_str, str) else []
                
                for slug_obj in slugs:
                    slug = slug_obj.get("titleSlug")
                    if not slug:
                        continue
                        
                    try:
                        # Wait for individual extraction sequentially to respect the BaseConnector Rate Limit
                        await self.run_single(connector, slug, correlation_id)
                        count += 1
                    except Exception as e:
                        self._logger.warning(f"Tolerating failure for {slug} during massive stream: {e}")
                        # Do not raise. The Event Bus already caught it for the DLQ.
                        
        except Exception as e:
            self._logger.error(f"Streaming Engine critically crashed: {e}")
            raise IngestionError(f"Stream failed via {connector.name}") from e
            
        self._logger.info(f"Streaming Ingestion completed. Processed {count} items.")
