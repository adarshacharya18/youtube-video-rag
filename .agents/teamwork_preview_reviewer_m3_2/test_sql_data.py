import sqlite3
import re

TARGET_FILE = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase15/01_Platform_Evolution_Architecture.md"

def test_sql_with_data():
    with open(TARGET_FILE) as f:
        content = f.read()

    sql_blocks = re.findall(r'```sql\n(.*?)```', content, re.DOTALL)
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # DDL
    ddl_block = sql_blocks[0]
    cursor.executescript(ddl_block)

    # Insert sample data into tables
    cursor.execute("""
        INSERT INTO experiments (experiment_id, name, status, target_phases, salt)
        VALUES ('exp_phase05_socratic_v3', 'Socratic V3', 'ACTIVE', '["Phase05_ScriptGen"]', 'salt123')
    """)

    cursor.execute("""
        INSERT INTO evolution_ledger (ledger_id, batch_run_id, video_id, phase_id, experiment_id, variant_id, execution_status, error_type, latency_ms, input_tokens, output_tokens, created_at)
        VALUES 
        ('l1', 'batch_01', 'v1', 'Phase05_ScriptGen', 'exp_phase05_socratic_v3', 'control', 'SUCCESS', NULL, 1200.0, 500, 1000, '2026-07-23 10:00:00'),
        ('l2', 'batch_01', 'v2', 'Phase05_ScriptGen', 'exp_phase05_socratic_v3', 'treatment_socratic', 'SUCCESS', NULL, 1500.0, 600, 1200, '2026-07-23 10:05:00'),
        ('l3', 'batch_01', 'v3', 'Phase05_ScriptGen', 'exp_phase05_socratic_v3', 'treatment_socratic', 'FAILURE', 'QUALITY_REJECT', 1400.0, 550, 1100, '2026-07-23 10:10:00')
    """)

    cursor.execute("""
        INSERT INTO quality_metrics (metric_id, ledger_id, video_id, variant_id, overall_judge_score, pedagogical_clarity, code_correctness, visual_engagement, hallucination_flag, judge_model, evaluated_at)
        VALUES 
        ('m1', 'l1', 'v1', 'control', 8.8, 9.0, 9.5, 8.0, 0, 'gemini-1.5-pro', '2026-07-23 10:01:00'),
        ('m2', 'l2', 'v2', 'treatment_socratic', 9.2, 9.5, 9.8, 8.5, 0, 'gemini-1.5-pro', '2026-07-23 10:06:00'),
        ('m3', 'l3', 'v3', 'treatment_socratic', 7.5, 7.0, 8.0, 7.5, 1, 'gemini-1.5-pro', '2026-07-23 10:11:00')
    """)

    conn.commit()

    queries = sql_blocks[1:]
    for i, q in enumerate(queries, 1):
        print(f"\n================ SQL QUERY {i} ================")
        try:
            if ":experiment_id" in q:
                cursor.execute(q, {"experiment_id": "exp_phase05_socratic_v3"})
            else:
                cursor.execute(q)
            rows = cursor.fetchall()
            cols = [description[0] for description in cursor.description]
            print(f"Columns: {cols}")
            for r in rows:
                print(f"Row: {r}")
        except Exception as e:
            print(f"FAILED Query {i}: {e}")

    conn.close()

if __name__ == "__main__":
    test_sql_with_data()
