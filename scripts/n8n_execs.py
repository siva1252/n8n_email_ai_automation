import sqlite3
import subprocess
from pathlib import Path

dest = Path(__file__).resolve().parent.parent / "tmp_n8n" / "database.sqlite"
subprocess.check_call(["docker", "cp", "n8n:/home/node/.n8n/database.sqlite", str(dest)])
con = sqlite3.connect(dest)
print("tables", [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() if "exec" in r[0].lower() or "workflow" in r[0].lower()])
try:
    rows = con.execute(
        "SELECT id, workflowId, status, mode, startedAt, stoppedAt FROM execution_entity ORDER BY id DESC LIMIT 8"
    ).fetchall()
    print("executions", rows)
except Exception as exc:
    print("exec err", exc)
print("workflows", con.execute("SELECT id, name, active FROM workflow_entity").fetchall())
