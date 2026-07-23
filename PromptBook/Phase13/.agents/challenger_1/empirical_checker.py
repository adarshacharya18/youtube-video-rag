#!/usr/bin/env python3
import ast
import json
import re
import sqlite3
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

def test_mermaid_syntax_py(mermaid_blocks):
    print("=== 1. MERMAID DIAGRAM SYNTAX & LOGIC ANALYSIS ===")
    results = []
    for idx, code in enumerate(mermaid_blocks, 1):
        lines = [l.strip() for l in code.splitlines() if l.strip() and not l.strip().startswith("%%")]
        first_line = lines[0] if lines else ""
        
        errors = []
        # Check diagram type
        valid_types = ["graph", "flowchart", "sequenceDiagram", "gantt", "classDiagram", "stateDiagram"]
        if not any(first_line.startswith(vt) for vt in valid_types):
            errors.append(f"Invalid or missing diagram header: '{first_line}'")
        
        if first_line.startswith("sequenceDiagram"):
            # Check for illegal participant names with spaces/parens without alias
            participants = set()
            for line in lines:
                if line.startswith("participant"):
                    parts = line.split()
                    if len(parts) >= 2:
                        participants.add(parts[1])
            
            for line in lines:
                if "->" in line or "--" in line:
                    # check arrow lines
                    # e.g. External API (YouTube)-->>YouTube
                    match = re.search(r"^([A-Za-z0-9_\s\(\)]+?)(--?>|--?>>|-x|--x)([A-Za-z0-9_\s\(\)]+?):", line)
                    if match:
                        src, arrow, tgt = match.group(1).strip(), match.group(2), match.group(3).strip()
                        if "(" in src or ")" in src:
                            errors.append(f"Unescaped/unquoted participant with parens in line: '{line}'")
                        if "(" in tgt or ")" in tgt:
                            errors.append(f"Unescaped/unquoted target with parens in line: '{line}'")

        results.append({
            "index": idx,
            "header": first_line,
            "errors": errors,
            "passed": len(errors) == 0
        })
        print(f"Diagram {idx} [{first_line}]: {'PASS' if len(errors) == 0 else 'FAIL'}")
        for err in errors:
            print(f"   -> {err}")
    return results

def test_python_snippets(blocks):
    print("\n=== 2. PYTHON CODE SNIPPETS AST SYNTAX CHECK ===")
    py_blocks = [(idx, b[1]) for idx, b in enumerate(blocks) if b[0] == "python"]
    print(f"Found {len(py_blocks)} Python code blocks.")

    errors = []
    for idx, code in py_blocks:
        try:
            ast.parse(code)
            print(f"Python block {idx}: PASS")
        except SyntaxError as e:
            print(f"Python block {idx}: FAIL -> SyntaxError line {e.lineno}: {e.msg}")
            errors.append({"block_idx": idx, "line": e.lineno, "msg": e.msg, "text": e.text})
    return errors

def test_yaml_snippets(blocks):
    print("\n=== 3. YAML CODE SNIPPETS SYNTAX CHECK ===")
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

def test_sql_schema(blocks):
    print("\n=== 4. SQL SCHEMA SYNTAX & EXECUTION CHECK ===")
    sql_blocks = [(idx, b[1]) for idx, b in enumerate(blocks) if b[0] == "sql"]
    print(f"Found {len(sql_blocks)} SQL code blocks.")

    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    errors = []
    for idx, sql_code in sql_blocks:
        try:
            cursor.executescript(sql_code)
            print(f"SQL block {idx}: PASS")
        except sqlite3.Error as e:
            print(f"SQL block {idx}: FAIL -> SQLite Error: {e}")
            errors.append({"block_idx": idx, "error": str(e)})
    return errors

def analyze_event_topics_and_schemas(doc_text):
    print("\n=== 5. EVENT BUS TOPICS & SCHEMAS ANALYSIS ===")
    
    # Topic Table
    table_topics = re.findall(r"\| `([a-z0-9_\.]+)` \|", doc_text)
    
    # Sequence Topics
    seq_topics = re.findall(r'Publish \[([a-z0-9_\.]+)\]', doc_text)
    
    # Workflow YAML topics/tasks
    yaml_tasks = re.findall(r'id:\s*"([a-z0-9_]+)"', doc_text)

    # Prompt specified topics
    required_topics = [
        "media.voice.generated",
        "media.animation.rendered",
        "media.subtitles.generated",
        "media.video.assembled",
        "media.published"
    ]

    print(f"Table topics (Sec 1.6): {table_topics}")
    print(f"Sequence topics (Sec 1.2): {seq_topics}")
    
    topic_mismatches = []
    for req in required_topics:
        if req not in doc_text:
            topic_mismatches.append(req)

    # Payload dataclasses search
    payload_dataclasses = [
        "ScriptApprovedPayload", "VoiceSynthesisStartedPayload", "AudioRenderedPayload",
        "AnimationRenderStartedPayload", "RenderCompletePayload", "SubtitleCompletePayload",
        "VideoAssembledPayload", "ThumbnailCompletePayload", "YoutubePublishedPayload",
        "PipelineFailedPayload"
    ]
    missing_dataclasses = []
    for cls in payload_dataclasses:
        if f"class {cls}" not in doc_text and f"@dataclass\nclass {cls}" not in doc_text and f"class {cls}(" not in doc_text:
            missing_dataclasses.append(cls)

    print(f"Required topics missing from doc: {topic_mismatches}")
    print(f"Payload dataclass definitions missing from doc: {missing_dataclasses}")

    return {
        "table_topics": table_topics,
        "seq_topics": seq_topics,
        "required_missing": topic_mismatches,
        "missing_payload_dataclasses": missing_dataclasses
    }

if __name__ == "__main__":
    with open(DOC_PATH, "r", encoding="utf-8") as f:
        doc_text = f.read()

    blocks = extract_code_blocks(doc_text)
    mermaid_blocks = [b[1] for b in blocks if b[0] == "mermaid"]
    
    m_res = test_mermaid_syntax_py(mermaid_blocks)
    py_err = test_python_snippets(blocks)
    yaml_err = test_yaml_snippets(blocks)
    sql_err = test_sql_schema(blocks)
    event_res = analyze_event_topics_and_schemas(doc_text)

    res = {
        "mermaid": m_res,
        "python_errors": py_err,
        "yaml_errors": yaml_err,
        "sql_errors": sql_err,
        "event_analysis": event_res
    }
    with open("/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/.agents/challenger_1/verification_results.json", "w") as f:
        json.dump(res, f, indent=2)
    print("\nWrote results to verification_results.json")
