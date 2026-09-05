import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def get(url, timeout=8):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except Exception as exc:
        return None, str(exc)


def post(url, payload, headers=None, timeout=90):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = body[:400]
            return r.status, parsed
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:400]
    except Exception as exc:
        return None, str(exc)


def main():
    time.sleep(2)
    st, health = get("http://127.0.0.1:5000/health")
    print("flask", st)
    if isinstance(health, dict):
        prov = health.get("providers") or {}
        for name in ("ollama", "mistral", "groq", "cerebras", "openrouter"):
            item = prov.get(name) or {}
            print(name, "configured", item.get("configured"), "available", item.get("available"))

    st, n8n = get("http://127.0.0.1:5678/healthz")
    print("n8n", st, n8n)
    st, dj = get("http://127.0.0.1:8000/health/")
    print("django", st, dj)

    key = os.environ.get("INTERNAL_API_KEY", "")
    st, ingest = post(
        "http://127.0.0.1:8000/api/emails/ingest/",
        {
            "thread_id": "n8n-live-collab-1",
            "gmail_message_id": "n8n-live-collab-1-m0",
            "subject": "Paid reel collaboration",
            "body": "Hi, we want a paid Instagram Reel collaboration. Budget is 3500 INR. Can we work together this month?",
            "from_email": "brand.live@example.com",
            "to_email": "creator@example.com",
        },
        {"X-Internal-API-Key": key},
        timeout=120,
    )
    print("ingest", st)
    if isinstance(ingest, dict):
        print("decision", ingest.get("ai_decision"), "provider_fields", ingest.get("deal_status"), "send", ingest.get("send_reply"))

    st, hook = post(
        "http://127.0.0.1:5678/webhook/ingest-email",
        {
            "id": "wh-test-1",
            "threadId": "n8n-webhook-thread-1",
            "subject": "Sponsorship for one reel",
            "text": "Hello, we would like to sponsor one reel. Budget 8000.",
            "from": "sponsor@example.com",
            "to": "creator@example.com",
        },
        timeout=30,
    )
    print("n8n webhook", st, str(hook)[:300])


if __name__ == "__main__":
    main()
