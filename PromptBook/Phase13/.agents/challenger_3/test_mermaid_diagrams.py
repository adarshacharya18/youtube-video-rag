#!/usr/bin/env python3
"""
Test Harness 1: Mermaid Diagram Syntax & Structure Verification (V2)
Extracts all ```mermaid blocks from 01_Media_Production_Architecture.md and validates syntax.
"""

import sys
import re
import subprocess
from pathlib import Path

TARGET_FILE = Path("/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md")

def extract_mermaid_diagrams(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    diagrams = []
    in_mermaid = False
    current_lines = []
    start_line = 0
    
    for idx, line in enumerate(lines, 1):
        if line.strip() == "```mermaid":
            in_mermaid = True
            start_line = idx + 1
            current_lines = []
        elif line.strip() == "```" and in_mermaid:
            in_mermaid = False
            diagram_content = "".join(current_lines)
            diagrams.append({
                "index": len(diagrams) + 1,
                "start_line": start_line,
                "end_line": idx - 1,
                "content": diagram_content
            })
        elif in_mermaid:
            current_lines.append(line)
            
    return diagrams

def validate_mermaid_syntax(diagram):
    content = diagram["content"].strip()
    lines = [l.rstrip() for l in content.splitlines() if l.strip() and not l.strip().startswith("%%")]
    
    errors = []
    warnings = []
    
    if not lines:
        errors.append("Empty mermaid diagram")
        return errors, warnings
        
    header = lines[0].strip()
    valid_headers = ("graph ", "sequenceDiagram", "flowchart ", "classDiagram", "stateDiagram", "erDiagram", "gantt", "pie", "gitGraph")
    if not any(header.startswith(vh) for vh in valid_headers):
        errors.append(f"Invalid or unrecognized Mermaid header: '{header}'")
        
    # Subgraph balance check for graph/flowchart
    if header.startswith(("graph", "flowchart")):
        subgraph_count = sum(1 for l in lines if l.strip().startswith("subgraph"))
        end_count = sum(1 for l in lines if l.strip() == "end")
        if subgraph_count != end_count:
            errors.append(f"Mismatched subgraph ({subgraph_count}) and end ({end_count}) statements")

    # Sequence diagram check for loops/alt/par/opt/rect
    if header == "sequenceDiagram":
        # Block starters: loop, alt, par, opt, rect (excluding 'else' and 'and' which are internal section dividers)
        block_starters = 0
        block_ends = 0
        for l in lines:
            stripped = l.strip()
            # Must match word boundaries: loop ..., alt ..., par ..., opt ..., rect ...
            if re.match(r'^(loop|alt|par|opt|rect)\b', stripped):
                block_starters += 1
            elif stripped == "end":
                block_ends += 1
                
        if block_starters != block_ends:
            errors.append(f"Mismatched sequence block starters ({block_starters}) and end ({block_ends}) statements")

    return errors, warnings

def test_mmdc_cli(diagrams):
    cli_results = []
    for diag in diagrams:
        idx = diag["index"]
        tmp_file = Path(f"/tmp/diag_{idx}.mmd")
        tmp_out = Path(f"/tmp/diag_{idx}.svg")
        tmp_file.write_text(diag["content"], encoding="utf-8")
        
        # Use node inline script or mmdc if available
        # Check if node has @mermaid-js/mermaid-cli or if we can run via npx
        cmd = ["npx", "-p", "@mermaid-js/mermaid-cli", "mmdc", "-i", str(tmp_file), "-o", str(tmp_out)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if res.returncode == 0:
                cli_results.append((idx, True, "Valid"))
            else:
                cli_results.append((idx, False, res.stderr or res.stdout))
        except Exception as e:
            cli_results.append((idx, None, f"CLI execution failed: {e}"))
            
        if tmp_file.exists():
            tmp_file.unlink()
        if tmp_out.exists():
            tmp_out.unlink()
            
    return cli_results

def main():
    print(f"Extracting Mermaid diagrams from {TARGET_FILE}...")
    diagrams = extract_mermaid_diagrams(TARGET_FILE)
    print(f"Found total {len(diagrams)} Mermaid diagrams.")
    
    all_passed = True
    report = []
    
    for diag in diagrams:
        idx = diag["index"]
        start_line = diag["start_line"]
        end_line = diag["end_line"]
        header = diag["content"].strip().splitlines()[0]
        
        errors, warnings = validate_mermaid_syntax(diag)
        status = "FAIL" if errors else "PASS"
        if errors:
            all_passed = False
            
        print(f"Diagram {idx} (Lines {start_line}-{end_line}): Header='{header}' -> {status}")
        if errors:
            for err in errors:
                print(f"   [ERROR] {err}")
        if warnings:
            for warn in warnings:
                print(f"   [WARN] {warn}")
                
        report.append({
            "index": idx,
            "start_line": start_line,
            "end_line": end_line,
            "header": header,
            "status": status,
            "errors": errors,
            "warnings": warnings
        })

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
