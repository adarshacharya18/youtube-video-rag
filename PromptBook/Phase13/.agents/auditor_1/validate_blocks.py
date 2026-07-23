import re
import yaml
import json

target_path = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md"

with open(target_path, "r", encoding="utf-8") as f:
    content = f.read()

code_blocks = re.findall(r'```(\w*)\n(.*?)```', content, re.DOTALL)

yaml_success = 0
yaml_fail = 0
json_success = 0
json_fail = 0

for lang, code in code_blocks:
    lang = lang.strip().lower()
    if lang in ("yaml", "yml"):
        try:
            yaml.safe_load(code)
            yaml_success += 1
        except Exception as e:
            yaml_fail += 1
            print(f"YAML Parse Error: {e}")
    elif lang in ("json",):
        try:
            json.loads(code)
            json_success += 1
        except Exception as e:
            json_fail += 1
            print(f"JSON Parse Error: {e}")

print(f"YAML Blocks Parsed Successfully: {yaml_success}/{yaml_success + yaml_fail}")
print(f"JSON Blocks Parsed Successfully: {json_success}/{json_success + json_fail}")

