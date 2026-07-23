import re

TARGET_FILE = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md"

with open(TARGET_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

blocks = re.findall(r"```python([\s\S]*?)```", content)
print("=== BLOCK 11 ===")
print(blocks[10])
