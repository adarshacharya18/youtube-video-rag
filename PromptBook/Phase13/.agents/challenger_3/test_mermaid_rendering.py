#!/usr/bin/env python3
"""
Empirical test to render all 11 Mermaid diagrams using mermaid-cli (mmdc).
"""
import sys
import subprocess
from pathlib import Path
from test_mermaid_diagrams import extract_mermaid_diagrams, TARGET_FILE

def main():
    diagrams = extract_mermaid_diagrams(TARGET_FILE)
    print(f"Testing rendering for all {len(diagrams)} Mermaid diagrams via mmdc...")
    
    results = []
    for diag in diagrams:
        idx = diag["index"]
        tmp_in = Path(f"/tmp/test_diagram_{idx}.mmd")
        tmp_out = Path(f"/tmp/test_diagram_{idx}.svg")
        tmp_in.write_text(diag["content"], encoding="utf-8")
        
        cmd = ["npx", "--no-install", "mmdc", "-i", str(tmp_in), "-o", str(tmp_out)]
        # If mmdc is not locally installed, try npx @mermaid-js/mermaid-cli
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            # Try npx @mermaid-js/mermaid-cli
            cmd2 = ["npx", "@mermaid-js/mermaid-cli", "mmdc", "-i", str(tmp_in), "-o", str(tmp_out)]
            res = subprocess.run(cmd2, capture_output=True, text=True)
            
        success = (res.returncode == 0) and tmp_out.exists()
        out_msg = "SUCCESS" if success else f"FAIL: {res.stderr[:200] if res.stderr else res.stdout[:200]}"
        print(f"Diagram {idx} (Lines {diag['start_line']}-{diag['end_line']}): {out_msg}")
        results.append((idx, success, res.stderr or res.stdout))
        
        if tmp_in.exists():
            tmp_in.unlink()
        if tmp_out.exists():
            tmp_out.unlink()
            
    passed_count = sum(1 for r in results if r[1])
    print(f"\nSummary: {passed_count}/{len(diagrams)} diagrams rendered successfully.")
    return 0 if passed_count == len(diagrams) else 1

if __name__ == "__main__":
    sys.exit(main())
