import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
KEY = (dotenv_values(ROOT / ".env").get("INTERNAL_API_KEY") or "")


def post(url, payload, headers=None, timeout=180):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", **(headers or {})}
    )
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


def main():
    tid = f"n8n-wh-{int(time.time())}"
    st, hook = post(
        "http://127.0.0.1:5678/webhook/ingest-email",
        {
            "id": f"wh-{int(time.time())}",
            "threadId": tid,
            "subject": "Sponsorship for one reel",
            "text": "Hello, we would like to sponsor one reel. Budget 8000 INR.",
            "from": "sponsor@example.com",
            "to": "creator@example.com",
        },
        timeout=180,
    )
    print("webhook", st)
    if isinstance(hook, dict):
        print(
            "decision",
            hook.get("ai_decision"),
            "status",
            hook.get("deal_status"),
            "send",
            hook.get("send_reply"),
            "deal",
            hook.get("deal_id"),
        )
    else:
        print(str(hook)[:400])

    st, action = post(
        "http://127.0.0.1:5678/webhook/deal-action",
        {
            "action": "accept",
            "thread_id": tid,
            "deal_id": hook.get("deal_id") if isinstance(hook, dict) else 0,
            "ai_reply": "Thanks, we will proceed on this reel.",
            "from_email": "sponsor@example.com",
            "subject": "Re: Sponsorship for one reel",
            "idempotency_key": f"action-{int(time.time())}",
        },
        {"X-Internal-API-Key": KEY},
        timeout=60,
    )
    print("deal_action", st, str(action)[:300])


if __name__ == "__main__":
    main()
