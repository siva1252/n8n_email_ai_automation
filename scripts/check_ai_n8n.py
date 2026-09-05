import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
KEY = os.environ.get("INTERNAL_API_KEY", "")


def get(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        raw = r.read().decode()
        try:
            return r.status, json.loads(raw)
        except json.JSONDecodeError:
            return r.status, raw


def post(url, payload, headers=None, timeout=45):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            return r.status, json.loads(body) if body.startswith("{") else body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:400]


def main():
    st, health = None, None
    code, body = get("http://127.0.0.1:5000/health")
    print("flask", code, body)
    code, body = get("http://127.0.0.1:8000/health/")
    print("django", code, body)
    try:
        code, body = get("http://127.0.0.1:5678/healthz")
        print("n8n", code, body)
    except Exception as exc:
        print("n8n down", exc)

    code, body = post(
        "http://127.0.0.1:5000/classify_email",
        {"body": "Hi, we want a paid Instagram reel collaboration for our brand launch. Budget 5000."},
        timeout=40,
    )
    print("classify", code, str(body)[:400])

    code, body = post(
        "http://127.0.0.1:8000/api/emails/ingest/",
        {
            "thread_id": "live-ai-check-1",
            "gmail_message_id": f"live-ai-check-{int(time.time())}",
            "subject": "Paid reel collab",
            "body": "Hi, we want a paid Instagram reel collaboration. Budget INR 3500.",
            "from_email": "brand.check@example.com",
            "to_email": "creator@example.com",
        },
        {"X-Internal-API-Key": KEY},
        timeout=90,
    )
    print("ingest", code, str(body)[:500])

    code, body = post(
        "http://127.0.0.1:5678/webhook/ingest-email",
        {
            "id": f"n8n-{int(time.time())}",
            "threadId": "n8n-live-thread-1",
            "subject": "n8n pipeline collab",
            "text": "We would like to collaborate on a paid reel. Budget 8000.",
            "from": "n8n.brand@example.com",
            "to": "creator@example.com",
        },
        timeout=120,
    )
    print("n8n webhook", code, str(body)[:500])


if __name__ == "__main__":
    main()
