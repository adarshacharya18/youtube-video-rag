#!/usr/bin/env python3
"""
Test Harness 2: Event Taxonomy & Payload Dataclass Verification (V2)
Extracts Python code blocks containing event payload dataclasses from 01_Media_Production_Architecture.md,
executes them under Python 3.12, and checks event taxonomy consistency across the specification.
"""

import sys
import re
import ast
from dataclasses import is_dataclass, fields, dataclass
from typing import Generic, TypeVar, Any
from pathlib import Path

TARGET_FILE = Path("/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md")

T = TypeVar("T")

def test_event_dataclasses_execution(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    in_sec_1_6 = False
    py_blocks = []
    current_block = []
    in_py = False
    
    for idx, line in enumerate(lines, 1):
        if "### 1.6 Integration with Event Bus" in line:
            in_sec_1_6 = True
        elif "### 1.7 Integration with Persistence" in line:
            in_sec_1_6 = False
            
        if in_sec_1_6:
            if line.strip() == "```python":
                in_py = True
                current_block = []
                continue
            elif line.strip() == "```" and in_py:
                in_py = False
                py_blocks.append("".join(current_block))
                continue
            if in_py:
                current_block.append(line)

    print(f"Extracted {len(py_blocks)} Python code blocks from Section 1.6.")
    
    # Check block 1 (Envelope & Metadata)
    print("\n--- Testing Block 1 (Event Metadata & IntegrationEvent Envelope) ---")
    b1_code = py_blocks[0]
    
    # AST check
    try:
        ast.parse(b1_code)
        print("Block 1 AST parse: PASSED")
    except SyntaxError as e:
        print(f"Block 1 AST parse: FAILED ({e})")
        
    # Standalone Exec check (without pre-imported modules)
    ns1_raw = {}
    b1_raw_success = True
    try:
        exec(b1_code, ns1_raw)
        print("Block 1 Standalone Execution (without pre-imported modules): PASSED")
    except NameError as e:
        print(f"Block 1 Standalone Execution: FAILED due to missing imports in snippet: {e}")
        b1_raw_success = False

    # Exec with standard imports provided
    ns1 = {"dataclass": dataclass, "Generic": Generic, "TypeVar": TypeVar, "T": T, "Any": Any}
    try:
        exec(b1_code, ns1)
        print("Block 1 Execution with standard imports provided: PASSED")
    except Exception as e:
        print(f"Block 1 Execution: FAILED ({e})")

    # Check block 2 (Concrete Event Payload Schemas)
    print("\n--- Testing Block 2 (Concrete Event Payload Schemas) ---")
    b2_code = py_blocks[1]
    try:
        ast.parse(b2_code)
        print("Block 2 AST parse: PASSED")
    except SyntaxError as e:
        print(f"Block 2 AST parse: FAILED ({e})")

    ns2_raw = {}
    b2_raw_success = True
    try:
        exec(b2_code, ns2_raw)
        print("Block 2 Standalone Execution: PASSED")
    except Exception as e:
        print(f"Block 2 Standalone Execution: FAILED ({e})")
        b2_raw_success = False

    found_dataclasses = {}
    for name, obj in ns2_raw.items():
        if isinstance(obj, type) and is_dataclass(obj):
            found_dataclasses[name] = obj

    return b1_raw_success and b2_raw_success, found_dataclasses

def check_event_taxonomy_consistency(file_path: Path, found_dataclasses: dict):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find all media.* event references in document
    media_events = set(re.findall(r"\bmedia\.[a-z0-9_.]+\b", content))
    
    # Events in Event Topic Catalog Table (Section 1.6)
    sec_1_6_text = content.split("### 1.6 Integration with Event Bus")[1].split("### 1.7 Integration with Persistence")[0]
    table_events = set(re.findall(r"`(media\.[a-z0-9_.]+)`", sec_1_6_text))
    
    # Find events in Sequence Diagram (Section 1.2)
    seq_text = content.split("### 1.2 Comprehensive Mermaid End-to-End Sequence Diagram")[1].split("### 1.3 Integration with Educational Content Platform")[0]
    seq_events = set(re.findall(r"\[(media\.[a-z0-9_.]+)\]", seq_text))
    
    print("\n--- Event Taxonomy Consistency Analysis ---")
    print(f"Events in Section 1.6 Topic Catalog Table ({len(table_events)}):")
    for ev in sorted(table_events):
        print(f"  - {ev}")

    print(f"\nEvents published in Sequence Diagram ({len(seq_events)}):")
    for ev in sorted(seq_events):
        print(f"  - {ev}")

    missing_from_catalog = seq_events - table_events
    print(f"\nEvents published in Sequence Diagram BUT MISSING from Section 1.6 Catalog Table ({len(missing_from_catalog)}):")
    for ev in sorted(missing_from_catalog):
        print(f"  - [MISSING FROM TABLE] {ev}")

    # Check Dataclass mapping for each table event
    print("\n--- Event Payload Dataclass Field Mapping ---")
    expected_dataclasses = {
        "media.script.approved": "ScriptApprovedPayload",
        "media.voice.started": "VoiceSynthesisStartedPayload",
        "media.voice.generated": "AudioRenderedPayload",
        "media.animation.started": "AnimationRenderStartedPayload",
        "media.animation.rendered": "RenderCompletePayload",
        "media.subtitles.generated": "SubtitleCompletePayload",
        "media.video.assembled": "VideoAssembledPayload",
        "media.thumbnail.generated": "ThumbnailCompletePayload",
        "media.published": "YoutubePublishedPayload",
        "media.failed": "PipelineFailedPayload"
    }

    for event_name, dc_name in expected_dataclasses.items():
        if dc_name in found_dataclasses:
            cls = found_dataclasses[dc_name]
            f_names = [f.name for f in fields(cls)]
            has_slug = "slug" in f_names
            has_run_id = "run_id" in f_names
            has_corr = "correlation_id" in f_names
            print(f"Event '{event_name}' -> Dataclass '{dc_name}': OK (fields: {f_names})")
            if not (has_slug and has_run_id and has_corr):
                print(f"  [WARN] Missing common tracing fields (slug: {has_slug}, run_id: {has_run_id}, correlation_id: {has_corr})")
        else:
            print(f"Event '{event_name}' -> Dataclass '{dc_name}': MISSING DEFINITION!")

    return len(missing_from_catalog) == 0

def main():
    print(f"Testing Event Taxonomy & Dataclass Definitions in {TARGET_FILE}...")
    success, dc_dict = test_event_dataclasses_execution(TARGET_FILE)
    consistency_ok = check_event_taxonomy_consistency(TARGET_FILE, dc_dict)
    
    passed = success and consistency_ok
    print(f"\nFocus Area 2 Overall Verdict: {'PASS' if passed else 'FAIL (Issues Detected)'}")
    return 0 if passed else 1

if __name__ == "__main__":
    sys.exit(main())
