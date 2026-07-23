import ast
import re
import sys
import os

TARGET_FILE = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md"

def test_file_existence():
    print("--- Phase 1: Canonical Adherence & Existence ---")
    if not os.path.exists(TARGET_FILE):
        print("FAIL: Target file does not exist!")
        return False
    print(f"PASS: Target file exists at {TARGET_FILE}")
    print(f"File size: {os.path.getsize(TARGET_FILE)} bytes")
    return True

def analyze_requirements():
    print("\n--- Phase 1: Requirements Audit ---")
    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    reqs = {
        "R1 Integration Points": [
            ("Educational Content Platform", re.compile(r"Educational Content Platform", re.IGNORECASE)),
            ("Plugin Platform SDK", re.compile(r"Plugin Platform", re.IGNORECASE)),
            ("Workflow Engine", re.compile(r"Workflow Engine", re.IGNORECASE)),
            ("Event Bus", re.compile(r"Event Bus", re.IGNORECASE)),
            ("Persistence Layer", re.compile(r"Persistence Layer", re.IGNORECASE)),
        ],
        "R1 Diagrams": [
            ("Architecture Diagram", re.compile(r"```mermaid[\s\S]*?(?:graph|architecture|C4Context|flowchart)[\s\S]*?```", re.IGNORECASE)),
            ("Sequence Diagram", re.compile(r"```mermaid[\s\S]*?sequenceDiagram[\s\S]*?```", re.IGNORECASE)),
            ("Component Diagram", re.compile(r"```mermaid[\s\S]*?(?:classDiagram|graph|flowchart|C4Component)[\s\S]*?```", re.IGNORECASE)),
        ],
        "R2 Core Responsibilities": [
            ("Voice Production", re.compile(r"Voice Production|Kokoro|TTS", re.IGNORECASE)),
            ("Animation Production", re.compile(r"Animation Production|Manim", re.IGNORECASE)),
            ("Subtitle Generation", re.compile(r"Subtitle Generation|Whisper|SRT|VTT", re.IGNORECASE)),
            ("Video Assembly", re.compile(r"Video Assembly|FFmpeg", re.IGNORECASE)),
            ("Thumbnail Generation", re.compile(r"Thumbnail Generation|Pillow|ImageMagick", re.IGNORECASE)),
            ("Publishing", re.compile(r"Publishing|YouTube|Social", re.IGNORECASE)),
            ("Artifact Tracking", re.compile(r"Artifact Tracking|ArtifactStore|Storage", re.IGNORECASE)),
            ("SPI Provider Abstraction", re.compile(r"SPI|Provider|Plugin", re.IGNORECASE)),
        ],
        "R3 Resiliency & Extensibility": [
            ("Exponential Backoff / Jitter", re.compile(r"backoff|jitter", re.IGNORECASE)),
            ("Stateful Circuit Breaker", re.compile(r"CircuitBreaker|circuit_breaker|Stateful", re.IGNORECASE)),
            ("DLQ with JSON serialization", re.compile(r"DLQ|Dead-Letter|DeadLetter|json", re.IGNORECASE)),
            ("Step Checkpointing / Segment Hash", re.compile(r"checkpoint|segment_hash|deduplication", re.IGNORECASE)),
            ("Metrics & Monitoring", re.compile(r"metric|prometheus|monitoring", re.IGNORECASE)),
            ("Tracing", re.compile(r"tracing|opentelemetry|trace_id", re.IGNORECASE)),
            ("Fallback Chains", re.compile(r"fallback|FallbackChain", re.IGNORECASE)),
        ]
    }

    all_passed = True
    for cat, items in reqs.items():
        print(f"\nChecking Category: {cat}")
        for label, pattern in items:
            matches = pattern.findall(content)
            if matches:
                print(f"  [PASS] {label}: Found {len(matches)} match(es)")
            else:
                print(f"  [FAIL] {label}: NOT FOUND!")
                all_passed = False
    return all_passed

def analyze_cheating_and_integrity():
    print("\n--- Phase 2: Cheating & Integrity Audit ---")
    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check suspicious markers
    suspicious_patterns = [
        ("TODO markers", re.compile(r"\bTODO\b")),
        ("FIXME markers", re.compile(r"\bFIXME\b")),
        ("XXX markers", re.compile(r"\bXXX\b")),
        ("STUB markers", re.compile(r"\bSTUB\b")),
        ("Mock implementations", re.compile(r"\bMock[A-Z]\w+")),
        ("NotImplementedError", re.compile(r"raise NotImplementedError")),
        ("Ellipsis placeholders", re.compile(r"^\s*\.\.\.\s*$", re.MULTILINE)),
    ]

    integrity_passed = True
    for label, pattern in suspicious_patterns:
        matches = pattern.findall(content)
        if matches:
            print(f"  [WARNING/FAIL] Found {len(matches)} occurrence(s) of {label}: {matches[:5]}")
            # If TODO/FIXME/XXX or stubbed code, flag
            if label in ["TODO markers", "FIXME markers", "XXX markers", "STUB markers", "Ellipsis placeholders"]:
                integrity_passed = False
        else:
            print(f"  [PASS] No {label} found.")

    return integrity_passed

def extract_and_verify_python_code():
    print("\n--- Phase 2/3: Extracting & Parsing Python Snippets via AST ---")
    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    python_blocks = re.findall(r"```python([\s\S]*?)```", content)
    print(f"Found {len(python_blocks)} python code blocks.")

    ast_passed = True
    combined_code = []

    for idx, block in enumerate(python_blocks, 1):
        try:
            tree = ast.parse(block)
            print(f"  Block {idx} (lines {block.count('\n') + 1}): AST parse SUCCESSFUL.")
            combined_code.append(block)
        except SyntaxError as e:
            print(f"  Block {idx}: SyntaxError: {e}")
            ast_passed = False

    return ast_passed, combined_code

def check_mermaid_diagrams():
    print("\n--- Phase 2: Mermaid Diagram Syntax Audit ---")
    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    mermaid_blocks = re.findall(r"```mermaid([\s\S]*?)```", content)
    print(f"Found {len(mermaid_blocks)} Mermaid diagram blocks.")

    if not mermaid_blocks:
        print("FAIL: No Mermaid diagrams found!")
        return False

    valid = True
    for idx, block in enumerate(mermaid_blocks, 1):
        lines = block.strip().split('\n')
        header = lines[0].strip()
        print(f"  Diagram {idx}: Header line: '{header}', line count: {len(lines)}")
        if not any(header.startswith(kw) for kw in ["graph", "sequenceDiagram", "classDiagram", "stateDiagram", "erDiagram", "gantt", "pie", "flowchart", "C4Context", "C4Component", "architecture-beta"]):
            print(f"    WARNING: Diagram {idx} header '{header}' does not start with standard Mermaid keyword.")
    return valid

if __name__ == "__main__":
    t_ok = test_file_existence()
    r_ok = analyze_requirements()
    c_ok = analyze_cheating_and_integrity()
    ast_ok, blocks = extract_and_verify_python_code()
    m_ok = check_mermaid_diagrams()

    print("\n================ SUMMARY ================")
    print(f"Existence: {t_ok}")
    print(f"Requirements: {r_ok}")
    print(f"Integrity: {c_ok}")
    print(f"Python AST: {ast_ok}")
    print(f"Mermaid Diagrams: {m_ok}")
