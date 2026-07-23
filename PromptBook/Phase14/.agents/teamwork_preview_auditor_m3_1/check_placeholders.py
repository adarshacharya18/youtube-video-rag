import re

target_file = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/01_Production_Architecture.md"

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.split('\n')

patterns = [
    r'\bTODO\b',
    r'\bFIXME\b',
    r'\bTBD\b',
    r'\bXXX\b',
    r'\bplaceholder\b',
    r'^\s*$', # empty lines
]

findings = []

for idx, line in enumerate(lines, 1):
    for pat in patterns[:5]:
        if re.search(pat, line, re.IGNORECASE):
            findings.append((idx, pat, line))

print(f"Total lines: {len(lines)}")
print(f"Placeholder findings count: {len(findings)}")

for f in findings:
    print(f"Line {f[0]}: match '{f[1]}' -> {f[2]}")

