from pathlib import Path
from typing import Any, Optional

from router import RouterError, complete_json
from safety import sanitize_user_content
from schemas import ExtractRequest, ExtractResult

PROMPT = (Path(__file__).parent / "prompts" / "extract_v1.txt").read_text(encoding="utf-8")


def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    digits = "".join(ch for ch in text if ch.isdigit() or ch in ".-")
    try:
        return float(digits) if digits not in {"", ".", "-"} else None
    except ValueError:
        return None


def extract_lead(req: ExtractRequest, correlation_id: str = "") -> ExtractResult:
    user = sanitize_user_content(
        f"Subject: {req.subject}\nFrom: {req.from_email}\nReply-To: {req.reply_to}\nMessage-ID: {req.source_message_id}\n\n{req.body}"
    )
    try:
        parsed, meta = complete_json("extract", PROMPT, user, correlation_id=correlation_id)
    except RouterError:
        return ExtractResult(
            sender_email=req.from_email or None,
            reply_to=req.reply_to or None,
            source_message_id=req.source_message_id,
            confidence=0.0,
            provider="none",
            model="",
        )
    provider = meta["provider"]
    model = meta["model"]
    return ExtractResult(
        brand_name=parsed.get("brand_name") or None,
        contact_name=parsed.get("contact_name") or None,
        sender_email=parsed.get("sender_email") or req.from_email or None,
        reply_to=parsed.get("reply_to") or req.reply_to or None,
        phone=parsed.get("phone") or None,
        platform=list(parsed.get("platform") or []),
        campaign=parsed.get("campaign") or None,
        product=parsed.get("product") or None,
        deliverables=list(parsed.get("deliverables") or []),
        budget_offered=_num(parsed.get("budget_offered")),
        currency=parsed.get("currency") or None,
        timeline=parsed.get("timeline") or None,
        location=parsed.get("location") or None,
        meeting_requested=bool(parsed.get("meeting_requested")),
        human_contact_requested=bool(parsed.get("human_contact_requested")),
        contact_details=list(parsed.get("contact_details") or []),
        source_message_id=req.source_message_id,
        confidence=float(parsed.get("confidence") or 0),
        provider=provider,
        model=model,
    )
