import re

TARGET_FILE = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md"

with open(TARGET_FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

content = "".join(lines)
blocks = re.split(r"(```python[\s\S]*?```)", content)

block_count = 0
for part in blocks:
    if part.startswith("```python"):
        block_count += 1
        print(f"=== PYTHON BLOCK {block_count} ===")
        print(part[:300]) # Print first 300 chars
        print("...\n")
