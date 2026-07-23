import re
import ast

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
    try:
        ast.parse(code)
        print(f"Python Block #{i} (Lines {start}-{end}): AST Parse SUCCESS")
    except SyntaxError as e:
        print(f"Python Block #{i} (Lines {start}-{end}): AST Parse SYNTAX ERROR: line {e.lineno} col {e.offset}: {e.msg}")
        print(f"  Snippet around line {e.lineno}:")
        code_lines = code.splitlines()
        err_line_idx = (e.lineno or 1) - 1
        for l_idx in range(max(0, err_line_idx - 2), min(len(code_lines), err_line_idx + 3)):
            print(f"  Line {start + 1 + l_idx}: {code_lines[l_idx]}")

