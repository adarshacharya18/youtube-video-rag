import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from markdown_it import MarkdownIt

nested_lines = []
for depth in range(1, 6):
    indent = "  " * (depth - 1)
    nested_lines.append(f"{indent}* Level {depth} constraint line")
nested_md = "\n".join(nested_lines)

md_nested_list = f"""# 101. Nested List Problem

Difficulty: Easy
Tags: Recursion

## Description
Nested list problem.

## Constraints
{nested_md}

## Solution
```python
def nested(): pass
```
"""

md = MarkdownIt("commonmark", {"html": True})
tokens = md.parse(md_nested_list)
print("Tokens with 5 levels:")
for i, tok in enumerate(tokens):
    if tok.type in ("heading_open", "fence"):
        print(f"  Token {i}: {tok.type} tag={tok.tag}")
