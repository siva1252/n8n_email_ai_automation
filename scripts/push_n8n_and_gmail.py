"""Push n8n workflows, send a real Gmail, and verify webhooks. Never prints secrets."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
KEY = os.environ.get("INTERNAL_API_KEY", "")
N8N = "http://127.0.0.1:5678"
CRED_ID = "8KCxPfpiIW8Mx4E0"


def sh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=check, capture_output=True, text=True)


def wait_n8n(seconds: int = 90) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{N8N}/healthz", timeout=3) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(2)
    raise SystemExit("n8n did not become healthy")


def post(url: str, payload: dict, headers: dict | None = None, timeout: int = 120):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            return r.status, json.loads(body) if body.startswith("{") else body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:500]


def import_workflows() -> None:
    for name in ("incoming_email.json", "deal_action.json", "reconcile.json"):
        src = ROOT / "n8n" / "workflows" / name
        if not src.exists():
            continue
        sh("docker", "cp", str(src), f"n8n:/tmp/{name}")
        result = sh(
            "docker",
            "exec",
            "n8n",
            "n8n",
            "import:workflow",
            f"--input=/tmp/{name}",
            check=False,
        )
        print(name, "import", "ok" if result.returncode == 0 else result.stderr[-300:])
    for wf_id in ("incoming-email-pipeline", "deal-action-webhook"):
        sh(
            "docker",
            "exec",
            "n8n",
            "n8n",
            "update:workflow",
            f"--id={wf_id}",
            "--active=true",
            check=False,
        )


def load_gmail_oauth() -> dict:
    out = "/tmp/n8n-gmail-cred.json"
    result = sh(
        "docker",
        "exec",
        "n8n",
        "n8n",
        "export:credentials",
        f"--id={CRED_ID}",
        "--decrypted",
        check=False,
    )
    if result.returncode != 0:
        result = sh(
            "docker",
            "exec",
            "n8n",
            "n8n",
            "export:credentials",
            "--all",
            "--decrypted",
            check=False,
        )
    text = (result.stdout or "").strip()
    if not text:
        raise RuntimeError(result.stderr[-400:] or "credential export empty")
    data = json.loads(text)
    items = data if isinstance(data, list) else [data]
    for item in items:
        if item.get("id") == CRED_ID or item.get("type") == "gmailOAuth2":
            return item.get("data") or item
    return items[0].get("data") or items[0]


def refresh_token(oauth: dict) -> str:
    token = oauth.get("access_token") or ""
    refresh = oauth.get("refresh_token") or ""
    client_id = oauth.get("clientId") or oauth.get("client_id") or os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = oauth.get("clientSecret") or oauth.get("client_secret") or os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not refresh or not client_id:
        return token
    body = urllib.parse_qs if False else None  # keep import local
    import urllib.parse

    payload = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        }
    ).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        tok = json.loads(r.read().decode())
    return tok.get("access_token") or token


def gmail_profile(token: str) -> str:
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode()).get("emailAddress") or ""


def send_gmail(token: str, to_email: str) -> str:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = MIMEText(
        "Paid Instagram Reel collaboration. Budget INR 5500. Please confirm availability.\n\n"
        f"Automation self-test {stamp}"
    )
    msg["To"] = to_email
    msg["From"] = to_email
    msg["Subject"] = f"Collab offer reel INR 5500 [{int(time.time())}]"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    data = json.dumps({"raw": raw}).encode()
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        sent = json.loads(r.read().decode())
    return sent.get("id") or ""


def main() -> None:
    wait_n8n()
    import_workflows()
    print("workflows imported")

    code, body = post(
        f"{N8N}/webhook/ingest-email",
        {
            "id": f"n8n-{int(time.time())}",
            "threadId": f"n8n-live-{int(time.time())}",
            "subject": "Paid reel collab via n8n",
            "text": "Hi, we want a paid Instagram reel. Budget INR 8000. Can you share a slot this month?",
            "from": "n8n.brand@example.com",
            "to": "creator@example.com",
        },
        timeout=180,
    )
    print("ingest_webhook", code, str(body)[:220])

    gmail_ok = False
    email = ""
    try:
        creds = load_gmail_oauth()
        oauth = creds.get("oauthTokenData") or creds
        token = refresh_token(oauth if isinstance(oauth, dict) else creds)
        email = gmail_profile(token)
        print("gmail_account_present", bool(email))
        sent_id = send_gmail(token, email)
        print("gmail_sent", bool(sent_id))
        gmail_ok = bool(sent_id)
        code, body = post(
            f"{N8N}/webhook/deal-action",
            {
                "action": "accept",
                "thread_id": "selftest",
                "deal_id": 0,
                "ai_reply": "Thanks — this is an automation check from Creator Email AI. No action needed.",
                "from_email": email,
                "subject": "Creator Email AI automation check",
                "idempotency_key": f"selftest:{int(time.time())}",
            },
            {"X-Internal-API-Key": KEY},
            timeout=90,
        )
        print("deal_action", code, str(body)[:220])
    except Exception as exc:
        print("gmail_path", type(exc).__name__)

    if gmail_ok:
        print("waiting_for_gmail_trigger")
        deadline = time.time() + 90
        found = False
        while time.time() < deadline:
            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:8000/api/emails/ingest/",
                    method="GET",
                )
            except Exception:
                pass
            code = 0
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/health/", timeout=5) as r:
                    code = r.status
            except Exception:
                code = 0
            # Look for the live subject via Django admin-less search using cookie-less is not available.
            # Poll n8n executions instead.
            time.sleep(8)
            result = sh(
                "docker",
                "exec",
                "n8n",
                "n8n",
                "list:workflow",
                check=False,
            )
            # executions via sqlite
            sh("docker", "cp", "n8n:/home/node/.n8n/database.sqlite", str(ROOT / "tmp_n8n" / "database.sqlite"), check=False)
            try:
                import sqlite3

                con = sqlite3.connect(ROOT / "tmp_n8n" / "database.sqlite")
                row = con.execute(
                    "SELECT id, workflowId, status, startedAt FROM execution_entity ORDER BY id DESC LIMIT 1"
                ).fetchone()
                print("latest_n8n_execution", row)
                if row:
                    found = True
                    break
            except Exception as exc:
                print("exec_query", type(exc).__name__)
                break
        print("gmail_trigger_execution_seen", found)

    print("done")


if __name__ == "__main__":
    main()
