import sqlite3
import json

db_path = "data/state_ledger.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT output_payload FROM step_executions WHERE pipeline_run_id=(SELECT pipeline_run_id FROM step_executions ORDER BY created_at DESC LIMIT 1) AND step_name='script_generator'")
row = cur.fetchone()
if row:
    payload = json.loads(row['output_payload'])
    print(json.dumps(payload, indent=2))
else:
    print("No script generator output found.")
conn.close()
