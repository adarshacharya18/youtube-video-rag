import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.ingestion.parser import DSAParser

md_indented_hijack = """# 1. Indented Hijack Problem

Difficulty: Easy
Tags: Array

## Description
Some description text.

    * item 1
        * item 2
            * item 3
                * item 4

## Solution
```python
def solve():
    return 42
```
"""

parser = DSAParser()
try:
    prob = parser.parse(md_indented_hijack)
    print("Parsed successfully!")
    print("Code:", prob.accepted_code)
except Exception as e:
    print("Exception:", type(e), e)
