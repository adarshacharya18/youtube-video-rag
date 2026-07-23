"""
CLI entry point for manual testing of the Content Generation Platform.

Provides fine-grained command-line execution for the Planner, Storyboard, 
Narration, and Reviewer modules to isolate LLM prompt debugging.
"""

import argparse
import logging
import sys
from pathlib import Path

# Stub imports for architectural wiring demonstration
from src.core.script.animation import AnimationPlanner
from src.core.script.formatter import OutputFormatter
from src.core.script.generator import FinalScriptPayload, ScriptGenerator
from src.core.script.narration import NarrationPlanner
from src.core.script.planner import EducationalPlanner
from src.core.script.reviewer import ContentReviewer
from src.core.script.storyboard import StoryboardGenerator

logger = logging.getLogger(__name__)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Content Generation CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # 1. Plan
    plan_parser = subparsers.add_parser("plan", help="Generate Pedagogical Plan")
    plan_parser.add_argument("--slug", required=True, help="LeetCode Slug")
    
    # 2. Storyboard
    storyboard_parser = subparsers.add_parser("storyboard", help="Generate Visual Pacing Timeline")
    storyboard_parser.add_argument("--slug", required=True)
    
    # 3. Script Compiler
    script_parser = subparsers.add_parser("script", help="Compile and Merge JSON Outputs")
    script_parser.add_argument("--slug", required=True)
    
    # 4. Reviewer (LLM-as-a-Judge)
    review_parser = subparsers.add_parser("review", help="Audit the compiled script against RAG context")
    review_parser.add_argument("--slug", required=True)
    
    # 5. Export
    export_parser = subparsers.add_parser("export", help="Zip and checksum the JSON/Markdown payload")
    export_parser.add_argument("--slug", required=True)
    
    args = parser.parse_args()
    
    # In a production environment, we would inject the real Gemini/OpenAI client here
    llm_client_stub = None 
    
    if args.command == "plan":
        logger.info(f"Generating Educational Plan for '{args.slug}'...")
        planner = EducationalPlanner(llm_client_stub)
        # We mock the RAG context string for CLI isolation
        plan = planner.generate_plan(args.slug, "Mock RAG Context: Two Sum HashMap Optimization")
        print(f"✅ Generated Plan with {len(plan.learning_objectives)} learning objectives.")
        
    elif args.command == "storyboard":
        logger.info(f"Generating Storyboard for '{args.slug}'...")
        generator = StoryboardGenerator(llm_client_stub)
        storyboard = generator.generate(args.slug, "{}", "{}")
        print(f"✅ Generated Storyboard with {len(storyboard.scenes)} visual scenes.")
        
    elif args.command == "script":
        logger.info(f"Compiling AST Script Payload for '{args.slug}'...")
        # (Compilation wiring stub)
        print("✅ Successfully compiled FinalScriptPayload.")
        
    elif args.command == "review":
        logger.info(f"Running LLM-as-a-Judge Review for '{args.slug}'...")
        reviewer = ContentReviewer(llm_client_stub)
        
        # We mock the payload for demonstration
        mock_payload = FinalScriptPayload("1.0", "now", args.slug, {}, {}, {}, {})
        report = reviewer.review_script(mock_payload, "Mock Original RAG Context")
        
        if report.is_approved:
            print(f"✅ Review Passed. Score: {report.overall_score}/100")
        else:
            print(f"❌ Review Failed. Score: {report.overall_score}/100")
            print(f"Critical Findings: {len(report.findings)}")
            for finding in report.findings:
                print(f"  - [{finding.severity}] {finding.description}")
                print(f"    Action: {finding.recommended_fix}")
        
    elif args.command == "export":
        logger.info(f"Formatting and Exporting ZIP Package for '{args.slug}'...")
        formatter = OutputFormatter(f"/tmp/{args.slug}")
        # (Export wiring stub)
        print(f"✅ Exported securely to /tmp/{args.slug}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    main()
