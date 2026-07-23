import re
import sys

def extract_mermaid_blocks(doc_path):
    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    blocks = re.findall(r"```mermaid\n(.*?)```", content, re.DOTALL)
    return blocks

def validate_flowchart(code):
    errors = []
    lines = [line.strip() for line in code.strip().split("\n") if line.strip() and not line.strip().startswith("%%")]
    header = lines[0]
    if not (header.startswith("flowchart") or header.startswith("graph")):
        errors.append(f"Invalid flowchart header: {header}")
    
    subgraph_stack = []
    for line_idx, line in enumerate(lines[1:], 2):
        if line.startswith("subgraph"):
            subgraph_stack.append(line)
        elif line == "end":
            if not subgraph_stack:
                errors.append(f"Line {line_idx}: 'end' without matching 'subgraph'")
            else:
                subgraph_stack.pop()
        # Check node shapes, brackets, quotes balance
        for bracket_pair in [("[", "]"), ("(", ")"), ("{", "}"), ("([", "])"), ("[(", ")]")]:
            open_count = line.count(bracket_pair[0])
            close_count = line.count(bracket_pair[1])
            if open_count != close_count:
                errors.append(f"Line {line_idx}: Mismatched brackets '{bracket_pair[0]}' and '{bracket_pair[1]}' in '{line}'")
    
    if subgraph_stack:
        errors.append(f"Unclosed subgraphs remaining: {len(subgraph_stack)}")
        
    return errors

def validate_sequence_diagram(code):
    errors = []
    lines = [line.strip() for line in code.strip().split("\n") if line.strip() and not line.strip().startswith("%%")]
    header = lines[0]
    if header != "sequenceDiagram":
        errors.append(f"Invalid sequenceDiagram header: {header}")
    
    block_stack = []
    for line_idx, line in enumerate(lines[1:], 2):
        if line.startswith("loop") or line.startswith("alt") or line.startswith("opt"):
            block_stack.append(line.split()[0])
        elif line.startswith("else"):
            if not block_stack or block_stack[-1] != "alt":
                errors.append(f"Line {line_idx}: 'else' outside of 'alt' block")
        elif line == "end":
            if not block_stack:
                errors.append(f"Line {line_idx}: 'end' without matching loop/alt/opt block")
            else:
                block_stack.pop()
                
    if block_stack:
        errors.append(f"Unclosed control blocks remaining: {block_stack}")
        
    return errors

def validate_state_diagram(code):
    errors = []
    lines = [line.strip() for line in code.strip().split("\n") if line.strip() and not line.strip().startswith("%%")]
    header = lines[0]
    if not (header.startswith("stateDiagram") or header.startswith("stateDiagram-v2")):
        errors.append(f"Invalid stateDiagram header: {header}")
        
    state_stack = []
    for line_idx, line in enumerate(lines[1:], 2):
        if line.startswith("state ") and "{" in line:
            state_stack.append(line)
        elif line == "}":
            if not state_stack:
                errors.append(f"Line {line_idx}: '}}' without matching composite state declaration")
            else:
                state_stack.pop()
                
    if state_stack:
        errors.append(f"Unclosed composite state blocks remaining: {len(state_stack)}")
        
    return errors

def test_all_mermaid():
    doc_path = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase15/01_Platform_Evolution_Architecture.md"
    blocks = extract_mermaid_blocks(doc_path)
    print(f"Found {len(blocks)} Mermaid code blocks.\n")

    for i, code in enumerate(blocks, 1):
        lines = [line.strip() for line in code.strip().split("\n") if line.strip()]
        header = lines[0]
        print(f"--- MERMAID BLOCK {i} ({header.split()[0]}) ---")
        
        if header.startswith("flowchart") or header.startswith("graph"):
            errs = validate_flowchart(code)
        elif header.startswith("sequenceDiagram"):
            errs = validate_sequence_diagram(code)
        elif header.startswith("stateDiagram"):
            errs = validate_state_diagram(code)
        else:
            errs = [f"Unknown diagram type: {header}"]

        if not errs:
            print(f"PASS: Block {i} syntax is valid.")
        else:
            print(f"FAIL: Block {i} has syntax errors:")
            for e in errs:
                print(f"  - {e}")
        print()

if __name__ == "__main__":
    test_all_mermaid()
