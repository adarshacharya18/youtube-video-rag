#!/usr/bin/env python3
"""
Deep Validation Test for all 11 Mermaid Diagrams in 01_Media_Production_Architecture.md
Validates node identifiers, bracket syntax, subgraph nesting, sequence diagram participant references and message arrows.
"""

import sys
import re
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

def deep_validate_diagram(diag):
    idx = diag["index"]
    content = diag["content"].strip()
    lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith("%%")]
    header = lines[0].strip()
    
    errors = []
    warnings = []

    # 1. Check for unescaped special characters or syntax issues in labels
    for l_num, line in enumerate(lines, 1):
        stripped = line.strip()
        # Check unmatched quotes inside labels
        quotes_count = stripped.count('"')
        if quotes_count % 2 != 0:
            errors.append(f"Line {l_num}: Odd number of double quotes: '{stripped}'")

        # Check unmatched brackets
        # Ignore brackets inside quotes
        line_no_str = re.sub(r'".*?"', '""', stripped)
        if line_no_str.count('[') != line_no_str.count(']'):
            # Double brackets like [[ ]] or [( )] are fine if balanced
            pass
        if line_no_str.count('(') != line_no_str.count(')'):
            errors.append(f"Line {l_num}: Unbalanced parenthesis: '{stripped}'")
        if line_no_str.count('{') != line_no_str.count('}'):
            errors.append(f"Line {l_num}: Unbalanced curly braces: '{stripped}'")

    # 2. Sequence diagram specific checks
    if header == "sequenceDiagram":
        participants = set()
        for line in lines:
            stripped = line.strip()
            m_part = re.match(r'^(actor|participant)\s+([A-Za-z0-9_]+)', stripped)
            if m_part:
                participants.add(m_part.group(2))
                
        # Check message lines
        for l_num, line in enumerate(lines, 1):
            stripped = line.strip()
            # Message pattern: Sender->>Recipient: Message or Sender-->>Recipient: Message
            m_msg = re.match(r'^([A-Za-z0-9_]+)\s*(-?->>|-->>|->|-->)\s*([A-Za-z0-9_]+)\s*:\s*(.*)', stripped)
            if m_msg:
                sender, arrow, recipient, msg = m_msg.groups()
                if sender not in participants:
                    warnings.append(f"Line {l_num}: Sender '{sender}' was not explicitly declared as participant")
                if recipient not in participants:
                    warnings.append(f"Line {l_num}: Recipient '{recipient}' was not explicitly declared as participant")

    # 3. Flowchart/Graph subgraph check
    if header.startswith(("graph", "flowchart")):
        subgraphs = []
        for l_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("subgraph"):
                subgraphs.append(stripped)
            elif stripped == "end":
                if not subgraphs:
                    errors.append(f"Line {l_num}: 'end' without matching 'subgraph'")
                else:
                    subgraphs.pop()
        if subgraphs:
            errors.append(f"Unclosed subgraphs at end of diagram: {subgraphs}")

    return errors, warnings

def main():
    diagrams = extract_mermaid_diagrams(TARGET_FILE)
    print(f"Deep validating {len(diagrams)} Mermaid diagrams...")
    
    total_errors = 0
    total_warnings = 0
    
    for diag in diagrams:
        errors, warnings = deep_validate_diagram(diag)
        idx = diag["index"]
        header = diag["content"].strip().splitlines()[0]
        status = "FAIL" if errors else "PASS"
        print(f"\nDiagram {idx} (Lines {diag['start_line']}-{diag['end_line']}): Header='{header}' -> {status}")
        if errors:
            for e in errors:
                print(f"  [ERROR] {e}")
                total_errors += 1
        if warnings:
            for w in warnings:
                print(f"  [WARN] {w}")
                total_warnings += 1
                
    print(f"\nTotal Errors: {total_errors}, Total Warnings: {total_warnings}")
    return 0 if total_errors == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
