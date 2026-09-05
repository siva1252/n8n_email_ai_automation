"""Single command to know whether the stack is actually working.

Covers:
  1. Flask, Django, n8n health
  2. Unit tests (pytest)
  3. Dashboard login + demo mailboxes (inbox / spam / human queue)
  4. Inbound test mails landing in the dashboard
  5. Dashboard Accept and Reject, including outgoing closing mail
  6. n8n incoming-email and deal-action automations

Usage (from repo root, stack already running):

    python scripts/verify_everything.py
    python scripts/verify_everything.py --gmail

Exit code 0 means required checks passed. --gmail also waits for a real
Gmail trigger; that check is skipped unless you pass the flag.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
ENV = dotenv_values(ROOT / ".env")
KEY = ENV.get("INTERNAL_API_KEY") or os.environ.get("INTERNAL_API_KEY") or ""
ADMIN_USER = ENV.get("DJANGO_ADMIN_USER") or "admin"
ADMIN_PASSWORD = ENV.get("DJANGO_ADMIN_PASSWORD") or "DemoAdmin123!"
DJANGO = "http://127.0.0.1:8000"
FLASK = "http://127.0.0.1:5000"
N8N = "http://127.0.0.1:5678"


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        self.rows.append((status, name, detail[:240]))
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail[:240]}" if detail else ""))

    def skip(self, name: str, detail: str = "") -> None:
        self.rows.append(("SKIP", name, detail[:240]))
        print(f"[SKIP] {name}" + (f" — {detail[:240]}" if detail else ""))

    def failed(self) -> bool:
        return any(status == "FAIL" for status, _, _ in self.rows)

    def summary(self) -> int:
        counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
        for status, _, _ in self.rows:
            counts[status] += 1
        print()
        print(
            f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped"
        )
        if counts["FAIL"]:
            print("OVERALL: NOT WORKING")
            return 1
        print("OVERALL: WORKING")
        return 0


def get_json(url: str, timeout: int = 8):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = r.read().decode()
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except Exception as exc:
        return None, str(exc)


def post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 180):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = body[:400]
            return r.status, parsed
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:400]
    except Exception as exc:
        return None, str(exc)


def csrf_token(html: str) -> str:
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    return match.group(1) if match else ""


class Dashboard:
    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def login(self) -> str:
        page = self.opener.open(f"{DJANGO}/login/", timeout=10).read().decode()
        token = csrf_token(page)
        data = urllib.parse.urlencode(
            {
                "username": ADMIN_USER,
                "password": ADMIN_PASSWORD,
                "csrfmiddlewaretoken": token,
            }
        ).encode()
        req = urllib.request.Request(
            f"{DJANGO}/login/",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": f"{DJANGO}/login/",
            },
        )
        return self.opener.open(req, timeout=10).read().decode()

    def get(self, path: str) -> str:
        return self.opener.open(f"{DJANGO}{path}", timeout=15).read().decode()

    def post_form(self, path: str, fields: dict, referer: str) -> str:
        html = self.get(referer)
        fields = {"csrfmiddlewaretoken": csrf_token(html), **fields}
        data = urllib.parse.urlencode(fields).encode()
        req = urllib.request.Request(
            f"{DJANGO}{path}",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": f"{DJANGO}{referer}",
            },
        )
        return self.opener.open(req, timeout=120).read().decode()


def ingest(thread_id: str, subject: str, body: str, from_email: str, skip_ai: bool = True):
    payload = {
        "thread_id": thread_id,
        "gmail_message_id": f"{thread_id}-m0",
        "subject": subject,
        "body": body,
        "from_email": from_email,
        "to_email": "creator@demo.local",
        "skip_ai": skip_ai,
    }
    return post_json(
        f"{DJANGO}/api/emails/ingest/",
        payload,
        {"X-Internal-API-Key": KEY},
        timeout=180,
    )


def run_pytest() -> tuple[bool, str]:
    env = os.environ.copy()
    env["AI_MOCK"] = "true"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    summary = lines[-1] if lines else ((proc.stderr or "")[-200:].replace("\n", " "))
    return proc.returncode == 0, summary


def check_health(report: Report) -> None:
    st, body = get_json(f"{FLASK}/health")
    detail = str(body)[:160]
    if isinstance(body, dict):
        ollama = body.get("ollama") or (body.get("providers") or {}).get("ollama") or {}
        detail = f"status={body.get('status')} mock={body.get('mock')} ollama={ollama.get('available')}"
    report.add("flask health", st == 200, detail)

    st, body = get_json(f"{DJANGO}/health/")
    report.add("django health", st == 200, str(body)[:160])

    st, body = get_json(f"{N8N}/healthz")
    report.add("n8n health", st == 200, str(body)[:120])

    st, body = post_json(
        f"{DJANGO}/api/emails/ingest/",
        {"thread_id": "no-key"},
        timeout=10,
    )
    report.add("ingest without API key is 401", st == 401, str(st))


def check_demo_pages(dash: Dashboard, report: Report) -> None:
    html = dash.login()
    report.add("dashboard login", "Creator Email AI" in html and "Invalid username" not in html)

    dashboard = dash.get("/dashboard/")
    inbox = dash.get("/inbox/?q=northline")
    spam = dash.get("/spam/")
    human = dash.get("/human-queue/")
    done = dash.get("/completed/")
    report.add("inbox/dashboard show demo collab mail", "northline" in inbox.lower())
    report.add("spam mailbox has phishing demo", "prize" in spam.lower() or "crypto" in spam.lower())
    report.add("human queue has call-request demo", "harbor" in human.lower())
    report.add(
        "dashboard nav has inbox/spam/done",
        all(x in dashboard for x in ("Inbox", "Spam", "Done", "Needs a call")),
    )
    report.add("completed page loads", "Completed" in done or "records" in done)


def check_dashboard_accept_reject(dash: Dashboard, report: Report) -> tuple[int | None, int | None]:
    stamp = int(time.time())
    accept_subject = f"E2E Accept Peak Reel [{stamp}]"
    reject_subject = f"E2E Reject Glowbar Promo [{stamp}]"
    accept_tid = f"e2e-accept-{stamp}"
    reject_tid = f"e2e-reject-{stamp}"

    st, body = ingest(
        accept_tid,
        accept_subject,
        "Hi, Peak Athletics wants a paid Instagram Reel. Budget INR 8000. Can we lock this month?",
        f"e2e.accept.{stamp}@brand.example",
        skip_ai=True,
    )
    accept_id = body.get("deal_id") if isinstance(body, dict) else None
    report.add("inbound accept-mail ingested", st == 201 and bool(accept_id), str(body)[:180])

    st, body = ingest(
        reject_tid,
        reject_subject,
        "Hi, Glowbar wants a story shoutout. Budget INR 2000.",
        f"e2e.reject.{stamp}@brand.example",
        skip_ai=True,
    )
    reject_id = body.get("deal_id") if isinstance(body, dict) else None
    report.add("inbound reject-mail ingested", st == 201 and bool(reject_id), str(body)[:180])

    inbox = dash.get(f"/inbox/?q={urllib.parse.quote(str(stamp))}")
    report.add("accept mail visible in inbox", accept_subject in inbox)
    report.add("reject mail visible in inbox", reject_subject in inbox)
    recent = dash.get("/dashboard/")
    report.add(
        "new mails visible on dashboard",
        accept_subject in recent or reject_subject in recent,
        "recent table is last 8 deals",
    )

    if accept_id:
        detail = dash.get(f"/deal/{accept_id}/")
        report.add("accept deal page has Accept/Reject", "Accept deal" in detail and "Reject deal" in detail)
        after = dash.post_form(
            f"/deal/{accept_id}/accept/",
            {},
            f"/deal/{accept_id}/",
        )
        report.add("dashboard accept flash", "Deal accepted" in after)
        report.add("accepted deal shows outgoing mail", "closing" in after.lower() or "You" in after)
        report.add("accepted deal is Completed", "Completed" in after and "Accept deal" not in after)
        done = dash.get("/completed/")
        report.add("accepted deal on Done page", accept_subject in done)
    else:
        report.add("dashboard accept", False, "no deal_id")

    if reject_id:
        after = dash.post_form(
            f"/deal/{reject_id}/reject/",
            {"reason": "E2E reject: dates do not work"},
            f"/deal/{reject_id}/",
        )
        report.add("dashboard reject flash", "Deal rejected" in after)
        report.add("rejected deal is Rejected", "Rejected" in after and "Accept deal" not in after)
        done = dash.get("/completed/")
        report.add("rejected deal on Done page", reject_subject in done)
    else:
        report.add("dashboard reject", False, "no deal_id")

    return accept_id, reject_id


def n8n_exec_snapshot():
    dest_dir = ROOT / "tmp_n8n"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / "database.sqlite"
    for name in ("database.sqlite", "database.sqlite-wal", "database.sqlite-shm"):
        subprocess.run(
            ["docker", "cp", f"n8n:/home/node/.n8n/{name}", str(dest_dir / name)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    if not dest.exists():
        return [], "n8n sqlite copy missing"
    try:
        import sqlite3

        con = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT id, workflowId, status, mode FROM execution_entity ORDER BY id DESC LIMIT 20"
        ).fetchall()
        con.close()
        return rows, ""
    except Exception as exc:
        return [], str(exc)


def n8n_ingest(thread_id: str, subject: str, body: str, from_email: str, message_id: str, skip_ai: bool = False):
    payload = {
        "id": message_id,
        "threadId": thread_id,
        "subject": subject,
        "text": body,
        "from": from_email,
        "to": "creator@example.com",
        "skip_ai": skip_ai,
    }
    return post_json(f"{N8N}/webhook/ingest-email", payload, timeout=180)


def check_n8n_automations(dash: Dashboard, report: Report) -> None:
    before, snap_err = n8n_exec_snapshot()
    before_ids = {row[0] for row in before}
    report.add("n8n workflow db readable", not snap_err, snap_err or f"latest_id={before[0][0] if before else 0}")

    stamp = str(int(time.time()))
    accept_tid = f"n8n-accept-{stamp}"
    reject_tid = f"n8n-reject-{stamp}"
    accept_subject = f"n8n fake mail ACCEPT reel INR 8000 [{stamp}]"
    reject_subject = f"n8n fake mail REJECT reel INR 8000 [{stamp}]"
    accept_body = (
        "Hi, this is Maya from Northline Labs. We want a paid Instagram Reel collaboration. "
        "Budget is INR 8000. Can we lock a date this month?"
    )
    reject_body = (
        "Hi, this is Rohan from Glowbar Studio. We want a paid Instagram Reel. "
        "Budget is INR 8000. Please confirm if you can shoot next week."
    )
    accept_from = f"maya.n8n.{stamp}@northline.example"
    reject_from = f"rohan.n8n.{stamp}@glowbar.example"

    st, body = n8n_ingest(accept_tid, accept_subject, accept_body, accept_from, f"wh-accept-{stamp}", skip_ai=True)
    accept_id = body.get("deal_id") if isinstance(body, dict) else None
    report.add(
        "n8n fake accept-mail ingested",
        st in {200, 201} and bool(accept_id),
        str(body)[:200] if not isinstance(body, dict) else f"deal={accept_id} status={body.get('deal_status')} decision={body.get('ai_decision')}",
    )

    st, body = n8n_ingest(reject_tid, reject_subject, reject_body, reject_from, f"wh-reject-{stamp}", skip_ai=True)
    reject_id = body.get("deal_id") if isinstance(body, dict) else None
    report.add(
        "n8n fake reject-mail ingested",
        st in {200, 201} and bool(reject_id),
        str(body)[:200] if not isinstance(body, dict) else f"deal={reject_id} status={body.get('deal_status')} decision={body.get('ai_decision')}",
    )

    follow_body = "Following up on the same thread — still happy at INR 8000 if you can confirm."
    st, body = n8n_ingest(
        accept_tid,
        f"Re: {accept_subject}",
        follow_body,
        accept_from,
        f"wh-accept-follow-{stamp}",
        skip_ai=True,
    )
    same_deal = isinstance(body, dict) and body.get("deal_id") == accept_id
    report.add("n8n follow-up stays on same deal/conversation", bool(same_deal), str(body)[:180])

    ai_subject = f"n8n live AI collab INR 8000 [{stamp}]"
    st, body = n8n_ingest(
        f"n8n-ai-{stamp}",
        ai_subject,
        "Hi, we want a paid Instagram Reel collaboration. Budget INR 8000. Can you share a slot this month?",
        f"ai.n8n.{stamp}@brand.example",
        f"wh-ai-{stamp}",
        skip_ai=False,
    )
    report.add(
        "n8n live AI pipeline ingested a fake mail",
        st in {200, 201} and isinstance(body, dict) and bool(body.get("deal_id")),
        str(body)[:200] if not isinstance(body, dict) else f"deal={body.get('deal_id')} status={body.get('deal_status')} decision={body.get('ai_decision')}",
    )
    if isinstance(body, dict) and body.get("deal_id"):
        inbox = dash.get(f"/inbox/?q={urllib.parse.quote(ai_subject)}")
        report.add("n8n AI mail visible in dashboard inbox", ai_subject in inbox or str(body.get("deal_id")) in inbox)

    if accept_id:
        inbox = dash.get(f"/inbox/?q={urllib.parse.quote(accept_subject)}")
        report.add("n8n accept-mail visible in inbox", accept_subject in inbox)
        convo = dash.get(f"/deal/{accept_id}/")
        report.add(
            "dashboard conversation shows inbound n8n mail",
            "Northline Labs" in convo and "INR 8000" in convo,
        )
        report.add(
            "dashboard conversation shows follow-up",
            "Following up on the same thread" in convo,
        )
        report.add("n8n accept deal has Accept/Reject buttons", "Accept deal" in convo and "Reject deal" in convo)
        after = dash.post_form(f"/deal/{accept_id}/accept/", {}, f"/deal/{accept_id}/")
        report.add("dashboard accept of n8n deal", "Deal accepted" in after)
        report.add("n8n accepted deal is Completed", "Completed" in after and "Accept deal" not in after)
        report.add("n8n accepted deal has outgoing closing mail", "You" in after)
        done = dash.get("/completed/")
        report.add("n8n accepted deal on Done page", accept_subject in done)
    else:
        report.add("n8n accept deal dashboard flow", False, "no deal_id")

    if reject_id:
        inbox = dash.get(f"/inbox/?q={urllib.parse.quote(reject_subject)}")
        report.add("n8n reject-mail visible in inbox", reject_subject in inbox)
        convo = dash.get(f"/deal/{reject_id}/")
        report.add("dashboard conversation shows reject inbound mail", "Glowbar Studio" in convo)
        after = dash.post_form(
            f"/deal/{reject_id}/reject/",
            {"reason": "E2E n8n reject: dates do not work"},
            f"/deal/{reject_id}/",
        )
        report.add("dashboard reject of n8n deal", "Deal rejected" in after)
        report.add("n8n rejected deal is Rejected", "Rejected" in after and "Accept deal" not in after)
        done = dash.get("/completed/")
        report.add("n8n rejected deal on Done page", reject_subject in done)
    else:
        report.add("n8n reject deal dashboard flow", False, "no deal_id")

    unauth_st, unauth_body = post_json(
        f"{N8N}/webhook/deal-action",
        {"action": "accept", "deal_id": 0, "thread_id": "nope"},
        timeout=30,
    )
    report.add(
        "n8n deal-action rejects missing API key",
        unauth_st == 401 or (isinstance(unauth_body, dict) and unauth_body.get("ok") is False),
        f"{unauth_st} {str(unauth_body)[:120]}",
    )

    after_rows, after_err = n8n_exec_snapshot()
    new_rows = [row for row in after_rows if row[0] not in before_ids]
    incoming_ok = [row for row in new_rows if row[1] == "incoming-email-pipeline" and row[2] == "success"]
    action_ok = [row for row in new_rows if row[1] == "deal-action-webhook" and row[2] == "success"]
    action_err = [row for row in new_rows if row[1] == "deal-action-webhook" and row[2] == "error"]
    report.add(
        "n8n incoming-email executions succeeded",
        len(incoming_ok) >= 2,
        after_err or f"success={len(incoming_ok)} new={len(new_rows)}",
    )
    report.add(
        "n8n deal-action executions succeeded after accept/reject",
        len(action_ok) >= 1 and len(action_err) == 0,
        f"success={len(action_ok)} error={len(action_err)}",
    )


def check_live_gmail(report: Report) -> None:
    send_script = ROOT / "scripts" / "send_gmail_now.py"
    if not send_script.exists():
        report.skip("live Gmail send+trigger", "send_gmail_now.py missing")
        return
    try:
        proc = subprocess.run(
            [sys.executable, str(send_script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as exc:
        report.skip("live Gmail send+trigger", f"could not start Gmail send: {exc}")
        return
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        report.skip(
            "live Gmail send+trigger",
            "Gmail OAuth is not exported in the n8n container. Connect Gmail in n8n, then re-run with --gmail.",
        )
        return
    report.add(
        "live Gmail send",
        "gmail_sent True" in output or "gmail_sent" in output,
        output[:180],
    )
    subject_file = ROOT / "tmp_n8n" / "gmail_subject.txt"
    if not subject_file.exists():
        report.add("live Gmail appeared in Django", False, "no subject file")
        return
    token = subject_file.read_text(encoding="utf-8").strip()
    deadline = time.time() + 95
    found = False
    last = ""
    while time.time() < deadline:
        st, body = get_json(f"{DJANGO}/health/")
        _ = st, body
        try:
            import sqlite3

            db = ROOT / "backend" / "db.sqlite3"
            if db.exists():
                con = sqlite3.connect(db)
                rows = con.execute(
                    "SELECT id, subject, status FROM deals_deal WHERE subject LIKE ? ORDER BY id DESC LIMIT 3",
                    (f"%{token}%",),
                ).fetchall()
                con.close()
                if rows:
                    found = True
                    last = str(rows[0])
                    break
        except Exception as exc:
            last = str(exc)
        time.sleep(8)
    report.add("live Gmail appeared in Django", found, last or f"waited for {token}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prove whether automations, mail, and dashboard accept/reject work.")
    parser.add_argument("--gmail", action="store_true", help="Also send a real Gmail and wait for n8n trigger")
    parser.add_argument("--skip-unit", action="store_true", help="Skip pytest (live stack only)")
    args = parser.parse_args()
    report = Report()

    print("=== 1. Service health ===")
    check_health(report)

    if not args.skip_unit:
        print("\n=== 2. Unit tests ===")
        ok, tail = run_pytest()
        report.add("pytest (AI_MOCK)", ok, tail)
    else:
        report.skip("pytest (AI_MOCK)", "--skip-unit")

    print("\n=== 3. Dashboard mailboxes ===")
    dash = Dashboard()
    try:
        check_demo_pages(dash, report)
    except Exception as exc:
        report.add("dashboard login", False, str(exc))
        print()
        return report.summary()

    print("\n=== 4. Dashboard accept + reject ===")
    check_dashboard_accept_reject(dash, report)

    print("\n=== 5. n8n automations ===")
    check_n8n_automations(dash, report)

    print("\n=== 6. Live Gmail (optional) ===")
    if args.gmail:
        check_live_gmail(report)
    else:
        report.skip("live Gmail send+trigger", "pass --gmail to include real mailbox")

    print()
    return report.summary()


if __name__ == "__main__":
    sys.exit(main())
