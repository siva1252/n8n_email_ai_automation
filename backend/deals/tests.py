import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client as TestClient, RequestFactory, TestCase, override_settings

from deals.gmail_parser import html_to_text, normalize_gmail_payload
from deals.models import Client, Deal, EmailMessage, HumanAction
from deals.pipeline import ingest_email


def fake_pipeline(path, payload, timeout=90):
    body = (payload.get("body") or "").lower()
    if "verify your password" in body or "crypto giveaway" in body:
        return {
            "spam": {
                "decision": "SPAM",
                "confidence": 0.95,
                "reason": "phishing",
                "provider": "mock",
                "model": "mock",
            }
        }
    if "call me" in body or "jump on a call" in body:
        extract = {
            "brand_name": "Harbor",
            "phone": "+91-90000-11111",
            "budget_offered": None,
            "human_contact_requested": True,
            "meeting_requested": True,
            "provider": "mock",
            "model": "mock",
        }
        return {
            "spam": {"decision": "NOT_SPAM", "confidence": 0.9, "provider": "mock", "model": "mock"},
            "intent": {"intent": "BUSINESS_INQUIRY", "confidence": 0.9, "provider": "mock"},
            "extract": extract,
            "negotiation": {
                "decision": "HUMAN_REQUIRED",
                "needs_human": True,
                "reply_body": "",
                "reason": "call requested",
                "provider": "policy",
                "model": "rules",
            },
        }
    budget = 3500 if "3500" in body else (8000 if "8000" in body else None)
    decision = "READY_TO_CLOSE" if budget and budget >= 5000 else ("NEED_INFORMATION" if budget is None else "NEGOTIATE")
    return {
        "spam": {"decision": "NOT_SPAM", "confidence": 0.9, "provider": "mock", "model": "mock"},
        "intent": {"intent": "COLLABORATION", "confidence": 0.9, "provider": "mock"},
        "extract": {
            "brand_name": "Northline",
            "phone": None,
            "budget_offered": budget,
            "human_contact_requested": False,
            "provider": "mock",
            "model": "mock",
        },
        "negotiation": {
            "decision": decision,
            "reply_body": "Thanks for reaching out.",
            "reply_subject": "Re: collab",
            "needs_human": False,
            "provider": "mock",
            "model": "mock",
            "facts_used": ["creator_policy.md"],
        },
    }


class GmailParserTests(TestCase):
    def test_html_and_plain(self):
        self.assertIn("Hello", html_to_text("<p>Hello<br>World</p>"))

    def test_headers_and_reply_to(self):
        data = normalize_gmail_payload(
            {
                "id": "m1",
                "threadId": "t1",
                "subject": "Hi",
                "textPlain": "plain body",
                "from": "Brand <brand@x.com>",
                "to": "me@y.com",
                "headers": [{"name": "Reply-To", "value": "other@x.com"}, {"name": "Subject", "value": "Hi"}],
                "attachments": [{"filename": "brief.pdf", "mimeType": "application/pdf"}],
            }
        )
        self.assertEqual(data["from_email"], "brand@x.com")
        self.assertEqual(data["reply_to"], "other@x.com")
        self.assertEqual(data["gmail_message_id"], "m1")
        self.assertTrue(data["attachments"])

    def test_missing_fields(self):
        data = normalize_gmail_payload({"thread_id": "t", "from_email": "a@b.com", "body": "x"})
        self.assertEqual(data["subject"], "(no subject)")


