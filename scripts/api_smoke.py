import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
KEY = os.environ["INTERNAL_API_KEY"]


def post(url, payload, headers=None, timeout=90):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            print(r.status, url, r.read().decode()[:500])
    except Exception as exc:
        print("FAIL", url, exc)


post(
    "http://127.0.0.1:8000/api/emails/ingest/",
    {"thread_id": "x", "body": "hi", "from_email": "a@b.com", "to_email": "c@d.com", "subject": "s"},
)
post(
    "http://127.0.0.1:8000/api/emails/ingest/",
    {
        "thread_id": "live-skip-1",
        "gmail_message_id": "live-skip-1-m0",
        "subject": "Skip AI persist test",
        "body": "persisted without calling the model",
        "from_email": "qa@demo.local",
        "to_email": "creator@demo.local",
        "skip_ai": True,
    },
    {"X-Internal-API-Key": KEY},
    timeout=20,
)
post(
    "http://127.0.0.1:5000/classify_email",
    {"body": "Hi Siva, we need to talk with you for a business collaboration on a paid reel."},
    timeout=90,
)
