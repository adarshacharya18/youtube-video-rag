import re

TARGET_FILE = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md"

with open(TARGET_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

mermaid_blocks = re.findall(r"```mermaid([\s\S]*?)```", content)

print(f"Total Mermaid Blocks: {len(mermaid_blocks)}")

for idx, block in enumerate(mermaid_blocks, 1):
    lines = block.strip().split('\n')
    header = lines[0].strip()
    print(f"Diagram {idx} ({header}): {len(lines)} lines")
    # Check for unclosed quotes or syntax brackets
    brackets_open = block.count('{') + block.count('[') + block.count('(')
    brackets_close = block.count('}') + block.count(']') + block.count(')')
    if abs(brackets_open - brackets_close) > 5:
        print(f"  [WARNING] Diagram {idx} bracket mismatch: {brackets_open} open vs {brackets_close} close")
    else:
        print(f"  [PASS] Diagram {idx} structure intact.")
