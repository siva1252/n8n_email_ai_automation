import sqlite3
import subprocess
from pathlib import Path

dest = Path(__file__).resolve().parent.parent / "tmp_n8n" / "database.sqlite"
subprocess.check_call(["docker", "cp", "n8n:/home/node/.n8n/database.sqlite", str(dest)])
con = sqlite3.connect(dest)
print("workflow_entity cols", [r[1] for r in con.execute("PRAGMA table_info(workflow_entity)")])
print("published cols", [r[1] for r in con.execute("PRAGMA table_info(workflow_published_version)")])
rows = con.execute("SELECT id, name, active, versionId FROM workflow_entity").fetchall()
print("wf", rows)
print("users", con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%user%'").fetchall())
try:
    print("user rows", con.execute("SELECT id, email, role FROM user").fetchall())
except Exception as exc:
    print("user err", exc)
print("history count", con.execute("SELECT count(*) FROM workflow_history").fetchone())
print("shared", con.execute("SELECT * FROM shared_workflow").fetchall())
