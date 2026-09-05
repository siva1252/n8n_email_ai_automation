from __future__ import annotations

import logging
import re
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .gmail_parser import normalize_gmail_payload
from .models import AIInteraction, Client, Deal, EmailMessage, HumanAction, NegotiationTurn

logger = logging.getLogger(__name__)

ACTIONABLE_INTENTS = {
    "COLLABORATION",
    "PROMOTION",
    "SPONSORSHIP",
    "AFFILIATE",
    "PRODUCT_REVIEW",
    "BUSINESS_INQUIRY",
}


def polish_creator_reply(text: str) -> str:
    name = getattr(settings, "CREATOR_NAME", "Siva") or "Siva"
    body = re.sub(r"\*{0,2}\[(?:Creator Name|Your Name|Name)\]\*{0,2}", name, text or "", flags=re.I).strip()
    if re.search(r"best regards|kind regards|warm regards", body, re.I):
        if name.lower() not in body.splitlines()[-1].lower():
            last = body.splitlines()[-1].strip()
            if last.endswith(",") or last.lower() in {"best regards", "kind regards", "warm regards"}:
                body = body.rstrip() + f"\n{name}"
        return body
    return f"{body}\n\nBest regards,\n{name}"


def flask_post(path: str, payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    url = f"{settings.FLASK_AI_URL}{path}"
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def assign_priority(deal: Deal) -> str:
    if deal.human_required or deal.status in {"HUMAN_REQUIRED", "PENDING_CREATOR"}:
        return "HIGH"
    if deal.budget_offered and deal.target_price and deal.budget_offered >= deal.target_price:
        return "HIGH"
    if deal.status in {"NEED_INFORMATION", "WAITING_FOR_CLIENT", "NEW"} and deal.intent in ACTIONABLE_INTENTS:
        return "MEDIUM"
    if deal.status == "SPAM":
        return "LOW"
    return "MEDIUM"


def client_for_message(normalized: dict[str, Any], existing_deal: Deal | None) -> Client:
    if existing_deal:
        return existing_deal.client
    direction = normalized["direction"]
    brand_email = normalized["from_email"] if direction == "INCOMING" else (normalized["to_email"] or normalized["from_email"])
    client, _ = Client.objects.get_or_create(
        email=brand_email or "unknown@example.com",
        defaults={"brand_name": normalized.get("brand_name") or ""},
    )
    if normalized.get("brand_name") and not client.brand_name:
        client.brand_name = normalized["brand_name"]
        client.save(update_fields=["brand_name", "updated_at"])
    return client


def record_ai(deal: Deal, email: EmailMessage | None, task: str, payload: dict[str, Any], success: bool = True):
    AIInteraction.objects.create(
        deal=deal,
        email=email,
        task=task,
        provider=payload.get("provider") or "",
        model=payload.get("model") or "",
        prompt_version=payload.get("prompt_version") or "",
        success=success,
        confidence=payload.get("confidence"),
        error_type="" if success else payload.get("error_type") or "AI_UNAVAILABLE",
        summary=(payload.get("reason") or payload.get("decision") or payload.get("intent") or "")[:500],
    )


def persist_outgoing(normalized: dict[str, Any]) -> dict[str, Any]:
    thread_id = normalized["thread_id"]
    if not thread_id:
        return {"error": "thread_id is required", "status": 400}
    try:
        deal = Deal.objects.select_related("client").get(thread_id=thread_id)
    except Deal.DoesNotExist:
        return {"error": "Deal not found for thread", "status": 404}

    message_id = normalized.get("gmail_message_id")
    if message_id:
        existing = EmailMessage.objects.filter(gmail_message_id=message_id).first()
        if existing:
            return {"status": "duplicate", "deal_id": deal.id, "email_message_id": existing.id, "deal_status": deal.status}

    email = EmailMessage.objects.create(
        deal=deal,
        gmail_message_id=message_id,
        thread_id=thread_id,
        direction="OUTGOING",
        subject=normalized["subject"],
        body=normalized["body"],
        body_text=normalized["body_text"],
        body_html=normalized.get("body_html") or "",
        from_email=normalized["from_email"],
        to_email=normalized["to_email"] or deal.client.email,
        reply_to=normalized.get("reply_to") or "",
        headers_json=normalized.get("headers") or {},
        labels_json=normalized.get("labels") or [],
        attachment_metadata_json=normalized.get("attachments") or [],
        urls_json=normalized.get("urls") or [],
        idempotency_key=normalized.get("idempotency_key") or "",
        sent_at=normalized.get("sent_at") or timezone.now(),
    )
    if not deal.is_terminal:
        deal.status = "WAITING_FOR_CLIENT"
        deal.send_reply = False
        deal.our_reply_sent_at = timezone.now()
        deal.save(update_fields=["status", "send_reply", "our_reply_sent_at", "updated_at"])
    return {"status": "success", "deal_id": deal.id, "email_message_id": email.id, "deal_status": deal.status}


def ingest_email(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_gmail_payload(raw)
    if not normalized["thread_id"]:
        return {"error": "thread_id is required", "status": 400}
    if not normalized["from_email"]:
        return {"error": "from_email is required", "status": 400}

    if normalized["direction"] == "OUTGOING":
        result = persist_outgoing(normalized)
        if result.get("error"):
            result["status_code"] = result.get("status", 400) if isinstance(result.get("status"), int) else 400
            return result
        result["status_code"] = 200 if result.get("status") == "duplicate" else 201
        return result

    with transaction.atomic():
        if normalized.get("gmail_message_id"):
            existing_msg = (
                EmailMessage.objects.select_related("deal", "deal__client")
                .filter(gmail_message_id=normalized["gmail_message_id"])
                .first()
            )
            if existing_msg:
                deal = existing_msg.deal
                return {
                    "status": "duplicate",
                    "deal_id": deal.id,
                    "email_message_id": existing_msg.id,
                    "deal_status": deal.status,
                    "send_reply": False,
                    "ai_reply": deal.ai_generated_reply,
                    "status_code": 200,
                }

        existing_deal = Deal.objects.filter(thread_id=normalized["thread_id"]).select_related("client").first()
        client = client_for_message(normalized, existing_deal)
        deal, created = Deal.objects.get_or_create(
            thread_id=normalized["thread_id"],
            defaults={
                "client": client,
                "subject": normalized["subject"],
                "status": "NEW",
                "min_price": settings.NEGOTIATION_MIN_PRICE,
                "target_price": settings.NEGOTIATION_TARGET_PRICE,
            },
        )
        if deal.subject != normalized["subject"] and normalized["subject"]:
            deal.subject = normalized["subject"]
            deal.save(update_fields=["subject", "updated_at"])

        email = EmailMessage.objects.create(
            deal=deal,
            gmail_message_id=normalized.get("gmail_message_id"),
            thread_id=normalized["thread_id"],
            direction="INCOMING",
            subject=normalized["subject"],
            body=normalized["body"],
            body_text=normalized["body_text"],
            body_html=normalized.get("body_html") or "",
            from_email=normalized["from_email"],
            to_email=normalized["to_email"],
            reply_to=normalized.get("reply_to") or "",
            headers_json=normalized.get("headers") or {},
            labels_json=normalized.get("labels") or [],
            attachment_metadata_json=normalized.get("attachments") or [],
            urls_json=normalized.get("urls") or [],
            received_at=normalized.get("received_at") or timezone.now(),
        )
        deal.client_replied_at = timezone.now()
        deal.save(update_fields=["client_replied_at", "updated_at"])

        if deal.is_terminal:
            return {
                "status": "success",
                "deal_id": deal.id,
                "deal_created": created,
                "email_message_id": email.id,
                "deal_status": deal.status,
                "send_reply": False,
                "reason": "terminal_deal_protected",
                "status_code": 201,
            }

        if normalized.get("skip_ai"):
            return {
                "status": "success",
                "deal_id": deal.id,
                "deal_created": created,
                "email_message_id": email.id,
                "deal_status": deal.status,
                "send_reply": False,
                "status_code": 201,
            }

        return _run_ai_pipeline(deal, email, normalized, created)


def _run_ai_pipeline(deal: Deal, email: EmailMessage, normalized: dict[str, Any], created: bool) -> dict[str, Any]:
    flask_payload = {
        "body": normalized["body_text"] or normalized["body"],
        "subject": normalized["subject"],
        "from_email": normalized["from_email"],
        "reply_to": normalized.get("reply_to") or "",
        "labels": [
            (x.get("id") if isinstance(x, dict) else x)
            for x in (normalized.get("labels") or [])
            if (x.get("id") if isinstance(x, dict) else x)
        ],
        "headers": normalized.get("headers") or {},
        "urls": normalized.get("urls") or [],
        "attachment_names": [a.get("filename") for a in (normalized.get("attachments") or []) if isinstance(a, dict)],
        "source_message_id": normalized.get("gmail_message_id"),
        "correlation_id": normalized.get("correlation_id") or deal.thread_id,
        "min_price": deal.min_price or settings.NEGOTIATION_MIN_PRICE,
        "goal_price": deal.target_price or settings.NEGOTIATION_TARGET_PRICE,
        "negotiation_round": deal.negotiation_round,
        "max_rounds": settings.NEGOTIATION_MAX_ROUNDS,
        "action": "negotiate",
    }

    try:
        pipeline = flask_post("/ai/pipeline", flask_payload)
    except Exception as exc:
        logger.exception("Flask pipeline failed")
        deal.status = "REVIEW"
        deal.spam_decision = "REVIEW"
        deal.human_required = True
        deal.human_required_reason = f"AI unavailable: {exc}"
        deal.priority = "HIGH"
        deal.send_reply = False
        deal.save()
        record_ai(deal, email, "pipeline", {"error_type": "AI_UNAVAILABLE", "reason": str(exc)}, success=False)
        return {
            "status": "success",
            "deal_id": deal.id,
            "deal_created": created,
            "email_message_id": email.id,
            "deal_status": deal.status,
            "send_reply": False,
            "ai_decision": "HUMAN_REVIEW",
            "reason": "AI_UNAVAILABLE",
            "status_code": 201,
        }

    spam = pipeline.get("spam") or {}
    record_ai(deal, email, "spam", spam, success=spam.get("provider") not in {"", "none"})
    deal.spam_decision = spam.get("decision") or ""
    deal.confidence = spam.get("confidence")
    deal.last_ai_provider = spam.get("provider") or ""
    deal.last_ai_model = spam.get("model") or ""

    if spam.get("decision") == "SPAM":
        deal.status = "SPAM"
        deal.priority = "LOW"
        deal.send_reply = False
        deal.ai_summary = spam.get("reason") or "Classified as spam"
        deal.save()
        return {
            "status": "success",
            "deal_id": deal.id,
            "deal_created": created,
            "email_message_id": email.id,
            "deal_status": deal.status,
            "send_reply": False,
            "apply_spam_label": True,
            "ai_decision": "SPAM",
            "spam": spam,
            "status_code": 201,
        }

    if spam.get("decision") == "REVIEW":
        deal.status = "REVIEW"
        deal.priority = "HIGH"
        deal.human_required = True
        deal.human_required_reason = spam.get("reason") or "Needs review"
        deal.send_reply = False
        deal.ai_summary = deal.human_required_reason
        deal.save()
        return {
            "status": "success",
            "deal_id": deal.id,
            "deal_created": created,
            "email_message_id": email.id,
            "deal_status": deal.status,
            "send_reply": False,
            "ai_decision": "REVIEW",
            "spam": spam,
            "status_code": 201,
        }

    intent = pipeline.get("intent") or {}
    extract = pipeline.get("extract") or {}
    negotiation = pipeline.get("negotiation") or {}
    record_ai(deal, email, "intent", intent)
    record_ai(deal, email, "extract", extract)
    record_ai(deal, email, "negotiate", negotiation)

    deal.intent = intent.get("intent") or ""
    deal.extracted_json = extract
    deal.budget_offered = extract.get("budget_offered")
    deal.currency = extract.get("currency") or deal.currency
    if extract.get("brand_name") and not deal.client.brand_name:
        deal.client.brand_name = extract["brand_name"]
        deal.client.save(update_fields=["brand_name", "updated_at"])
    if extract.get("phone") and not deal.client.phone:
        deal.client.phone = extract["phone"]
        deal.client.save(update_fields=["phone", "updated_at"])
    if extract.get("contact_name") and not deal.client.contact_name:
        deal.client.contact_name = extract["contact_name"]
        deal.client.save(update_fields=["contact_name", "updated_at"])

    decision = (negotiation.get("decision") or "").upper()
    deal.last_ai_decision = decision
    deal.last_ai_provider = negotiation.get("provider") or deal.last_ai_provider
    deal.last_ai_model = negotiation.get("model") or deal.last_ai_model
    deal.ai_generated_reply = polish_creator_reply(negotiation.get("reply_body") or negotiation.get("reply") or "")
    deal.rag_facts_json = negotiation.get("facts_used") or []
    deal.ai_summary = negotiation.get("reason") or intent.get("reason") or ""
    deal.send_reply = False

    if decision == "HUMAN_REQUIRED" or negotiation.get("needs_human"):
        deal.status = "HUMAN_REQUIRED"
        deal.human_required = True
        deal.human_required_reason = negotiation.get("reason") or "Human follow-up required"
        deal.priority = "HIGH"
    elif decision == "READY_TO_CLOSE":
        deal.status = "PENDING_CREATOR"
        deal.priority = "HIGH"
        deal.human_required = False
    elif decision == "NEED_INFORMATION":
        deal.status = "NEED_INFORMATION"
        deal.negotiation_round += 1
        deal.send_reply = bool(deal.ai_generated_reply)
        deal.priority = assign_priority(deal)
    elif decision == "REJECT":
        deal.status = "AUTO_REJECTED"
        deal.send_reply = bool(deal.ai_generated_reply)
        deal.priority = "LOW"
    elif deal.intent in ACTIONABLE_INTENTS:
        deal.status = "NEW" if created else deal.status
        if decision == "NEGOTIATE":
            deal.negotiation_round += 1
            deal.send_reply = bool(deal.ai_generated_reply)
        deal.priority = assign_priority(deal)
    else:
        deal.status = "NEW"
        deal.priority = "LOW"
        deal.send_reply = False

    deal.priority = assign_priority(deal)
    deal.save()

    if decision or deal.ai_generated_reply:
        NegotiationTurn.objects.create(
            deal=deal,
            round=deal.negotiation_round or 1,
            client_message=email.body_text or email.body,
            ai_reply=deal.ai_generated_reply,
            decision=decision,
            offer_amount=deal.budget_offered,
        )

    return {
        "status": "success",
        "deal_id": deal.id,
        "deal_created": created,
        "email_message_id": email.id,
        "deal_status": deal.status,
        "intent": deal.intent,
        "priority": deal.priority,
        "send_reply": deal.send_reply,
        "ai_decision": decision,
        "ai_reply": deal.ai_generated_reply,
        "reply_subject": negotiation.get("reply_subject") or f"Re: {deal.subject}",
        "to_email": deal.client.email,
        "thread_id": deal.thread_id,
        "spam": spam,
        "extract": extract,
        "status_code": 201,
    }


def notify_n8n(deal: Deal, action: str) -> None:
    if not settings.N8N_WEBHOOK_URL:
        return
    try:
        url = settings.N8N_WEBHOOK_URL or ""
        if "://n8n:" in url:
            url = url.replace("://n8n:", "://127.0.0.1:")
        requests.post(
            url,
            json={
                "action": action,
                "thread_id": deal.thread_id,
                "deal_id": deal.id,
                "ai_reply": deal.ai_generated_reply,
                "from_email": deal.client.email,
                "subject": deal.subject,
                "idempotency_key": f"{action}:{deal.id}:{deal.thread_id}",
                "internal_api_key": settings.INTERNAL_API_KEY,
            },
            headers={"X-Internal-API-Key": settings.INTERNAL_API_KEY},
            timeout=90,
        )
    except Exception as exc:
        logger.warning("n8n webhook failed: %s", exc)


def accept_or_reject(deal: Deal, action: str, user=None, reason: str = "") -> Deal:
    if deal.status not in {"PENDING_CREATOR", "HUMAN_REQUIRED", "NEED_INFORMATION", "WAITING_FOR_CLIENT", "NEW", "REVIEW"}:
        if deal.is_terminal:
            return deal
    payload = {
        "body": f"The creator has chosen to {action} this deal. Reason: {reason}",
        "subject": deal.subject,
        "chat_history": [
            {"role": "client" if m.direction == "INCOMING" else "ai", "content": m.body_text or m.body}
            for m in deal.emails.order_by("created_at")
        ],
        "extracted": deal.extracted_json or {},
        "action": action,
        "min_price": deal.min_price,
        "goal_price": deal.target_price,
    }
    try:
        ai = flask_post("/ai/negotiate", payload)
        deal.ai_generated_reply = polish_creator_reply(ai.get("reply_body") or ai.get("reply") or deal.ai_generated_reply)
        record_ai(deal, None, action, ai)
    except Exception as exc:
        logger.warning("closing email AI failed: %s", exc)
        if action == "accept":
            deal.ai_generated_reply = polish_creator_reply(
                deal.ai_generated_reply
                or "Thank you — we accept this collaboration and will follow up with next steps."
            )
        else:
            deal.ai_generated_reply = polish_creator_reply(
                deal.ai_generated_reply
                or "Thank you for reaching out. We are unable to take this project on right now."
            )

    deal.status = "COMPLETED" if action == "accept" else "REJECTED"
    deal.human_required = False
    deal.send_reply = True
    deal.save()
    HumanAction.objects.create(deal=deal, action=action, reason=reason, user=user)
    EmailMessage.objects.create(
        deal=deal,
        thread_id=deal.thread_id,
        direction="OUTGOING",
        subject=f"Re: {deal.subject}",
        body=deal.ai_generated_reply or "",
        body_text=deal.ai_generated_reply or "",
        from_email="creator@local",
        to_email=deal.client.email,
        idempotency_key=f"{action}:{deal.id}",
        sent_at=timezone.now(),
    )
    notify_n8n(deal, action)
    return deal
