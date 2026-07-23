import re
import subprocess
import sys
import os

target_file = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/01_Production_Architecture.md"

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

mermaid_blocks = re.findall(r'```mermaid\n(.*?)\n```', content, re.DOTALL)
print(f"Found {len(mermaid_blocks)} Mermaid blocks.")

for i, block in enumerate(mermaid_blocks, 1):
    tmp_mmd = f"/tmp/diagram_{i}.mmd"
    tmp_svg = f"/tmp/diagram_{i}.svg"
    with open(tmp_mmd, "w", encoding="utf-8") as f:
        f.write(block)
    print(f"\n--- Testing Diagram {i} ---")
    print(block[:100] + "...")
    cmd = ["npx", "-p", "@mermaid-js/mermaid-cli", "mmdc", "-i", tmp_mmd, "-o", tmp_svg]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"Diagram {i}: PASS")
    else:
        print(f"Diagram {i}: FAIL")
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
