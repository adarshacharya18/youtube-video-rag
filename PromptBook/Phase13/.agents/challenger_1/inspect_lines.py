#!/usr/bin/env python3
import re
from pathlib import Path

DOC_PATH = Path("/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md")

with open(DOC_PATH, "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    if "async def get_voice_provider(" in line:
        print(f"Line {i}: {line.strip()}")
