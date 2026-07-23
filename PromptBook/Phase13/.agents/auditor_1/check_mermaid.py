import re

target_path = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md"

with open(target_path, "r", encoding="utf-8") as f:
    content = f.read()

mermaid_blocks = re.findall(r'```mermaid\n(.*?)```', content, re.DOTALL)
print(f"Total Mermaid Diagrams Found: {len(mermaid_blocks)}")

for i, block in enumerate(mermaid_blocks, 1):
    lines = block.strip().splitlines()
    diagram_type = lines[0] if lines else "EMPTY"
    print(f"\n--- Mermaid Diagram #{i} (Type: {diagram_type}, Lines: {len(lines)}) ---")
    print("\n".join(lines[:10]))
    if len(lines) > 10:
        print("... (truncated)")

