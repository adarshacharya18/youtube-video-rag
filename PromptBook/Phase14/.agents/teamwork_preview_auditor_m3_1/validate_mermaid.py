import re

def check_mermaid_syntax(mmd_text, index):
    lines = mmd_text.strip().split('\n')
    header = lines[0].strip()
    errors = []
    
    print(f"Diagram {index} header: {header}")
    
    if header.startswith("flowchart") or header.startswith("graph"):
        # Check subgraphs, nodes, arrows
        open_subgraphs = 0
        for idx, l in enumerate(lines[1:], 2):
            line = l.strip()
            if not line or line.startswith("%%"):
                continue
            if line.startswith("subgraph"):
                open_subgraphs += 1
            elif line == "end":
                if open_subgraphs > 0:
                    open_subgraphs -= 1
                else:
                    errors.append(f"Line {idx}: 'end' without matching subgraph")
            # check brackets balancing
            if line.count('[') != line.count(']'):
                errors.append(f"Line {idx}: Unbalanced square brackets: {line}")
            if line.count('(') != line.count(')'):
                errors.append(f"Line {idx}: Unbalanced parentheses: {line}")
        if open_subgraphs != 0:
            errors.append(f"Unclosed subgraphs count: {open_subgraphs}")
            
    elif header.startswith("sequenceDiagram"):
        open_blocks = 0
        for idx, l in enumerate(lines[1:], 2):
            line = l.strip()
            if not line or line.startswith("%%"):
                continue
            if line.startswith("alt ") or line.startswith("par ") or line.startswith("opt ") or line.startswith("loop "):
                open_blocks += 1
            elif line.startswith("else ") or line.startswith("and "):
                if open_blocks == 0:
                    errors.append(f"Line {idx}: '{line}' outside block")
            elif line == "end":
                if open_blocks > 0:
                    open_blocks -= 1
                else:
                    errors.append(f"Line {idx}: 'end' without matching block")
        if open_blocks != 0:
            errors.append(f"Unclosed sequence blocks count: {open_blocks}")
            
    elif header.startswith("stateDiagram"):
        open_states = 0
        for idx, l in enumerate(lines[1:], 2):
            line = l.strip()
            if not line or line.startswith("%%"):
                continue
            if line.startswith("state ") and "{" in line:
                open_states += 1
            elif line == "}":
                if open_states > 0:
                    open_states -= 1
                else:
                    errors.append(f"Line {idx}: '}}' without matching state block")
        if open_states != 0:
            errors.append(f"Unclosed state blocks count: {open_states}")
    else:
        errors.append(f"Unknown diagram type header: {header}")
        
    return errors

target_file = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/01_Production_Architecture.md"

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

mermaid_blocks = re.findall(r'```mermaid\n(.*?)\n```', content, re.DOTALL)
print(f"Found {len(mermaid_blocks)} Mermaid blocks.")

all_clean = True
for i, block in enumerate(mermaid_blocks, 1):
    errs = check_mermaid_syntax(block, i)
    if errs:
        print(f"Diagram {i} HAS SYNTAX ERRORS:")
        for e in errs:
            print("  -", e)
        all_clean = False
    else:
        print(f"Diagram {i} Syntax Check: PASS")

if all_clean:
    print("\nALL MERMAID DIAGRAMS SYNTAX PASS")
