"""Send one Gmail using n8n's stored OAuth. Never prints tokens or the JSON file."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
TMP = ROOT / "tmp_n8n"
TMP.mkdir(exist_ok=True)
DEST = TMP / "gc.json"


def send() -> tuple[str, str]:
    subprocess.check_call(["docker", "cp", "n8n:/tmp/gc.json", str(DEST)])
    raw = json.loads(DEST.read_text(encoding="utf-8"))
    DEST.unlink(missing_ok=True)
    subprocess.run(["docker", "exec", "n8n", "rm", "-f", "/tmp/gc.json"], check=False)
    item = raw[0] if isinstance(raw, list) else raw
    data = item.get("data") or item
    oauth = data.get("oauthTokenData") or data
    refresh = oauth.get("refresh_token") or ""
    client_id = data.get("clientId") or os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = data.get("clientSecret") or os.environ.get("GOOGLE_CLIENT_SECRET", "")
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
        token = json.loads(r.read().decode())["access_token"]
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        email = json.loads(r.read().decode())["emailAddress"]
    stamp = int(time.time())
    subject = f"Peak Athletics paid reel collab INR 5500 [{stamp}]"
    msg = MIMEText(
        "Hi, this is Ravi from Peak Athletics.\n\n"
        "We want a paid Instagram Reel collaboration. Budget INR 5500. "
        "Please confirm if you can shoot this month.\n\n"
        "Thanks,\nRavi\nPeak Athletics"
    )
    msg["To"] = email
    msg["From"] = f"Peak Athletics <{email}>"
    msg["Subject"] = subject
    raw_b64 = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=json.dumps({"raw": raw_b64}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        sent = json.loads(r.read().decode())
    mid = sent.get("id") or ""
    if mid:
        req = urllib.request.Request(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}/modify",
            data=json.dumps({"addLabelIds": ["UNREAD", "INBOX"]}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=20).read()
        except Exception:
            pass
    return email, subject, mid, sent.get("threadId") or ""


if __name__ == "__main__":
    email, subject, mid, tid = send()
    (ROOT / "tmp_n8n" / "gmail_address.txt").write_text(email, encoding="utf-8")
    (ROOT / "tmp_n8n" / "gmail_subject.txt").write_text(subject, encoding="utf-8")
    print("gmail_sent", bool(mid), "thread_present", bool(tid), "subject_token", subject.split("[")[-1])
