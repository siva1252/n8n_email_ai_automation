import sqlite3
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "tmp_n8n" / "database.sqlite"
IDS = ("incoming-email-pipeline", "deal-action-webhook")


def wait() -> None:
    for _ in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:5678/healthz", timeout=3) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(2)
    raise SystemExit("n8n not healthy")


def copy_from_container() -> None:
    DB.parent.mkdir(exist_ok=True)
    for name in ("database.sqlite", "database.sqlite-wal", "database.sqlite-shm"):
        subprocess.run(
            ["docker", "cp", f"n8n:/home/node/.n8n/{name}", str(DB.parent / name)],
            check=False,
        )


def main() -> None:
    copy_from_container()
    con = sqlite3.connect(DB)
    print("before", con.execute("SELECT id, name, active, activeVersionId, versionId FROM workflow_entity").fetchall())
    for wf_id in IDS:
        row = con.execute(
            "SELECT versionId FROM workflow_entity WHERE id=?",
            (wf_id,),
        ).fetchone()
        if not row or not row[0]:
            continue
        con.execute(
            "UPDATE workflow_entity SET active=1, activeVersionId=? WHERE id=?",
            (row[0], wf_id),
        )
    con.commit()
    print("after", con.execute("SELECT id, name, active, activeVersionId, versionId FROM workflow_entity").fetchall())
    con.close()
    subprocess.check_call(["docker", "stop", "n8n"])
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-u",
            "0",
            "-v",
            "n8n_data:/data",
            "-v",
            f"{DB.parent.resolve()}:/src",
            "alpine",
            "sh",
            "-c",
            "cp /src/database.sqlite /data/database.sqlite && rm -f /data/database.sqlite-wal /data/database.sqlite-shm && chown 1000:1000 /data/database.sqlite && chmod 664 /data/database.sqlite",
        ],
        check=True,
    )
    subprocess.check_call(["docker", "start", "n8n"])
    wait()
    print("n8n restarted")


if __name__ == "__main__":
    main()
