"""Verify n8n webhooks and that the Gmail self-test landed in Django."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
KEY = os.environ.get("INTERNAL_API_KEY", "")
TOKEN = (ROOT / "tmp_n8n" / "gmail_subject.txt").read_text(encoding="utf-8").strip() if (ROOT / "tmp_n8n" / "gmail_subject.txt").exists() else "1788629084"
GMAIL = (ROOT / "tmp_n8n" / "gmail_address.txt").read_text(encoding="utf-8").strip() if (ROOT / "tmp_n8n" / "gmail_address.txt").exists() else "n8n.brand@example.com"
DB = ROOT / "backend" / "db.sqlite3"


def post(url, payload, headers=None, timeout=180):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            return r.status, json.loads(body) if body.startswith("{") else body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:400]


def deals_matching(needle: str):
    if not DB.exists():
        return []
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT id, subject, status, thread_id FROM deals_deal WHERE subject LIKE ? ORDER BY id DESC LIMIT 5",
        (f"%{needle}%",),
    ).fetchall()
    return rows


code, body = post(
    "http://127.0.0.1:5678/webhook/ingest-email",
    {
        "id": f"n8n-{int(time.time())}",
        "threadId": f"n8n-live-{int(time.time())}",
        "subject": "Paid reel collab via n8n webhook",
        "text": "Hi, we want a paid Instagram reel. Budget INR 8000. Can you share a slot this month?",
        "from": "n8n.brand@example.com",
        "to": "creator@example.com",
    },
)
print("ingest_webhook", code, str(body)[:240])

# deal-action: send closing mail to a throwaway path is skipped if we lack address;
# Accept path is covered by Django notify. Probe webhook auth + Gmail node.
code, body = post(
    "http://127.0.0.1:5678/webhook/deal-action",
    {
        "action": "accept",
        "thread_id": "selftest",
        "deal_id": 0,
        "ai_reply": "Thanks — automation check from Creator Email AI. No action needed.",
        "from_email": GMAIL,
        "subject": "Creator Email AI automation check",
        "idempotency_key": f"selftest:{int(time.time())}",
    },
    {"X-Internal-API-Key": KEY},
    timeout=90,
)
print("deal_action", code, str(body)[:240])

print("gmail_subject_now", deals_matching(TOKEN))
print("waiting_up_to_90s_for_gmail_trigger")
deadline = time.time() + 95
found = []
while time.time() < deadline:
    found = deals_matching(TOKEN)
    if found:
        break
    time.sleep(8)
print("gmail_deal", found)
print("webhook_deal", deals_matching("n8n webhook"))
