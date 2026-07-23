import re

TARGET_FILE = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md"

with open(TARGET_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

blocks = re.findall(r"```python([\s\S]*?)```", content)
block2 = blocks[1]

classes = re.findall(r"class\s+([A-Za-z0-9_]+)", block2)
print("Dataclasses found in Block 2:")
for c in classes:
    print(f" - {c}")
