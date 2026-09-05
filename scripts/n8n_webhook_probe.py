import json
import sqlite3
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

dest = Path(__file__).resolve().parent.parent / "tmp_n8n" / "database.sqlite"
subprocess.check_call(["docker", "cp", "n8n:/home/node/.n8n/database.sqlite", str(dest)])
con = sqlite3.connect(dest)
print("published", con.execute("SELECT * FROM workflow_published_version").fetchall())
print("triggers", con.execute("SELECT * FROM workflow_publication_trigger_status").fetchall())
print("history", con.execute("SELECT workflowId, event, createdAt FROM workflow_publish_history ORDER BY createdAt DESC LIMIT 8").fetchall())

for path in ("/webhook/ingest-email", "/webhook/deal-action", "/webhook-test/ingest-email"):
    req = Request(
        f"http://127.0.0.1:5678{path}",
        data=json.dumps({"subject": "ping", "threadId": "ping-1", "from": "a@b.com"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as r:
            body = r.read()
            print(path, r.status, "len", len(body), "ctype", r.headers.get("Content-Type"), "start", body[:80])
    except Exception as exc:
        print(path, type(exc).__name__, exc)
