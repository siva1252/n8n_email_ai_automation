from pathlib import Path

from router import RouterError, complete_json
from safety import sanitize_user_content
from schemas import IntentRequest, IntentResult

PROMPT = (Path(__file__).parent / "prompts" / "intent_v1.txt").read_text(encoding="utf-8")
VALID = {
    "COLLABORATION",
    "PROMOTION",
    "SPONSORSHIP",
    "AFFILIATE",
    "PRODUCT_REVIEW",
    "EVENT_INVITE",
    "BUSINESS_INQUIRY",
    "JOB_RECRUITMENT",
    "PERSONAL",
    "NEWSLETTER",
    "TRANSACTIONAL",
    "SUPPORT",
    "HUMAN_CONVERSATION",
    "OTHER",
    "UNCERTAIN",
}


def classify_intent(req: IntentRequest, correlation_id: str = "") -> IntentResult:
    user = sanitize_user_content(f"Subject: {req.subject}\n\n{req.body}")
    try:
        parsed, meta = complete_json("intent", PROMPT, user, correlation_id=correlation_id)
    except RouterError:
        return IntentResult(
            intent="UNCERTAIN",
            confidence=0.0,
            reason="AI unavailable",
            provider="none",
            model="",
        )
    intent = str(parsed.get("intent") or "UNCERTAIN").upper()
    if intent not in VALID:
        intent = "UNCERTAIN"
    return IntentResult(
        intent=intent,
        confidence=float(parsed.get("confidence") or 0),
        reason=str(parsed.get("reason") or ""),
        provider=meta["provider"],
        model=meta["model"],
    )
