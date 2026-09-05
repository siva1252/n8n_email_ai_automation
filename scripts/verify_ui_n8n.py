import json
import os
import time
import urllib.request
import urllib.parse
from http.cookiejar import CookieJar
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
env = dotenv_values(ROOT / ".env")
KEY = env.get("INTERNAL_API_KEY") or ""


def post(url, payload, headers=None, timeout=180):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def main():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    login_page = opener.open("http://127.0.0.1:8000/login/").read().decode()
    csrf = ""
    if 'name="csrfmiddlewaretoken"' in login_page:
        csrf = login_page.split('name="csrfmiddlewaretoken" value="')[1].split('"')[0]
    data = urllib.parse.urlencode(
        {"username": "admin", "password": "DemoAdmin123!", "csrfmiddlewaretoken": csrf}
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/login/",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": "http://127.0.0.1:8000/login/"},
    )
    dash = opener.open(req).read().decode()
    print("dash_full_width", "w-full px-6" in dash, "narrow", "max-w-7xl" in dash)
    print("dash_labels", "Needs you" in dash or "Waiting" in dash)

    deal_html = opener.open("http://127.0.0.1:8000/deal/11/").read().decode()
    print("save_draft", "Save draft" in deal_html)
    print("policy_used", "Policy used" in deal_html)
    print("neg_history", "Negotiation history" in deal_html)
    print("notes", ">Notes<" in deal_html or "Save note" in deal_html)
    print("accept", "Accept deal" in deal_html)
    print("creator_policy", "creator_policy.md" in deal_html)

    csrf2 = ""
    if 'name="csrfmiddlewaretoken"' in deal_html:
        csrf2 = deal_html.split('name="csrfmiddlewaretoken" value="')[1].split('"')[0]
    note_body = urllib.parse.urlencode(
        {"csrfmiddlewaretoken": csrf2, "action": "note", "notes": "Live UI note check"}
    ).encode()
    note_req = urllib.request.Request(
        "http://127.0.0.1:8000/deal/11/human-action/",
        data=note_body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": "http://127.0.0.1:8000/deal/11/"},
    )
    after_note = opener.open(note_req).read().decode()
    print("note_saved", "Live UI note check" in after_note)

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
    print("n8n_webhook_status", st)
    if isinstance(hook, dict):
        print(
            "n8n_decision",
            hook.get("ai_decision"),
            "n8n_status",
            hook.get("deal_status"),
            "n8n_send",
            hook.get("send_reply"),
            "n8n_deal",
            hook.get("deal_id"),
        )
    else:
        print("n8n_webhook_body", str(hook)[:300])

    st, action = post(
        "http://127.0.0.1:5678/webhook/deal-action",
        {
            "action": "accept",
            "thread_id": "ai-ok-demo-action",
            "deal_id": 11,
            "ai_reply": "Thanks, we will proceed on this reel.",
            "from_email": "brand.live@example.com",
            "subject": "Re: Paid reel collaboration",
            "idempotency_key": f"ui-action-{int(time.time())}",
        },
        {"X-Internal-API-Key": KEY},
        timeout=60,
    )
    print("deal_action_status", st, str(action)[:250])


if __name__ == "__main__":
    main()
