import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.ingestion.parser import DSAParser
from markdown_it import MarkdownIt

nested_lines = []
for depth in range(1, 16):
    indent = "  " * (depth - 1)
    nested_lines.append(f"{indent}* Level {depth} constraint line n <= {depth}")
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

parser = DSAParser()
i = 0
n = len(tokens)
current_section = "HEAD"
while i < n:
    tok = tokens[i]
    if tok.type == "heading_open":
        inline_tok = tokens[i+1] if i+1 < n and tokens[i+1].type == "inline" else None
        htext = inline_tok.content if inline_tok else ""
        print(f"Token {i}: heading_open {tok.tag} -> '{htext}'")
    elif tok.type == "fence":
        print(f"Token {i}: fence -> info={tok.info!r}")
    i += 1
