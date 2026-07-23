import re

TARGET_FILE = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md"

with open(TARGET_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

blocks = re.findall(r"```python([\s\S]*?)```", content)

print("=== BLOCK 4 ===")
print(blocks[3])

print("=== BLOCK 6 ===")
print(blocks[5])

print("=== BLOCK 7 ===")
print(blocks[6])
