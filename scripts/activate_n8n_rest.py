import sqlite3
import subprocess
from pathlib import Path

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
env = dotenv_values(ROOT / ".env")
EMAIL = env.get("N8N_OWNER_EMAIL") or "admin@localhost"
PASSWORD = env.get("N8N_OWNER_PASSWORD") or "DemoAdmin123!"
BASE = "http://127.0.0.1:5678"


def main() -> None:
    s = requests.Session()
    r = s.post(f"{BASE}/rest/login", json={"emailOrLdapLoginId": EMAIL, "password": PASSWORD}, timeout=15)
    print("login", r.status_code)
    w = s.get(f"{BASE}/rest/workflows", timeout=15)
    print("list", w.status_code)
    data = w.json()
    items = data.get("data") if isinstance(data, dict) else data
    for item in items or []:
        if isinstance(item, dict):
            print("item", item.get("id"), item.get("name"), "active", item.get("active"))

    for wf_id in ("incoming-email-pipeline", "deal-action-webhook"):
        for method, path, payload in (
            ("POST", f"/rest/workflows/{wf_id}/activate", None),
            ("POST", f"/rest/workflows/{wf_id}/publish", {"versionId": None}),
            ("PATCH", f"/rest/workflows/{wf_id}", {"active": True}),
        ):
            if method == "POST":
                resp = s.post(BASE + path, json=payload, timeout=20)
            else:
                resp = s.patch(BASE + path, json=payload, timeout=20)
            print(method, path, resp.status_code, resp.text[:220].replace("\n", " "))

    dest = ROOT / "tmp_n8n" / "database.sqlite"
    subprocess.check_call(["docker", "cp", "n8n:/home/node/.n8n/database.sqlite", str(dest)])
    con = sqlite3.connect(dest)
    print("wf_after", con.execute("SELECT id, name, active, activeVersionId FROM workflow_entity").fetchall())


if __name__ == "__main__":
    main()
