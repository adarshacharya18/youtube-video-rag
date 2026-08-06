import os
import re

scenes_dir = "src/animation/scenes/"

for file_name in os.listdir(scenes_dir):
    if not file_name.endswith("_scene.py") or file_name == "base_scene.py":
        continue
    
    file_path = os.path.join(scenes_dir, file_name)
    with open(file_path, "r") as f:
        content = f.read()

    # Find the time_tracker block
    # It usually starts with time_tracker = ValueTracker(0) and ends with self.wait(wait_time)
    
    pattern = re.compile(r"(\s*)time_tracker = ValueTracker\(0\).*?self\.wait\(wait_time\)", re.DOTALL)
    
    def replacer(match):
        indent = match.group(1)
        # Simply replace with a standard wait so it doesn't freeze the renderer with broken dt updaters.
        return f"{indent}# Deterministic wait replacing broken dt updater\n{indent}self.wait(wait_time)"
        
    new_content, count = pattern.subn(replacer, content)
    
    if count > 0:
        with open(file_path, "w") as f:
            f.write(new_content)
        print(f"Fixed {file_name}")