@override_settings(INTERNAL_API_KEY="test-key", FLASK_AI_URL="http://flask_ai:5000")
class PipelineTests(TestCase):
    def setUp(self):
        self.patcher = patch("deals.pipeline.flask_post", side_effect=fake_pipeline)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_same_thread_one_deal(self):
        first = ingest_email(
            {
                "thread_id": "thread-a",
                "gmail_message_id": "m-a1",
                "subject": "Collab",
                "body": "We want a collaboration",
                "from_email": "brand@test.com",
                "to_email": "creator@test.com",
            }
        )
        second = ingest_email(
            {
                "thread_id": "thread-a",
                "gmail_message_id": "m-a2",
                "subject": "Re: Collab",
                "body": "Following up on collaboration",
                "from_email": "brand@test.com",
                "to_email": "creator@test.com",
            }
        )
        self.assertEqual(Deal.objects.filter(thread_id="thread-a").count(), 1)
        self.assertEqual(first["deal_id"], second["deal_id"])
        self.assertEqual(EmailMessage.objects.filter(deal_id=first["deal_id"]).count(), 2)

    def test_idempotent_gmail_id(self):
        payload = {
            "thread_id": "thread-b",
            "gmail_message_id": "same-id",
            "subject": "Hi",
            "body": "collab please",
            "from_email": "brand@test.com",
            "to_email": "me@test.com",
        }
        ingest_email(payload)
        again = ingest_email(payload)
        self.assertEqual(again["status"], "duplicate")
        self.assertEqual(EmailMessage.objects.filter(gmail_message_id="same-id").count(), 1)

    def test_spam_not_from_ai_error(self):
        with patch("deals.pipeline.flask_post", side_effect=RuntimeError("down")):
            result = ingest_email(
                {
                    "thread_id": "thread-err",
                    "gmail_message_id": "m-err",
                    "subject": "Collab",
                    "body": "paid promotion",
                    "from_email": "brand@test.com",
                    "to_email": "me@test.com",
                }
            )
        deal = Deal.objects.get(thread_id="thread-err")
        self.assertEqual(deal.status, "REVIEW")
        self.assertNotEqual(deal.status, "SPAM")
        self.assertEqual(result["ai_decision"], "HUMAN_REVIEW")

    def test_human_call_stops_send(self):
        result = ingest_email(
            {
                "thread_id": "thread-call",
                "gmail_message_id": "m-call",
                "subject": "Need a call",
                "body": "Please call me this week for a collab",
                "from_email": "ajay@harbor.test",
                "to_email": "me@test.com",
            }
        )
        self.assertFalse(result["send_reply"])
        self.assertEqual(result["deal_status"], "HUMAN_REQUIRED")

    def test_low_offer_negotiates(self):
        result = ingest_email(
            {
                "thread_id": "thread-low",
                "gmail_message_id": "m-low",
                "subject": "Offer",
                "body": "We can offer 3500 for one reel",
                "from_email": "brand@test.com",
                "to_email": "me@test.com",
            }
        )
        self.assertEqual(result["ai_decision"], "NEGOTIATE")
        self.assertTrue(result["send_reply"])

    def test_target_offer_ready(self):
        result = ingest_email(
            {
                "thread_id": "thread-hi",
                "gmail_message_id": "m-hi",
                "subject": "Offer",
                "body": "Budget is 8000 for a reel",
                "from_email": "brand@test.com",
                "to_email": "me@test.com",
            }
        )
        self.assertEqual(result["deal_status"], "PENDING_CREATOR")

    def test_outgoing_uses_existing_client(self):
        ingest_email(
            {
                "thread_id": "thread-out",
                "gmail_message_id": "in-1",
                "subject": "Offer",
                "body": "collab 3500",
                "from_email": "brand@test.com",
                "to_email": "creator@test.com",
            }
        )
        ingest_email(
            {
                "thread_id": "thread-out",
                "gmail_message_id": "out-1",
                "subject": "Re: Offer",
                "body": "Our rate is higher",
                "from_email": "creator@test.com",
                "to_email": "brand@test.com",
                "direction": "OUTGOING",
            }
        )
        deal = Deal.objects.get(thread_id="thread-out")
        self.assertEqual(deal.client.email, "brand@test.com")
        self.assertEqual(deal.status, "WAITING_FOR_CLIENT")

    def test_terminal_protected(self):
        ingest_email(
            {
                "thread_id": "thread-done",
                "gmail_message_id": "done-1",
                "subject": "Offer",
                "body": "collab",
                "from_email": "brand@test.com",
                "to_email": "me@test.com",
            }
        )
        deal = Deal.objects.get(thread_id="thread-done")
        deal.status = "COMPLETED"
        deal.save()
        result = ingest_email(
            {
                "thread_id": "thread-done",
                "gmail_message_id": "done-2",
                "subject": "More",
                "body": "another 3500 offer",
                "from_email": "brand@test.com",
                "to_email": "me@test.com",
            }
        )
        deal.refresh_from_db()
        self.assertEqual(deal.status, "COMPLETED")
        self.assertEqual(result["reason"], "terminal_deal_protected")


@override_settings(INTERNAL_API_KEY="test-key")
class SecurityTests(TestCase):
    def test_ingest_requires_key(self):
        c = TestClient()
        res = c.post("/api/emails/ingest/", data="{}", content_type="application/json")
        self.assertEqual(res.status_code, 401)

    def test_ingest_with_key(self):
        c = TestClient()
        with patch("deals.pipeline.flask_post", side_effect=fake_pipeline):
            res = c.post(
                "/api/emails/ingest/",
                data=json.dumps(
                    {
                        "thread_id": "sec-1",
                        "gmail_message_id": "sec-m",
                        "subject": "Hi",
                        "body": "collaboration",
                        "from_email": "a@b.com",
                        "to_email": "c@d.com",
                    }
                ),
                content_type="application/json",
                HTTP_X_INTERNAL_API_KEY="test-key",
            )
        self.assertEqual(res.status_code, 201)

    def test_health_has_no_secrets(self):
        c = TestClient()
        res = c.get("/health/")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("INTERNAL_API_KEY", res.content.decode())
        self.assertNotIn("GOCSPX", res.content.decode())


