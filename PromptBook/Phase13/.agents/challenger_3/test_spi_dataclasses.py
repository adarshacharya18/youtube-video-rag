#!/usr/bin/env python3
"""
Test Harness 3: SPI Request Dataclasses Correlation/Trace ID Verification
Extracts Python code from Section 3.1 of 01_Media_Production_Architecture.md,
executes it under Python 3.12, and verifies correlation_id and trace_id fields across all 5 SPI request dataclasses.
"""

import sys
import re
import ast
from dataclasses import is_dataclass, fields
from pathlib import Path

TARGET_FILE = Path("/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md")

def extract_sec_3_1_python(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    in_sec_3_1 = False
    py_lines = []
    in_py = False
    
    for idx, line in enumerate(lines, 1):
        if "### 3.1 Plugin SPI Definitions" in line:
            in_sec_3_1 = True
        elif "### 3.2 Configuration-Driven Factory Pattern" in line:
            in_sec_3_1 = False
            
        if in_sec_3_1:
            if line.strip() == "```python":
                in_py = True
                continue
            elif line.strip() == "```" and in_py:
                in_py = False
                continue
            if in_py:
                py_lines.append(line)
                
    return "".join(py_lines)

def test_spi_execution_and_fields(py_code: str):
    print("--- AST Parsing of Section 3.1 SPI Definitions ---")
    try:
        ast.parse(py_code)
        print("AST Parsing: PASSED")
    except SyntaxError as e:
        print(f"AST Parsing: FAILED ({e})")
        return False, {}, f"SyntaxError: {e}"

    print("\n--- Standalone Execution of Section 3.1 SPI Definitions ---")
    namespace = {}
    try:
        exec(py_code, namespace)
        print("Standalone Execution under Python 3.12: PASSED")
    except Exception as e:
        print(f"Standalone Execution: FAILED ({e})")
        return False, {}, f"RuntimeError: {e}"

    # Target SPI Request dataclasses to check
    request_dataclasses = [
        "VoiceRequest",
        "AnimationRequest",
        "SubtitleRequest",
        "ThumbnailRequest",
        "PublishRequest"
    ]

    print("\n--- Empirical Inspection of SPI Request Dataclasses ---")
    results = {}
    all_passed = True

    for req_name in request_dataclasses:
        if req_name not in namespace:
            print(f"[FAIL] Dataclass '{req_name}' NOT FOUND in Section 3.1 namespace!")
            all_passed = False
            continue

        cls = namespace[req_name]
        if not is_dataclass(cls):
            print(f"[FAIL] '{req_name}' is not a valid dataclass!")
            all_passed = False
            continue

        field_dict = {f.name: f for f in fields(cls)}
        has_corr = "correlation_id" in field_dict
        has_trace = "trace_id" in field_dict

        corr_type = field_dict["correlation_id"].type if has_corr else None
        trace_type = field_dict["trace_id"].type if has_trace else None

        corr_default = field_dict["correlation_id"].default if has_corr else None
        trace_default = field_dict["trace_id"].default if has_trace else None

        status = "PASS" if (has_corr and has_trace) else "FAIL"
        if not (has_corr and has_trace):
            all_passed = False

        print(f"[{status}] {req_name}:")
        print(f"       correlation_id present: {has_corr} (type: {corr_type}, default: {repr(corr_default)})")
        print(f"       trace_id present:       {has_trace} (type: {trace_type}, default: {repr(trace_default)})")

        results[req_name] = {
            "has_correlation_id": has_corr,
            "has_trace_id": has_trace,
            "corr_type": corr_type,
            "trace_type": trace_type,
            "corr_default": corr_default,
            "trace_default": trace_default
        }

    # Test Instantiation test for each Request dataclass
    print("\n--- Testing Instantiation of SPI Request Dataclasses ---")
    try:
        vr = namespace["VoiceRequest"](slug="test", section_id="s1", narration_text="hello", correlation_id="c1", trace_id="t1")
        ar = namespace["AnimationRequest"](slug="test", section_id="s1", scene_type="array", visual_parameters={}, target_duration_seconds=5.0, correlation_id="c1", trace_id="t1")
        sr = namespace["SubtitleRequest"](slug="test", audio_file_path=Path("/tmp/a.wav"), narration_text="hello", word_timings=[], output_formats=[namespace["SubtitleFormat"].SRT], correlation_id="c1", trace_id="t1")
        tr = namespace["ThumbnailRequest"](slug="test", title_text="title", subtitle_text="sub", correlation_id="c1", trace_id="t1")
        pr = namespace["PublishRequest"](slug="test", video_file_path=Path("/tmp/v.mp4"), thumbnail_file_path=Path("/tmp/t.png"), subtitle_file_path=None, title="title", description="desc", tags=["tag"], correlation_id="c1", trace_id="t1")
        print("All 5 SPI Request Dataclasses instantiated successfully with correlation_id and trace_id!")
    except Exception as e:
        print(f"Instantiation failed: {e}")
        all_passed = False

    return all_passed, results, None

def main():
    print(f"Testing Section 3.1 SPI Dataclasses in {TARGET_FILE}...")
    py_code = extract_sec_3_1_python(TARGET_FILE)
    passed, results, err = test_spi_execution_and_fields(py_code)

    print(f"\nFocus Area 3 Overall Verdict: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1

if __name__ == "__main__":
    sys.exit(main())
