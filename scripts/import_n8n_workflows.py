"""Create n8n owner (if needed) and import versioned workflows."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BASE = os.environ.get("N8N_PUBLIC_URL", "http://localhost:5678").rstrip("/")
EMAIL = os.environ.get("N8N_OWNER_EMAIL", "admin@localhost")
PASSWORD = os.environ.get("N8N_OWNER_PASSWORD", "DemoAdmin123!")
FIRST = "Demo"
LAST = "Owner"
WORKFLOWS = ROOT / "n8n" / "workflows"


def wait() -> None:
    for _ in range(60):
        try:
            r = requests.get(f"{BASE}/healthz", timeout=3)
            if r.status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise SystemExit("n8n is not reachable on /healthz")


def session() -> requests.Session:
    s = requests.Session()
    setup = {
        "email": EMAIL,
        "firstName": FIRST,
        "lastName": LAST,
        "password": PASSWORD,
    }
    r = s.post(f"{BASE}/rest/owner/setup", json=setup, timeout=15)
    if r.status_code >= 400:
        r = s.post(f"{BASE}/rest/login", json={"emailOrLdapLoginId": EMAIL, "password": PASSWORD}, timeout=15)
        r.raise_for_status()
    return s


def import_workflows(s: requests.Session) -> None:
    existing = s.get(f"{BASE}/rest/workflows", timeout=15)
    existing.raise_for_status()
    data = existing.json()
    names = {w.get("name") for w in (data.get("data") or data or []) if isinstance(w, dict)}
    for path in sorted(WORKFLOWS.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        name = payload.get("name") or path.stem
        if name in names:
            print(f"skip existing {name}")
            continue
        r = s.post(f"{BASE}/rest/workflows", json=payload, timeout=20)
        if r.status_code >= 400:
            print(f"import failed {name}: {r.status_code} {r.text[:400]}")
        else:
            print(f"imported {name}")


def main() -> None:
    wait()
    s = session()
    import_workflows(s)
    print("n8n import finished. Connect Gmail OAuth in the UI before activating Gmail nodes.")


if __name__ == "__main__":
    main()