@override_settings(INTERNAL_API_KEY="test-key", N8N_WEBHOOK_URL="")
class DashboardAcceptRejectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("admin", "admin@localhost", "DemoAdmin123!")
        self.client.force_login(self.user)
        self.notify = patch("deals.pipeline.notify_n8n")
        self.notify.start()
        self.addCleanup(self.notify.stop)
        self.ai = patch(
            "deals.pipeline.flask_post",
            return_value={"reply_body": "Thanks — closing this collaboration now."},
        )
        self.ai.start()
        self.addCleanup(self.ai.stop)

    def _ingest(self, thread_id, subject, from_email):
        res = self.client.post(
            "/api/emails/ingest/",
            data=json.dumps(
                {
                    "thread_id": thread_id,
                    "gmail_message_id": f"{thread_id}-m0",
                    "subject": subject,
                    "body": "Hi, paid Instagram Reel collaboration. Budget 8000 INR.",
                    "from_email": from_email,
                    "to_email": "creator@demo.local",
                    "skip_ai": True,
                }
            ),
            content_type="application/json",
            HTTP_X_INTERNAL_API_KEY="test-key",
        )
        self.assertEqual(res.status_code, 201)
        return res.json()["deal_id"]

    def test_api_list_shows_ingested_mail(self):
        deal_id = self._ingest("dash-mail-1", "E2E inbox collab", "inbox.brand@example.com")
        listing = self.client.get("/api/deals/?q=E2E+inbox+collab")
        self.assertEqual(listing.status_code, 200)
        subjects = [row["subject"] for row in listing.json()["results"]]
        self.assertIn("E2E inbox collab", subjects)
        detail = self.client.get(f"/api/deals/{deal_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], deal_id)

    def test_api_accept_queues_outgoing_mail(self):
        deal_id = self._ingest("dash-accept-1", "E2E accept collab", "accept.brand@example.com")
        res = self.client.post(
            f"/api/deals/{deal_id}/accept/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "COMPLETED")
        deal = Deal.objects.get(id=deal_id)
        self.assertEqual(deal.status, "COMPLETED")
        outgoing = EmailMessage.objects.filter(deal=deal, direction="OUTGOING")
        self.assertEqual(outgoing.count(), 1)
        self.assertIn("closing this collaboration", outgoing.get().body_text.lower())
        self.assertTrue(HumanAction.objects.filter(deal=deal, action="accept").exists())

    def test_api_reject_queues_outgoing_mail(self):
        deal_id = self._ingest("dash-reject-1", "E2E reject collab", "reject.brand@example.com")
        res = self.client.post(
            f"/api/deals/{deal_id}/reject/",
            data=json.dumps({"reason": "Dates do not work"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "REJECTED")
        deal = Deal.objects.get(id=deal_id)
        self.assertEqual(deal.status, "REJECTED")
        self.assertEqual(EmailMessage.objects.filter(deal=deal, direction="OUTGOING").count(), 1)
        self.assertTrue(
            HumanAction.objects.filter(deal=deal, action="reject", reason="Dates do not work").exists()
        )


class HeaderAlertTests(TestCase):
    def test_header_counts_call_accepted_rejected(self):
        from deals.context_processors import header_alerts

        user = User.objects.create_user("admin", "admin@localhost", "x")
        brand = Client.objects.create(email="alerts@brand.test", brand_name="Alert Co")
        Deal.objects.create(client=brand, subject="Call me", thread_id="ha-call", status="HUMAN_REQUIRED", human_required=True)
        Deal.objects.create(client=brand, subject="Yes", thread_id="ha-ok", status="COMPLETED")
        Deal.objects.create(client=brand, subject="No", thread_id="ha-no", status="REJECTED")
        req = RequestFactory().get("/")
        req.user = user
        alerts = header_alerts(req)["header_alerts"]
        self.assertEqual(alerts["needs_call"], 1)
        self.assertEqual(alerts["accepted"], 1)
        self.assertEqual(alerts["rejected"], 1)
        Deal.objects.filter(thread_id="ha-call").first().mark_header_seen()
        alerts = header_alerts(req)["header_alerts"]
        self.assertEqual(alerts["needs_call"], 0)
        self.assertEqual(alerts["accepted"], 1)
        self.assertEqual(alerts["rejected"], 1)
