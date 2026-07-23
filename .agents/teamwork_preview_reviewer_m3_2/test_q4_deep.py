import sqlite3
import re

TARGET_FILE = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase15/01_Platform_Evolution_Architecture.md"

def test_query4_details():
    with open(TARGET_FILE) as f:
        content = f.read()

    sql_blocks = re.findall(r'```sql\n(.*?)```', content, re.DOTALL)
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # DDL
    ddl_block = sql_blocks[0]
    cursor.executescript(ddl_block)

    cursor.execute("""
        INSERT INTO experiments (experiment_id, name, status, target_phases, salt)
        VALUES ('exp1', 'exp1', 'ACTIVE', '["Phase05_ScriptGen"]', 'salt')
    """)

    # Insert 5 rows with different timestamps and different scores
    for i in range(1, 10):
        cursor.execute(f"""
            INSERT INTO evolution_ledger (ledger_id, batch_run_id, video_id, phase_id, experiment_id, variant_id, execution_status, latency_ms, created_at)
            VALUES ('l{i}', 'batch1', 'v{i}', 'Phase05_ScriptGen', 'exp1', 'control', 'SUCCESS', 1000, '2026-07-23 10:0{i}:00')
        """)
        # Score decreasing over time: 10.0 down to 5.0
        score = 10.0 - i * 0.5
        cursor.execute(f"""
            INSERT INTO quality_metrics (metric_id, ledger_id, video_id, variant_id, overall_judge_score, pedagogical_clarity, code_correctness, visual_engagement, hallucination_flag, judge_model, evaluated_at)
            VALUES ('m{i}', 'l{i}', 'v{i}', 'control', {score}, 9.0, 9.0, 9.0, 0, 'gemini', '2026-07-23 10:0{i}:00')
        """)

    conn.commit()

    q4 = sql_blocks[4] # 5th block is Query 4
    print("--- Query 4 Execution ---")
    cursor.execute(q4)
    cols = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    print("Columns:", cols)
    for r in rows:
        print("Row:", r)

    # Now let's compare with Query 4 WITHOUT GROUP BY or using Subquery/DISTINCT
    q4_fixed = """
    WITH RollingScores AS (
        SELECT 
            q.judge_model,
            l.phase_id,
            q.evaluated_at,
            q.overall_judge_score,
            AVG(q.overall_judge_score) OVER (
                PARTITION BY l.phase_id, l.variant_id 
                ORDER BY q.evaluated_at 
                ROWS BETWEEN 50 PRECEDING AND CURRENT ROW
            ) AS rolling_avg_score
        FROM quality_metrics q
        JOIN evolution_ledger l ON q.ledger_id = l.ledger_id
    ),
    DecayCalc AS (
        SELECT 
            phase_id,
            FIRST_VALUE(rolling_avg_score) OVER (PARTITION BY phase_id ORDER BY evaluated_at ASC) AS initial_baseline_score,
            LAST_VALUE(rolling_avg_score) OVER (PARTITION BY phase_id ORDER BY evaluated_at ASC RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS current_rolling_score
        FROM RollingScores
    )
    SELECT DISTINCT
        phase_id,
        ROUND(initial_baseline_score, 2) AS initial_baseline_score,
        ROUND(current_rolling_score, 2) AS current_rolling_score,
        ROUND((initial_baseline_score - current_rolling_score) * 100.0 / initial_baseline_score, 2) AS prompt_decay_pct
    FROM DecayCalc;
    """
    print("\n--- Fixed Query 4 Execution ---")
    cursor.execute(q4_fixed)
    cols = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    print("Columns:", cols)
    for r in rows:
        print("Row:", r)

    conn.close()

if __name__ == "__main__":
    test_query4_details()
