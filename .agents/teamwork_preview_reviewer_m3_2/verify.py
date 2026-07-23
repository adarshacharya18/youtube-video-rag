import sys
import os
import re
import sqlite3
import yaml

TARGET_FILE = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase15/01_Platform_Evolution_Architecture.md"

def test_mermaid():
    print("=== Testing Mermaid Diagrams ===")
    with open(TARGET_FILE) as f:
        lines = f.readlines()
    
    blocks = []
    in_mermaid = False
    cur = []
    for line in lines:
        if line.strip() == "```mermaid":
            in_mermaid = True
            cur = []
        elif line.strip() == "```" and in_mermaid:
            in_mermaid = False
            blocks.append("".join(cur))
        elif in_mermaid:
            cur.append(line)
            
    print(f"Found {len(blocks)} Mermaid blocks.")
    for i, b in enumerate(blocks, 1):
        lines_b = [l.strip() for l in b.strip().splitlines() if l.strip()]
        header = lines_b[0]
        print(f"Diagram {i}: Header = '{header}', Total Lines = {len(lines_b)}")
    return blocks

def test_sql():
    print("\n=== Testing SQL DDL and Queries ===")
    with open(TARGET_FILE) as f:
        content = f.read()

    # Extract SQL blocks
    sql_blocks = re.findall(r'```sql\n(.*?)```', content, re.DOTALL)
    print(f"Found {len(sql_blocks)} SQL code blocks.")
    
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    
    # Block 1 should be DDL
    ddl_block = sql_blocks[0]
    print("Executing DDL Statements...")
    try:
        cursor.executescript(ddl_block)
        print("DDL Execution Successful!")
    except Exception as e:
        print(f"DDL Execution Failed: {e}")
        return False, e
        
    # Test tables created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Created Tables ({len(tables)}): {tables}")
    
    # Test Queries (blocks 1 to 4)
    queries = sql_blocks[1:]
    print(f"Testing {len(queries)} SQL Queries against populated schema...")
    
    for i, q in enumerate(queries, 1):
        print(f"\n--- Testing Query {i} ---")
        print(q.strip()[:100] + "...")
        # Prepare params if any
        # Query 1 uses :experiment_id
        try:
            if ":experiment_id" in q:
                cursor.execute(q, {"experiment_id": "exp_phase05_socratic_v3"})
            else:
                cursor.execute(q)
            print(f"Query {i} parsed & executed successfully! (Rows returned: {len(cursor.fetchall())})")
        except Exception as e:
            print(f"Query {i} Error: {e}")
            
    conn.close()

def test_yaml():
    print("\n=== Testing YAML Schema ===")
    with open(TARGET_FILE) as f:
        content = f.read()

    yaml_blocks = re.findall(r'```yaml\n(.*?)```', content, re.DOTALL)
    print(f"Found {len(yaml_blocks)} YAML blocks.")
    for i, y in enumerate(yaml_blocks, 1):
        try:
            parsed = yaml.safe_load(y)
            print(f"YAML Block {i} parsed successfully! Keys: {list(parsed.keys())}")
        except Exception as e:
            print(f"YAML Block {i} Error: {e}")

if __name__ == "__main__":
    test_mermaid()
    test_sql()
    test_yaml()
