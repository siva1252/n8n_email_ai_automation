import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
env = dotenv_values(ROOT / ".env")
KEY = env.get("INTERNAL_API_KEY") or ""


def get(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def post(url, payload, headers=None, timeout=180):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:500]


def main():
    st, health = get("http://127.0.0.1:5000/health")
    prov = (health or {}).get("providers") or {}
    print("flask", st, "ollama", prov.get("ollama"), "mistral", prov.get("mistral"))
    st, dj = get("http://127.0.0.1:8000/health/")
    print("django", st, dj)
    st, n8n = get("http://127.0.0.1:5678/healthz")
    print("n8n", st, n8n)

    body = {
        "subject": "Paid reel collaboration",
        "body": "Hi, we want a paid Instagram Reel. Budget is 3500 INR. Can we lock this month?",
        "from_email": "brand.live@example.com",
        "correlation_id": "direct-pipe",
    }
    st, pipe = post("http://127.0.0.1:5000/ai/pipeline", body, timeout=180)
    print("pipeline", st)
    if isinstance(pipe, dict):
        for key in ("spam", "intent", "extract", "negotiation"):
            item = pipe.get(key) or {}
            print(
                key,
                "decision/intent",
                item.get("decision") or item.get("intent"),
                "provider",
                item.get("provider"),
                "model",
                item.get("model"),
                "facts",
                (item.get("facts_used") or [])[:3],
            )

    tid = f"ai-ok-{int(time.time())}"
    st, ingest = post(
        "http://127.0.0.1:8000/api/emails/ingest/",
        {
            "thread_id": tid,
            "gmail_message_id": f"{tid}-m0",
            "subject": "Paid reel collaboration",
            "body": body["body"],
            "from_email": "brand.live@example.com",
            "to_email": "creator@example.com",
        },
        {"X-Internal-API-Key": KEY},
        timeout=180,
    )
    print("ingest", st)
    if isinstance(ingest, dict):
        print(
            "decision",
            ingest.get("ai_decision"),
            "status",
            ingest.get("deal_status"),
            "send",
            ingest.get("send_reply"),
            "deal",
            ingest.get("deal_id"),
        )
        print("reply", (ingest.get("ai_reply") or "")[:180])

    st, hook = post(
        "http://127.0.0.1:5678/webhook/ingest-email",
        {
            "id": f"wh-{int(time.time())}",
            "threadId": f"n8n-wh-{int(time.time())}",
            "subject": "Sponsorship for one reel",
            "text": "Hello, we would like to sponsor one reel. Budget 8000 INR.",
            "from": "sponsor@example.com",
            "to": "creator@example.com",
        },
        timeout=180,
    )
    print("n8n webhook", st, str(hook)[:400])

    dash = urllib.request.urlopen("http://127.0.0.1:8000/login/", timeout=8).read().decode()
    print("login_full_width", "w-full px-6" in dash, "narrow_max", "max-w-7xl" in dash)


if __name__ == "__main__":
    main()
