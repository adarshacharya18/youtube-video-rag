import re

target_path = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md"

with open(target_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

in_py = False
py_blocks = []
current_block = []
start_line = 0

for idx, line in enumerate(lines, 1):
    if line.strip().startswith("```python"):
        in_py = True
        start_line = idx
        current_block = []
    elif line.strip() == "```" and in_py:
        in_py = False
        py_blocks.append((start_line, idx, "".join(current_block)))
    elif in_py:
        current_block.append(line)

for i, (start, end, code) in enumerate(py_blocks, 1):
    print(f"\n==================================================")
    print(f"PYTHON BLOCK #{i} (Lines {start}-{end}):")
    print(f"==================================================")
    print(code)

