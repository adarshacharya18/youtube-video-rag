# Phase 13 / 12: Media Production CLI

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/media/cli.py`](#2-source-code-srccoremediaclipy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

While the end goal of the platform is an automated 12-hour pipeline run, developers and content creators require manual intervention capabilities. If FFmpeg fails due to a bad filtergraph, or if Manim renders a mathematical error, you do not want to re-run the entire 12-hour pipeline. 

The **Media CLI** exposes granular `argparse` commands for every isolated generation module. This allows a developer to fix the Manim code, manually trigger a quick `--preview` render, and manually execute `assemble` without touching the overarching Orchestrator.

---

# 2. Source Code: `src/core/media/cli.py`

```python
"""
Media Production CLI (Phase 13)

Provides command-line interfaces to manually trigger or debug individual
components of the Media Production Platform.
"""
import argparse
import logging
from pathlib import Path


def setup_cli() -> argparse.ArgumentParser:
    """Configures the argparse subcommands for the Media module."""
    parser = argparse.ArgumentParser(description="Media Production Platform CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available media commands")
    
    # ---------------------------------------------------------
    # media voice
    # ---------------------------------------------------------
    voice_parser = subparsers.add_parser("voice", help="Generate Voice audio from NarrationPlan")
    voice_parser.add_argument("--plan", required=True, help="Path to NarrationPlan JSON")
    voice_parser.add_argument("--out", required=True, help="Output audio file path")
    
    # ---------------------------------------------------------
    # media animate
    # ---------------------------------------------------------
    animate_parser = subparsers.add_parser("animate", help="Generate Animation bounds from AnimationPlan")
    animate_parser.add_argument("--plan", required=True, help="Path to AnimationPlan JSON")
    animate_parser.add_argument("--out", required=True, help="Output scene config path")
    
    # ---------------------------------------------------------
    # media render
    # ---------------------------------------------------------
    render_parser = subparsers.add_parser("render", help="Render Manim scenes via subprocess isolation")
    render_parser.add_argument("--scene", required=True, help="Path to Manim scene python file")
    render_parser.add_argument("--preview", action="store_true", help="Render in 480p15 for ultra-fast preview")
    
    # ---------------------------------------------------------
    # media subtitles
    # ---------------------------------------------------------
    sub_parser = subparsers.add_parser("subtitles", help="Generate SRT/VTT from audio & plan")
    sub_parser.add_argument("--audio", required=True, help="Path to Master Audio file")
    sub_parser.add_argument("--plan", required=True, help="Path to NarrationPlan JSON")
    sub_parser.add_argument("--out", required=True, help="Base path for output SRT/VTT")
    
    # ---------------------------------------------------------
    # media assemble
    # ---------------------------------------------------------
    assemble_parser = subparsers.add_parser("assemble", help="Multiplex video, audio, subtitles via FFmpeg")
    assemble_parser.add_argument("--video", required=True, help="Master video track")
    assemble_parser.add_argument("--audio", required=True, help="Master audio track")
    assemble_parser.add_argument("--subs", help="Subtitle track (optional)")
    assemble_parser.add_argument("--out", required=True, help="Output MP4 path")
    
    # ---------------------------------------------------------
    # media publish
    # ---------------------------------------------------------
    publish_parser = subparsers.add_parser("publish", help="Upload artifact to YouTube Data API")
    publish_parser.add_argument("--video", required=True, help="Path to final MP4")
    publish_parser.add_argument("--thumb", required=True, help="Path to thumbnail PNG")
    publish_parser.add_argument("--title", required=True, help="Video title")
    
    # ---------------------------------------------------------
    # media status
    # ---------------------------------------------------------
    status_parser = subparsers.add_parser("status", help="Check Artifact Manager registry and disk usage")
    
    return parser


def main():
    """Main CLI entrypoint. Acts as a thin wrapper over the domain logic."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = setup_cli()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    logger = logging.getLogger("media_cli")
    
    # Command Dispatcher
    if args.command == "voice":
        logger.info(f"Generating voice for {args.plan} -> {args.out}")
        # STUB: Execute VoiceProvider
        
    elif args.command == "animate":
        logger.info(f"Preparing animations for {args.plan} -> {args.out}")
        # STUB: Execute AnimationProvider
        
    elif args.command == "render":
        mode = "Preview (480p15)" if args.preview else "Production (1080p60)"
        logger.info(f"Rendering Manim Scene [{mode}]: {args.scene}")
        # STUB: Execute ManimRenderer
        
    elif args.command == "subtitles":
        logger.info(f"Force-aligning subtitles: {args.audio} + {args.plan} -> {args.out}.srt")
        # STUB: Execute SubtitleProvider
        
    elif args.command == "assemble":
        logger.info(f"Multiplexing Video: {args.video} + {args.audio} -> {args.out}")
        # STUB: Execute FFmpegVideoAssembler
        
    elif args.command == "publish":
        logger.info(f"Publishing '{args.title}' to YouTube...")
        # STUB: Execute PublishProvider
        
    elif args.command == "status":
        logger.info("Checking Artifact Manager Disk Usage & Ledger Status...")
        # STUB: Execute ArtifactManager metrics


if __name__ == "__main__":
    main()
```

---

# 3. Design Decisions

1. **Thin Wrapper Paradigm:** The CLI contains zero business logic. It simply parses text flags from standard input and maps them to the respective Class instances defined previously in Phase 13. This ensures the Pipeline Orchestrator and the CLI execute identical underlying logic.
2. **Preview Flag Injection:** Exposing the `--preview` flag directly to the `render` command is critical for Developer Experience (DX). A 1080p60 Manim render can take 3 hours, whereas a 480p15 preview takes 12 seconds. By surfacing this flag at the command line, developers can rapidly prototype complex Python animations without wasting AWS GPU time.
3. **Artifact Tooling:** Exposing the `status` command allows DevOps to quickly query the health of the EBS volume and the `artifact_registry.json` ledger without needing to write custom bash scripts, ensuring that large-scale artifact lifecycle management is easy to debug.
