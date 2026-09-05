import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from deals.models import AIInteraction, Client, Deal, EmailMessage, HumanAction, NegotiationTurn

REPO = Path(settings.BASE_DIR).parent
DEMO_DIR = Path(os.environ.get("DEMO_DATA_DIR") or (REPO / "demo_data"))
if not DEMO_DIR.exists():
    alt = Path("/demo_data")
    if alt.exists():
        DEMO_DIR = alt


class Command(BaseCommand):
    help = "Load demo_data/*.json into SQLite for a local dashboard demo (no Gmail send)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo threads first")

    def handle(self, *args, **options):
        if not DEMO_DIR.exists():
            self.stderr.write("demo_data/ missing")
            return
        files = sorted(DEMO_DIR.glob("*.json"))
        if options["reset"]:
            Deal.objects.filter(thread_id__startswith="demo-").delete()
            Client.objects.filter(email__endswith="@demo.local").delete()
        loaded = 0
        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self._load_item(payload)
            loaded += 1
        self.stdout.write(self.style.SUCCESS(f"Loaded {loaded} demo fixtures"))

    def _load_item(self, item: dict):
        client, _ = Client.objects.get_or_create(
            email=item["client"]["email"],
            defaults={
                "brand_name": item["client"].get("brand_name") or "",
                "contact_name": item["client"].get("contact_name") or "",
                "phone": item["client"].get("phone") or "",
            },
        )
        for field in ("brand_name", "contact_name", "phone"):
            if item["client"].get(field):
                setattr(client, field, item["client"][field])
        client.save()
        deal, _ = Deal.objects.update_or_create(
            thread_id=item["thread_id"],
            defaults={
                "client": client,
                "subject": item["subject"],
                "status": item["status"],
                "intent": item.get("intent") or "",
                "priority": item.get("priority") or "MEDIUM",
                "spam_decision": item.get("spam_decision") or "",
                "confidence": item.get("confidence"),
                "budget_offered": item.get("budget_offered"),
                "currency": item.get("currency") or "",
                "min_price": item.get("min_price") or settings.NEGOTIATION_MIN_PRICE,
                "target_price": item.get("target_price") or settings.NEGOTIATION_TARGET_PRICE,
                "negotiation_round": item.get("negotiation_round") or 0,
                "human_required": item.get("human_required") or False,
                "human_required_reason": item.get("human_required_reason") or "",
                "extracted_json": item.get("extracted") or {},
                "rag_facts_json": item.get("rag_facts") or [],
                "ai_summary": item.get("ai_summary") or "",
                "ai_generated_reply": item.get("ai_reply") or "",
                "last_ai_provider": item.get("provider") or "mock",
                "last_ai_model": item.get("model") or "demo",
                "last_ai_decision": item.get("ai_decision") or "",
            },
        )
        deal.emails.all().delete()
        for idx, msg in enumerate(item.get("messages") or []):
            EmailMessage.objects.create(
                deal=deal,
                gmail_message_id=msg.get("gmail_message_id") or f"{item['thread_id']}-m{idx}",
                thread_id=item["thread_id"],
                direction=msg["direction"],
                subject=msg.get("subject") or item["subject"],
                body=msg.get("body") or "",
                body_text=msg.get("body") or "",
                from_email=msg["from_email"],
                to_email=msg.get("to_email") or "",
                reply_to=msg.get("reply_to") or "",
            )
        deal.negotiation_turns.all().delete()
        for turn in item.get("turns") or []:
            NegotiationTurn.objects.create(
                deal=deal,
                round=turn.get("round") or 1,
                client_message=turn.get("client_message") or "",
                ai_reply=turn.get("ai_reply") or "",
                decision=turn.get("decision") or "",
                offer_amount=turn.get("offer_amount"),
            )
        if item.get("human_note"):
            HumanAction.objects.create(deal=deal, action="note", notes=item["human_note"])
        if item.get("ai_decision"):
            AIInteraction.objects.create(
                deal=deal,
                task="demo",
                provider=item.get("provider") or "mock",
                model=item.get("model") or "demo",
                success=True,
                summary=item.get("ai_summary") or item.get("ai_decision"),
            )
