"""Repair n8n volume permissions, import workflows, and activate Gmail pipelines."""
from __future__ import annotations

import sqlite3
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / "tmp_n8n"
TMP.mkdir(exist_ok=True)
DB = TMP / "database.sqlite"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(str(c) for c in cmd[:14]))
    return subprocess.run(cmd, check=check)


def wait_healthy(tries: int = 24) -> bool:
    for _ in range(tries):
        try:
            with urllib.request.urlopen("http://127.0.0.1:5678/healthz", timeout=3) as r:
                if r.status == 200:
                    print("n8n health ok")
                    return True
        except Exception:
            time.sleep(5)
    return False


def activate_sqlite() -> None:
    copied = run(["docker", "cp", "n8n:/home/node/.n8n/database.sqlite", str(DB)], check=False)
    if copied.returncode != 0 or not DB.exists():
        raise SystemExit("Could not copy n8n sqlite")
    con = sqlite3.connect(DB)
    print("workflows", con.execute("SELECT id, name, active FROM workflow_entity").fetchall())
    con.execute(
        "UPDATE workflow_entity SET active=1 WHERE id IN ('incoming-email-pipeline','deal-action-webhook')"
    )
    con.commit()
    print("activated", con.execute("SELECT id, name, active FROM workflow_entity").fetchall())
    con.close()
    run(["docker", "cp", str(DB), "n8n:/home/node/.n8n/database.sqlite"])
    run(
        [
            "docker",
            "run",
            "--rm",
            "-u",
            "0",
            "-v",
            "n8n_data:/data",
            "alpine",
            "sh",
            "-c",
            "chown -R 1000:1000 /data && chmod -R u+rwX,g+rwX /data && ls -l /data/database.sqlite",
        ]
    )


def main() -> None:
    run(["docker", "stop", "n8n"], check=False)
    run(
        [
            "docker",
            "run",
            "--rm",
            "-u",
            "0",
            "-v",
            "n8n_data:/data",
            "alpine",
            "sh",
            "-c",
            "chown -R 1000:1000 /data && chmod -R u+rwX,g+rwX /data && ls -l /data | head",
        ]
    )
    started = run(["docker", "start", "n8n"], check=False)
    if started.returncode != 0:
        raise SystemExit("docker start n8n failed")
    if not wait_healthy():
        run(["docker", "logs", "n8n", "--tail", "50"], check=False)
        raise SystemExit("n8n did not become healthy after permission fix")

    run(["docker", "cp", str(ROOT / "n8n" / "workflows"), "n8n:/tmp/workflows"], check=False)
    for name in ("incoming_email.json", "deal_action.json", "reconcile.json"):
        run(
            ["docker", "exec", "n8n", "n8n", "import:workflow", f"--input=/tmp/workflows/{name}"],
            check=False,
        )

    run(["docker", "stop", "n8n"], check=False)
    activate_sqlite()
    run(["docker", "start", "n8n"], check=False)
    if not wait_healthy():
        run(["docker", "logs", "n8n", "--tail", "50"], check=False)
        raise SystemExit("n8n did not become healthy after activate")


if __name__ == "__main__":
    main()
