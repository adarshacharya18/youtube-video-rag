import sys
from pathlib import Path
from markdown_it import MarkdownIt

nested_list_lines = []
for depth in range(1, 20): # let's try 20 levels with standard 2 spaces vs 4 spaces
    indent = "  " * (depth - 1)
    nested_list_lines.append(f"{indent}* Level {depth} constraint line n <= 10^{depth}")
nested_md = "\n".join(nested_list_lines)

md_deep_list = f"""# 101. Deeply Nested List Problem

Difficulty: Easy
Tags: Recursion

## Description
Deep nested list problem.

## Constraints
{nested_md}

## Solution
```python
def deep(): pass
```
"""

md = MarkdownIt("commonmark", {"html": True})
tokens = md.parse(md_deep_list)
print(f"Total tokens for 20 levels: {len(tokens)}")

for i, tok in enumerate(tokens):
    if tok.type in ("heading_open", "fence", "code_block"):
        print(f"Token {i}: {tok.type} {tok.tag} info={tok.info!r} content={tok.content!r}")
