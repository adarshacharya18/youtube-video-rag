import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.ingestion.parser import DSAParser

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

parser = DSAParser()
try:
    prob = parser.parse(md_deep_list)
    print("Parsed successfully!")
    print("Constraints count:", len(prob.constraints))
    print("Constraints first 3:", prob.constraints[:3])
    print("Code:", prob.accepted_code)
except Exception as e:
    print("Exception:", type(e), e)
