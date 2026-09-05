from pathlib import Path

from router import RouterError, complete_json
from safety import dangerous_attachment, sanitize_user_content
from schemas import SpamRequest, SpamResult

PROMPT = (Path(__file__).parent / "prompts" / "spam_v1.txt").read_text(encoding="utf-8")


def metadata_signals(req: SpamRequest) -> list[str]:
    """Gmail/header/attachment metadata only — no body keyword lists."""
    signals = []
    labels = [str(x).upper() for x in req.labels]
    if any("SPAM" in lab for lab in labels):
        signals.append("gmail_spam_label")
    from_l = (req.from_email or "").lower()
    reply = (req.reply_to or "").lower()
    if reply and from_l and "@" in reply and "@" in from_l:
        if reply.split("<")[-1].strip("> ") != from_l.split("<")[-1].strip("> "):
            signals.append("sender_reply_to_mismatch")
    for name in req.attachment_names:
        if dangerous_attachment(name):
            signals.append(f"dangerous_attachment:{name}")
    spf = str(req.headers.get("Authentication-Results") or req.headers.get("authentication-results") or "").lower()
    if "spf=fail" in spf or "dkim=fail" in spf or "dmarc=fail" in spf:
        signals.append("auth_fail")
    return signals


def classify_spam(req: SpamRequest, correlation_id: str = "") -> SpamResult:
    signals = metadata_signals(req)
    user = sanitize_user_content(
        f"""Subject: {req.subject}
From: {req.from_email}
Reply-To: {req.reply_to}
Gmail labels: {req.labels}
Headers: {req.headers}
URLs: {req.urls}
Attachments: {req.attachment_names}
Metadata signals: {signals}

Email body:
{req.body}
"""
    )
    try:
        parsed, meta = complete_json("spam", PROMPT, user, correlation_id=correlation_id)
    except RouterError:
        return SpamResult(
            decision="REVIEW",
            confidence=0.0,
            risk_signals=signals + ["ai_unavailable"],
            reason="AI providers unavailable; routed to review instead of spam",
            provider="none",
            model="",
        )

    decision = str(parsed.get("decision", "REVIEW")).upper()
    if decision not in {"SPAM", "NOT_SPAM", "REVIEW"}:
        decision = "REVIEW"
    confidence = float(parsed.get("confidence") or 0)
    ai_signals = [str(s) for s in parsed.get("risk_signals") or []]
    merged = list(dict.fromkeys(signals + ai_signals))
    if confidence < 0.6 and decision == "SPAM":
        decision = "REVIEW"

    return SpamResult(
        decision=decision,
        confidence=confidence,
        risk_signals=merged,
        reason=str(parsed.get("reason") or ""),
        provider=meta["provider"],
        model=meta["model"],
    )
