"""
Ingestion CLI Module.

Provides command-line interfaces for manually triggering the extraction 
of knowledge from various sources (e.g., LeetCode, Wikipedia).
"""

import argparse
import asyncio
import logging
import sys
import uuid
from typing import List, Optional

from src.core.event_bus import EventBus
from src.core.memory_service import MemoryService
from src.core.metrics import MetricsRegistry
from src.core.storage_manager import StorageManager

from src.plugins.ingestion.connector_base import BaseSourceConnector
from src.plugins.ingestion.leetcode_connector import LeetCodeConnector
from src.plugins.ingestion.pipeline import IngestionPipeline


def setup_logger() -> None:
    """Configures strict terminal output formatting."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )


async def _run_ingestion(args: argparse.Namespace) -> int:
    """Core async execution block for the CLI."""
    setup_logger()
    logger = logging.getLogger("CLI.Ingestion")
    
    # 1. Initialize Core Infrastructure (In Prod, these are loaded from a DI Container)
    # Using an ephemeral in-memory SQLite DB for CLI dry-runs by default
    storage = StorageManager("sqlite:///:memory:") 
    bus = EventBus()
    metrics = MetricsRegistry()
    memory = MemoryService(storage)
    
    pipeline = IngestionPipeline(
        event_bus=bus,
        memory_service=memory,
        metrics=metrics
    )
    
    # 2. Resolve the Target Connector Plugin
    connector: BaseSourceConnector
    if args.source.lower() == "leetcode":
        connector = LeetCodeConnector()
        # In a production environment, `authenticate()` would pull secrets from ENV vars here
    else:
        logger.error(f"Unsupported source target: {args.source}")
        return 1
        
    try:
        # All events fired by this CLI invocation share this exact tracing UUID
        correlation_id = str(uuid.uuid4())
        
        # 3. Route Execution based on mutually-exclusive CLI flags
        if args.validate:
            logger.info(f"Validating connection and authentication to {args.source}...")
            is_healthy = await connector.check_health()
            if is_healthy:
                logger.info(f"[{args.source.upper()}] Connection and GraphQL Endpoint OK.")
                return 0
            else:
                logger.error(f"[{args.source.upper()}] Connection Failed.")
                return 1

        elif args.problem:
            logger.info(f"Ingesting specific problem: '{args.problem}'")
            await pipeline.run_single(connector, args.problem, correlation_id)
            
        elif args.all:
            logger.info(f"Initiating full stream ingestion for {args.source}...")
            logger.warning("This operation respects Rate Limits and may take up to 2 hours.")
            # For LeetCode, the stream_uri is implicitly the global problemset
            await pipeline.run_stream(connector, "all_problems", correlation_id)
            
        elif args.resume:
            logger.info(f"Resuming ingestion from the Dead Letter Queue...")
            logger.warning("DLQ Integration is pending Phase 11 networking logic.")
            # Placeholder for Dead Letter Queue replay logic
            
        else:
            logger.error("You must specify an operational flag (e.g., --problem, --all, --validate).")
            return 1
            
    except Exception as e:
        logger.error(f"CLI Execution critically failed: {e}")
        return 1
        
    finally:
        # Safely shut down aiohttp TCP sockets to prevent asyncio memory leak warnings
        if hasattr(connector, 'close'):
            await connector.close()
            
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """
    Entrypoint. 
    Usage: python -m src.cli.ingestion_cli leetcode --problem two-sum
    """
    parser = argparse.ArgumentParser(description="Knowledge Ingestion Manual CLI")
    
    parser.add_argument(
        "source", 
        type=str, 
        help="The target data source plugin (e.g., 'leetcode')"
    )
    
    # Prevent the user from passing conflicting commands simultaneously
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--problem", type=str, help="Ingest a specific problem slug (e.g., 'two-sum')")
    group.add_argument("--all", action="store_true", help="Ingest all available problems from the source via Pagination")
    group.add_argument("--resume", action="store_true", help="Resume failed ingestion attempts from the Dead Letter Queue")
    group.add_argument("--validate", action="store_true", help="Validate authentication and API network connectivity")
    
    args = parser.parse_args(argv)
    
    # Bridge the sync CLI arguments into the async execution graph
    return asyncio.run(_run_ingestion(args))


if __name__ == "__main__":
    sys.exit(main())
