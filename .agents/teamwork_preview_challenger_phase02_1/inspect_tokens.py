import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.ingestion.parser import DSAParser
from markdown_it import MarkdownIt

nested_list_lines = []
for depth in range(1, 101):
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

## Code
```python
def deep(): pass
```
"""

md = MarkdownIt("commonmark", {"html": True})
tokens = md.parse(md_deep_list)
print(f"Total tokens: {len(tokens)}")

parser = DSAParser()
i = 0
n = len(tokens)
current_section = "HEAD"
while i < n:
    token = tokens[i]
    if token.type == "heading_open":
        inline_tok = tokens[i+1] if i+1 < n and tokens[i+1].type == "inline" else None
        htext = inline_tok.content if inline_tok else ""
        print(f"Token {i}: heading_open {token.tag} -> {htext}")
    elif token.type == "fence":
        print(f"Token {i}: fence -> section={current_section}")
    elif token.type == "list_item_open":
        # Check index advancement
        pass
    i += 1
