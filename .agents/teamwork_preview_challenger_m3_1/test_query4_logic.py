import sqlite3
import re

def test_query4_logic():
    doc_path = '/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase15/01_Platform_Evolution_Architecture.md'
    with open(doc_path, 'r', encoding='utf-8') as f:
        content = f.read()

    ddl_match = re.search(r'```sql\n(.*?)```', content[content.find('Section 5:'):content.find('Section 6:')], re.DOTALL)
    ddl_sql = ddl_match.group(1)

    conn = sqlite3.connect(':memory:')
    conn.executescript(ddl_sql)

    conn.execute("INSERT INTO experiments (experiment_id, name, status, target_phases, salt) VALUES ('e1', 'E1', 'ACTIVE', '[]', 's')")

    # Insert 20 rows with DECAYING scores from 9.75 down to 5.0
    for i in range(1, 21):
        eval_time = f"2026-07-23 10:{i:02d}:00"
        score = 10.0 - (i * 0.25) # 9.75 down to 5.0
        conn.execute("INSERT INTO evolution_ledger VALUES (?, 'b1', ?, 'Phase05_ScriptGen', 'e1', 'control', 'SUCCESS', NULL, NULL, 100.0, 0, 0, 'CPU', ?)", (f'l_{i}', f'v_{i}', eval_time))
        conn.execute("INSERT INTO quality_metrics VALUES (?, ?, ?, 'control', ?, ?, ?, ?, 0, 'gemini-1.5-pro', ?)", (f'q_{i}', f'l_{i}', f'v_{i}', score, score, score, score, eval_time))
    conn.commit()

    section6 = content[content.find('Section 6:'):content.find('Section 7:')]
    query_blocks = re.findall(r'```sql\n(.*?)```', section6, re.DOTALL)
    q4 = query_blocks[3]

    print("=== EXECUTING QUERY 4 ON DECAYING DATA ===")
    res = conn.execute(q4).fetchall()
    print("Query 4 Result (with GROUP BY phase_id):")
    for r in res:
        print("  ", r)

    print("\n=== EXECUTING RollingScores CTE SEPARATELY ===")
    cte_q = """
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
    )
    SELECT phase_id, evaluated_at, overall_judge_score, rolling_avg_score FROM RollingScores ORDER BY evaluated_at;
    """
    rows = conn.execute(cte_q).fetchall()
    print(f"First row in RollingScores: evaluated_at={rows[0][1]}, score={rows[0][2]}, rolling_avg={rows[0][3]}")
    print(f"Last row in RollingScores: evaluated_at={rows[-1][1]}, score={rows[-1][2]}, rolling_avg={rows[-1][3]}")

if __name__ == "__main__":
    test_query4_logic()
