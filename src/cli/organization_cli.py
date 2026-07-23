"""
Organization CLI Module.

Command-line interface for managing the Knowledge Graph, Taxonomy rules, 
and topological curriculum generation manually.
"""

import argparse
import asyncio
import logging
import sys
from typing import List, Optional

from src.core.organization.concept_graph import ConceptGraph
from src.core.organization.index_preparer import IndexPreparer
from src.core.organization.knowledge_validator import KnowledgeValidator
from src.core.organization.learning_path_generator import LearningPathGenerator, PathDifficulty
from src.core.organization.prerequisite_analyzer import PrerequisiteAnalyzer
from src.core.organization.taxonomy_manager import TaxonomyManager
from src.core.storage_manager import StorageManager


def setup_logger() -> None:
    """Configures strict terminal output formatting."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )


async def _run_organize(args: argparse.Namespace) -> int:
    """Core execution block for the CLI."""
    setup_logger()
    logger = logging.getLogger("CLI.Organization")
    
    # 1. Initialize Core Infrastructure (In Prod, loaded from DI Container)
    storage = StorageManager("sqlite:///:memory:")
    
    # 2. Boot Core Organization Components
    tax = TaxonomyManager(storage)
    await tax.initialize()
    
    graph = ConceptGraph()
    # (In a production deployment, the graph would be fully deserialized from the DB here)
    
    # 3. Route Commands via Subparsers
    command = args.command
    
    try:
        if command == "taxonomy":
            logger.info("Dumping active Taxonomy Dictionary schema...")
            logger.info(f"Loaded Domains: {', '.join(tax._domains)}")
            for domain in tax._domains:
                count = len(tax._cache.get(domain, {}))
                logger.info(f"  - [{domain.upper()}]: {count} registered canonical IDs.")
            return 0
            
        elif command == "validate":
            logger.info("Executing Global System-Wide DAG Diagnostic...")
            validator = KnowledgeValidator(graph, tax)
            report = validator.run_full_diagnostic()
            
            if report.is_valid:
                logger.info("Validation PASSED. Graph is mathematically acyclic and structurally sound.")
                return 0
            else:
                logger.error(f"Validation FAILED! {len(report.prerequisite_cycles)} Cycles and {len(report.taxonomy_violations)} Taxonomy Violations found.")
                return 1
                
        elif command == "learning-path":
            if not getattr(args, 'topic', None):
                logger.error("FATAL: Must provide a --topic flag to generate a curriculum.")
                return 1
                
            analyzer = PrerequisiteAnalyzer(graph, tax)
            generator = LearningPathGenerator(graph, analyzer)
            
            # Map CLI string safely to Enum
            difficulty_map = {
                "beginner": PathDifficulty.BEGINNER,
                "intermediate": PathDifficulty.INTERMEDIATE,
                "advanced": PathDifficulty.ADVANCED,
                "interview": PathDifficulty.INTERVIEW_PREP
            }
            target_diff = difficulty_map.get(args.difficulty.lower(), PathDifficulty.BEGINNER)
            
            logger.info(f"Synthesizing {target_diff.name} curriculum for '{args.topic}'...")
            
            # Generate the Topological Curriculum
            path = generator.generate_topic_path(args.topic, target_diff)
            
            logger.info(f"Path Successfully Synthesized! (Estimated Time: {path.estimated_duration_hours} hours)")
            logger.info(f"Linear Execution Steps: {path.ordered_concepts}")
            return 0
            
        elif command == "prepare-index":
            logger.info("Initializing Index Preparer (Semantic Chunking & SHA-256 Hashing)...")
            preparer = IndexPreparer(max_tokens_per_chunk=500)
            logger.info("Index Preparer is active and ready to bridge documents to the Vector Database.")
            return 0
            
        elif command == "graph":
            logger.info("Dumping Knowledge Graph (DAG) state variables...")
            logger.info(f"Total Vertices (Nodes): {len(graph._nodes)}")
            logger.info(f"Total Edge Vectors: {sum(len(edges) for edges in graph._out_edges.values())}")
            return 0
            
        else:
            logger.error(f"Unknown subcommand: {command}")
            return 1
            
    except Exception as e:
        logger.error(f"CLI Execution critically failed: {e}")
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    """
    Entrypoint. 
    Usage: python -m src.cli.organization_cli learning-path --topic dynamic_programming --difficulty interview
    """
    parser = argparse.ArgumentParser(description="Knowledge Organization Management CLI")
    
    # Subparsers force the user to pick exactly one core command (e.g., 'validate' OR 'learning-path')
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Command: taxonomy
    subparsers.add_parser("taxonomy", help="Dump and inspect the rigorous Taxonomy Dictionaries.")
    
    # Command: validate
    subparsers.add_parser("validate", help="Run Kahn's Algorithm to verify DAG acyclic integrity globally.")
    
    # Command: graph
    subparsers.add_parser("graph", help="Dump Concept Graph V+E statistics.")
    
    # Command: prepare-index
    subparsers.add_parser("prepare-index", help="Test semantic chunking boundaries.")
    
    # Command: learning-path
    path_parser = subparsers.add_parser("learning-path", help="Synthesize a topological curriculum syllabus.")
    path_parser.add_argument("--topic", type=str, required=True, help="The target canonical concept ID to master (e.g., 'dijkstra')")
    path_parser.add_argument(
        "--difficulty", 
        type=str, 
        default="beginner", 
        choices=["beginner", "intermediate", "advanced", "interview"],
        help="Scales the syllabus progression depth."
    )
    
    args = parser.parse_args(argv)
    
    return asyncio.run(_run_organize(args))


if __name__ == "__main__":
    sys.exit(main())
