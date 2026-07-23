import sqlite3
import re
import sys

def run_sql_tests():
    doc_path = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase15/01_Platform_Evolution_Architecture.md"
    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract DDL block
    # Section 5.3 contains DDL
    ddl_match = re.search(r"```sql\n(.*?)```", content[content.find("Section 5:"):content.find("Section 6:")], re.DOTALL)
    if not ddl_match:
        print("ERROR: Could not extract DDL block from Section 5.3")
        sys.exit(1)
    
    ddl_sql = ddl_match.group(1)

    # Connect to in-memory SQLite database
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    print("=== EXECUTING DDL & INDEX STATEMENTS ===")
    try:
        cursor.executescript(ddl_sql)
        print("SUCCESS: DDL and Index creation executed cleanly.")
    except Exception as e:
        print(f"FAILED DDL: {e}")
        return

    # Verify tables created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print("Created tables:", tables)

    # Insert synthetic data to allow queries to run and test logic/execution
    print("\n=== INSERTING SYNTHETIC DATA FOR DML QUERY TESTS ===")
    cursor.execute("""
        INSERT INTO experiments (experiment_id, name, description, status, target_phases, salt)
        VALUES ('exp_phase05_socratic_v3', 'Socratic V3', 'Test exp', 'ACTIVE', '["Phase05_ScriptGen"]', 'salt123')
    """)

    cursor.executemany("""
        INSERT INTO evolution_ledger (ledger_id, batch_run_id, video_id, phase_id, experiment_id, variant_id, execution_status, error_type, error_message, latency_ms, input_tokens, output_tokens, compute_device, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        ('l1', 'batch1', 'video1', 'Phase05_ScriptGen', 'exp_phase05_socratic_v3', 'control', 'SUCCESS', None, None, 120.5, 500, 200, 'CPU', '2026-07-23 10:00:00'),
        ('l2', 'batch1', 'video2', 'Phase05_ScriptGen', 'exp_phase05_socratic_v3', 'treatment_socratic', 'SUCCESS', None, None, 150.0, 600, 300, 'CPU', '2026-07-23 10:05:00'),
        ('l3', 'batch1', 'video3', 'Phase05_ScriptGen', 'exp_phase05_socratic_v3', 'treatment_socratic', 'FAILURE', 'COMPUTE_RESOURCE', 'OOM', 50.0, 100, 0, 'GPU', '2026-07-23 10:10:00'),
        ('l4', 'batch2', 'video4', 'Phase06_Voice', 'exp_phase05_socratic_v3', 'control', 'SUCCESS', None, None, 200.0, 0, 0, 'NPU', '2026-07-23 11:00:00'),
    ])

    cursor.executemany("""
        INSERT INTO quality_metrics (metric_id, ledger_id, video_id, variant_id, overall_judge_score, pedagogical_clarity, code_correctness, visual_engagement, hallucination_flag, judge_model, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        ('q1', 'l1', 'video1', 'control', 9.0, 9.0, 9.0, 9.0, 0, 'gemini-1.5-pro', '2026-07-23 10:01:00'),
        ('q2', 'l2', 'video2', 'treatment_socratic', 8.5, 8.5, 8.5, 8.5, 0, 'gemini-1.5-pro', '2026-07-23 10:06:00'),
        ('q4', 'l4', 'video4', 'control', 9.2, 9.2, 9.2, 9.2, 0, 'gemini-1.5-pro', '2026-07-23 11:01:00'),
    ])

    conn.commit()

    # Extract Query 1, 2, 3, 4 from Section 6
    section6_content = content[content.find("Section 6:"):content.find("Section 7:")]
    query_blocks = re.findall(r"```sql\n(.*?)```", section6_content, re.DOTALL)

    print(f"\nFound {len(query_blocks)} queries in Section 6.")

    for idx, query_sql in enumerate(query_blocks, 1):
        print(f"\n--- TESTING QUERY {idx} ---")
        print("SQL string:\n", query_sql.strip())
        try:
            # Handle parameters if needed
            if ":experiment_id" in query_sql:
                cursor.execute(query_sql, {"experiment_id": "exp_phase05_socratic_v3"})
            else:
                cursor.execute(query_sql)
            results = cursor.fetchall()
            print(f"QUERY {idx} EXECUTED SUCCESSFULLY! Returned {len(results)} rows.")
            for row in results:
                print("  Row:", row)
        except Exception as e:
            print(f"QUERY {idx} FAILED WITH ERROR: {e}")

if __name__ == "__main__":
    run_sql_tests()
