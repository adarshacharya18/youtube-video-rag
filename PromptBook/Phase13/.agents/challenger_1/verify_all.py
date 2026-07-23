#!/usr/bin/env python3
import ast
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
import yaml

DOC_PATH = Path("/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md")

def extract_code_blocks(doc_text):
    pattern = r"```([a-zA-Z0-9_\-\+]*)\n(.*?)```"
    matches = re.findall(pattern, doc_text, re.DOTALL)
    blocks = []
    for lang, content in matches:
        blocks.append((lang.strip(), content.strip()))
    return blocks

def test_mermaid_syntax():
    print("=== 1. MERMAID DIAGRAM EXTRACTION & VALIDATION ===")
    with open(DOC_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    mermaid_blocks = re.findall(r"```mermaid\n(.*?)```", text, re.DOTALL)
    print(f"Found {len(mermaid_blocks)} Mermaid blocks.")

    results = []
    for idx, code in enumerate(mermaid_blocks, 1):
        tmp_file = Path(f"/tmp/diagram_{idx}.mmd")
        tmp_out = Path(f"/tmp/diagram_{idx}.svg")
        tmp_file.write_text(code, encoding="utf-8")

        # Attempt validation using mmdc via npx
        cmd = ["npx", "-p", "@mermaid-js/mermaid-cli", "mmdc", "-i", str(tmp_file), "-o", str(tmp_out)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        valid = (res.returncode == 0)
        err_msg = res.stderr if not valid else ""
        results.append({
            "diagram_index": idx,
            "header": code.splitlines()[0] if code.splitlines() else "",
            "valid": valid,
            "error": err_msg
        })
        print(f"Diagram {idx} ({code.splitlines()[0]}): {'PASS' if valid else 'FAIL'}")
        if not valid:
            print(f"   Error: {err_msg[:300]}")

    return results, mermaid_blocks

def test_python_snippets():
    print("\n=== 2. PYTHON CODE SNIPPETS AST SYNTAX CHECK ===")
    with open(DOC_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    blocks = extract_code_blocks(text)
    py_blocks = [(idx, b[1]) for idx, b in enumerate(blocks) if b[0] == "python"]
    print(f"Found {len(py_blocks)} Python code blocks.")

    errors = []
    for idx, code in py_blocks:
        try:
            ast.parse(code)
            print(f"Python block {idx}: PASS")
        except SyntaxError as e:
            print(f"Python block {idx}: FAIL -> SyntaxError: {e}")
            errors.append({"block_idx": idx, "error": str(e), "code": code[:150]})
    return errors

def test_yaml_snippets():
    print("\n=== 3. YAML CODE SNIPPETS SYNTAX CHECK ===")
    with open(DOC_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    blocks = extract_code_blocks(text)
    yaml_blocks = [(idx, b[1]) for idx, b in enumerate(blocks) if b[0] in ("yaml", "yml")]
    print(f"Found {len(yaml_blocks)} YAML code blocks.")

    errors = []
    for idx, code in yaml_blocks:
        try:
            yaml.safe_load(code)
            print(f"YAML block {idx}: PASS")
        except yaml.YAMLError as e:
            print(f"YAML block {idx}: FAIL -> YAMLError: {e}")
            errors.append({"block_idx": idx, "error": str(e)})
    return errors

def test_sql_schema():
    print("\n=== 4. SQL SCHEMA SYNTAX & EXECUTION CHECK ===")
    with open(DOC_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    blocks = extract_code_blocks(text)
    sql_blocks = [b[1] for b in blocks if b[0] == "sql"]
    print(f"Found {len(sql_blocks)} SQL code blocks.")

    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    errors = []
    for idx, sql_code in enumerate(sql_blocks, 1):
        try:
            # SQLite does not support 'TIMESTAMP WITH TIME ZONE' or 'DOUBLE PRECISION' natively,
            # but standard SQLite ignores unknown column types or converts them.
            cursor.executescript(sql_code)
            print(f"SQL block {idx}: PASS")
        except sqlite3.Error as e:
            print(f"SQL block {idx}: FAIL -> SQLite Error: {e}")
            errors.append({"block_idx": idx, "error": str(e)})
    return errors

def analyze_event_topics_and_schemas(doc_text):
    print("\n=== 5. EVENT BUS TOPIC & SCHEMA ANALYSIS ===")
    # Extract topics from table
    topic_table_matches = re.findall(r"\| `([a-z0-9_\.]+)` \|", doc_text)
    print(f"Topics found in table (Section 1.6): {set(topic_table_matches)}")

    # Extract topics/events from Mermaid 1.1
    m1_events = re.findall(r'Emits ([a-z0-9_\.]+)', doc_text)
    print(f"Events emitted in Mermaid 1.1: {set(m1_events)}")

    # Extract topics/events from Sequence 1.2
    seq_events = re.findall(r'Publish \[([a-z0-9_\.]+)\]', doc_text)
    print(f"Events published in Sequence 1.2: {set(seq_events)}")

    # Search for Payload dataclass definitions (e.g. ScriptApprovedPayload, AudioRenderedPayload, etc.)
    payload_classes = [
        "ScriptApprovedPayload", "VoiceSynthesisStartedPayload", "AudioRenderedPayload",
        "AnimationRenderStartedPayload", "RenderCompletePayload", "SubtitleCompletePayload",
        "VideoAssembledPayload", "ThumbnailCompletePayload", "YoutubePublishedPayload",
        "PipelineFailedPayload"
    ]
    missing_dataclasses = []
    for cls_name in payload_classes:
        if f"class {cls_name}" not in doc_text:
            missing_dataclasses.append(cls_name)

    print(f"Missing Payload Dataclass definitions in spec: {missing_dataclasses}")
    return {
        "table_topics": list(set(topic_table_matches)),
        "m1_events": list(set(m1_events)),
        "seq_events": list(set(seq_events)),
        "missing_payload_dataclasses": missing_dataclasses
    }

if __name__ == "__main__":
    with open(DOC_PATH, "r", encoding="utf-8") as f:
        doc_text = f.read()

    mermaid_res, m_blocks = test_mermaid_syntax()
    py_errors = test_python_snippets()
    yaml_errors = test_yaml_snippets()
    sql_errors = test_sql_schema()
    event_analysis = analyze_event_topics_and_schemas(doc_text)

    summary = {
        "mermaid_results": mermaid_res,
        "python_errors": py_errors,
        "yaml_errors": yaml_errors,
        "sql_errors": sql_errors,
        "event_analysis": event_analysis
    }
    with open("/tmp/verification_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("\nSaved empirical summary to /tmp/verification_summary.json")
