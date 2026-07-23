import sqlite3
import re

def test_sql_extended():
    doc_path = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase15/01_Platform_Evolution_Architecture.md"
    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()

    ddl_match = re.search(r"```sql\n(.*?)```", content[content.find("Section 5:"):content.find("Section 6:")], re.DOTALL)
    ddl_sql = ddl_match.group(1)

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    cursor.executescript(ddl_sql)

    # Populate multiple rows for Query 4 to test GROUP BY + Window Function behavior
    cursor.execute("""
        INSERT INTO experiments (experiment_id, name, description, status, target_phases, salt)
        VALUES ('exp1', 'Exp 1', 'Desc', 'ACTIVE', '["Phase05_ScriptGen"]', 'salt1')
    """)

    for i in range(1, 20):
        ledger_id = f"l_{i}"
        vid_id = f"v_{i}"
        eval_time = f"2026-07-23 10:{i:02d}:00"
        score = 9.0 - (i * 0.1) # Decaying score: 8.9 down to 7.0
        
        cursor.execute("""
            INSERT INTO evolution_ledger (ledger_id, batch_run_id, video_id, phase_id, experiment_id, variant_id, execution_status, latency_ms, created_at)
            VALUES (?, 'b1', ?, 'Phase05_ScriptGen', 'exp1', 'control', 'SUCCESS', 100.0, ?)
        """, (ledger_id, vid_id, eval_time))

        cursor.execute("""
            INSERT INTO quality_metrics (metric_id, ledger_id, video_id, variant_id, overall_judge_score, pedagogical_clarity, code_correctness, visual_engagement, hallucination_flag, judge_model, evaluated_at)
            VALUES (?, ?, ?, 'control', ?, ?, ?, ?, 0, 'gemini-1.5-pro', ?)
        """, (f"q_{i}", ledger_id, vid_id, score, score, score, score, eval_time))

    conn.commit()

    section6_content = content[content.find("Section 6:"):content.find("Section 7:")]
    query_blocks = re.findall(r"```sql\n(.*?)```", section6_content, re.DOTALL)

    query4 = query_blocks[3]
    print("--- TESTING QUERY 4 WITH 19 DECAYING SCORE ROWS ---")
    try:
        cursor.execute(query4)
        rows = cursor.fetchall()
        print("Query 4 output with 19 rows:")
        for r in rows:
            print("  ", r)
    except Exception as e:
        print(f"Query 4 Exception: {e}")

    # Also test FK constraints and ENUM constraints on tables
    print("\n--- TESTING TABLE CONSTRAINTS ---")
    # Test status check constraint on experiments
    try:
        cursor.execute("INSERT INTO experiments (experiment_id, name, status, target_phases, salt) VALUES ('e_bad', 'Bad', 'INVALID_STATUS', '[]', 's')")
        print("FAIL: CHECK constraint on status did NOT trigger!")
    except sqlite3.IntegrityError as e:
        print(f"PASS: CHECK constraint on experiments.status triggered correctly ({e})")

    # Test execution_status check constraint on evolution_ledger
    try:
        cursor.execute("INSERT INTO evolution_ledger (ledger_id, batch_run_id, video_id, phase_id, variant_id, execution_status, latency_ms) VALUES ('l_bad', 'b', 'v', 'p', 'v', 'INVALID', 10.0)")
        print("FAIL: CHECK constraint on execution_status did NOT trigger!")
    except sqlite3.IntegrityError as e:
        print(f"PASS: CHECK constraint on evolution_ledger.execution_status triggered correctly ({e})")

if __name__ == "__main__":
    test_sql_extended()
