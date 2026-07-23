import sqlite3
import re

def test_fixed_query4():
    doc_path = '/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase15/01_Platform_Evolution_Architecture.md'
    with open(doc_path, 'r', encoding='utf-8') as f:
        content = f.read()

    ddl_match = re.search(r'```sql\n(.*?)```', content[content.find('Section 5:'):content.find('Section 6:')], re.DOTALL)
    ddl_sql = ddl_match.group(1)

    conn = sqlite3.connect(':memory:')
    conn.executescript(ddl_sql)

    conn.execute("INSERT INTO experiments (experiment_id, name, status, target_phases, salt) VALUES ('e1', 'E1', 'ACTIVE', '[]', 's')")

    for i in range(1, 21):
        eval_time = f"2026-07-23 10:{i:02d}:00"
        score = 10.0 - (i * 0.25)
        conn.execute("INSERT INTO evolution_ledger VALUES (?, 'b1', ?, 'Phase05_ScriptGen', 'e1', 'control', 'SUCCESS', NULL, NULL, 100.0, 0, 0, 'CPU', ?)", (f'l_{i}', f'v_{i}', eval_time))
        conn.execute("INSERT INTO quality_metrics VALUES (?, ?, ?, 'control', ?, ?, ?, ?, 0, 'gemini-1.5-pro', ?)", (f'q_{i}', f'l_{i}', f'v_{i}', score, score, score, score, eval_time))

    fixed_q4 = """
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
    Boundaries AS (
        SELECT DISTINCT
            phase_id,
            FIRST_VALUE(rolling_avg_score) OVER (PARTITION BY phase_id ORDER BY evaluated_at ASC) AS initial_baseline_score,
            LAST_VALUE(rolling_avg_score) OVER (PARTITION BY phase_id ORDER BY evaluated_at ASC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS current_rolling_score
        FROM RollingScores
    )
    SELECT 
        phase_id,
        ROUND(initial_baseline_score, 2) AS initial_baseline_score,
        ROUND(current_rolling_score, 2) AS current_rolling_score,
        ROUND((initial_baseline_score - current_rolling_score) * 100.0 / initial_baseline_score, 2) AS prompt_decay_pct
    FROM Boundaries;
    """

    res = conn.execute(fixed_q4).fetchall()
    print("Fixed Query 4 Result:", res)

if __name__ == "__main__":
    test_fixed_query4()
