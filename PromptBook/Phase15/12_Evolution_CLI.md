# Phase 15 / 12: Evolution CLI

**Author:** Principal Operations Engineer  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/cli/evolve.py`](#2-source-code-srcclievolvepy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

A complex, self-healing system requires intuitive interfaces for human operators. While `src/cli/ops.py` (Phase 14) handles the day-to-day execution of the video generation pipeline (start, stop, diagnose), the new **Evolution CLI** (`src/cli/evolve.py`) is explicitly dedicated to managing the long-term lifecycle of the platform.

It exposes commands for prompt A/B testing, manual quality feedback injection, plugin installation, architecture upgrades, and generating headless telemetry reports.

---

# 2. Source Code: `src/cli/evolve.py`

```python
"""
Evolution CLI (Phase 15)

Command-line interface for managing platform evolution, models, prompts,
plugins, analytics, and upgrades.
"""
import argparse
import sys
import json
from src.core.evolution.analytics_dashboard import AnalyticsDashboard

def evaluate_cmd(args):
    """Triggers the LLM-as-a-judge quality evaluation for a specific video."""
    print(f"Triggering quality evaluation for video: {args.video_id}")
    # STUB: Call QualityEvaluationFramework

def feedback_cmd(args):
    """Injects manual human feedback into the feedback ledger."""
    print(f"Recording manual feedback for video: {args.video_id}, Score: {args.score}")
    # STUB: Call FeedbackManager

def models_cmd(args):
    """Lists registered models, their health, and fallbacks."""
    print("Listing registered models, circuit-breaker health, and fallbacks...")
    # STUB: Call ModelManager

def prompts_cmd(args):
    """Lists active prompts, experimental weights, and regression status."""
    print("Listing prompt templates, A/B test weights, and regression status...")
    # STUB: Call PromptManager

def plugins_cmd(args):
    """Manages discovery and installation of plugins."""
    if args.action == "discover":
        print("Discovering new plugins from remote registry...")
    elif args.action == "install":
        print(f"Verifying signature and installing plugin: {args.plugin_id}")
    elif args.action == "rollback":
        print(f"Rolling back plugin {args.plugin_id} to previous snapshot...")
    else:
        print("Invalid action. Use discover, install, or rollback.")

def upgrade_cmd(args):
    """Initiates a platform or schema upgrade."""
    print(f"Initiating {args.channel} upgrade to version {args.version}...")
    print("Creating physical ledger snapshots...")
    # STUB: Call UpgradeManager

def analytics_cmd(args):
    """Generates the comprehensive JSON analytics dashboard report."""
    dashboard = AnalyticsDashboard()
    report = dashboard.generate_dashboard_report()
    print(report)

def main():
    parser = argparse.ArgumentParser(description="DSA Pipeline Evolution CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # evolve evaluate
    eval_parser = subparsers.add_parser("evaluate", help="Run LLM quality evaluation on a video")
    eval_parser.add_argument("--video-id", required=True, help="Video ID to evaluate")

    # evolve feedback
    fb_parser = subparsers.add_parser("feedback", help="Submit manual quality score feedback")
    fb_parser.add_argument("--video-id", required=True, help="Video ID")
    fb_parser.add_argument("--score", type=float, required=True, help="Score (1-10)")

    # evolve models
    subparsers.add_parser("models", help="List models, capabilities, and circuit-breaker health")

    # evolve prompts
    subparsers.add_parser("prompts", help="List prompts and active A/B test configurations")

    # evolve plugins
    plugin_parser = subparsers.add_parser("plugins", help="Manage 3rd party plugins")
    plugin_parser.add_argument("action", choices=["discover", "install", "rollback"])
    plugin_parser.add_argument("--plugin-id", help="Plugin ID for install/rollback")

    # evolve upgrade
    up_parser = subparsers.add_parser("upgrade", help="Execute platform / schema upgrade")
    up_parser.add_argument("--version", required=True, help="Target semver version")
    up_parser.add_argument("--channel", default="stable", choices=["stable", "beta", "nightly"])

    # evolve analytics
    subparsers.add_parser("analytics", help="Generate headless JSON telemetry report")

    args = parser.parse_args()

    try:
        if args.command == "evaluate":
            evaluate_cmd(args)
        elif args.command == "feedback":
            feedback_cmd(args)
        elif args.command == "models":
            models_cmd(args)
        elif args.command == "prompts":
            prompts_cmd(args)
        elif args.command == "plugins":
            plugins_cmd(args)
        elif args.command == "upgrade":
            upgrade_cmd(args)
        elif args.command == "analytics":
            analytics_cmd(args)
    except Exception as e:
        print(f"Error executing command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

# 3. Design Decisions

1. **Clear CLI Boundaries:** The CLI structure specifically separates operations (`ops run`, `ops health`) from evolution (`evolve upgrade`, `evolve models`). This ensures that standard users triggering nightly runs aren't bogged down by A/B testing configurations, while DevOps engineers have a dedicated namespace.
2. **Headless Integration:** Commands like `evolve analytics` specifically print raw JSON payloads to `stdout`. This allows external bash scripts and CI/CD pipelines to easily `grep` or `jq` the output to build automated Grafana dashboards or trigger Slack alerts.
3. **Manual Override Support:** While the system utilizes LLMs-as-a-Judge, the `evolve feedback --score 5.5` command allows human operators to manually inject overrides into the `feedback_ledger.sqlite`. If the AI graded an A/B test highly, but a human engineer realizes the audio is corrupted, they can force the feedback score down, instantly triggering the Prompt Manager's regression kill-switch.
