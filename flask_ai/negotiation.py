from pathlib import Path
from typing import Any, Optional

from rag import facts_for_prompt
from router import RouterError, complete_json
from safety import reply_is_safe, sanitize_user_content
from schemas import NegotiationRequest, NegotiationResult

PROMPTS = {
    "negotiate": (Path(__file__).parent / "prompts" / "negotiate_v1.txt").read_text(encoding="utf-8"),
    "accept": (Path(__file__).parent / "prompts" / "accept_v1.txt").read_text(encoding="utf-8"),
    "reject": (Path(__file__).parent / "prompts" / "reject_v1.txt").read_text(encoding="utf-8"),
}

VALID_DECISIONS = {"READY_TO_CLOSE", "NEGOTIATE", "NEED_INFORMATION", "HUMAN_REQUIRED", "REJECT", "ACCEPTED", "REJECTED"}
ACTIONABLE_INTENTS = {
    "COLLABORATION",
    "PROMOTION",
    "SPONSORSHIP",
    "AFFILIATE",
    "PRODUCT_REVIEW",
    "BUSINESS_INQUIRY",
}


def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def negotiate(req: NegotiationRequest, correlation_id: str = "") -> NegotiationResult:
    action = (req.action or "negotiate").lower()
    prompt_key = action if action in PROMPTS else "negotiate"
    extracted = req.extracted or {}
    offer = _num(extracted.get("budget_offered"))
    query = " ".join(
        [
            str(extracted.get("brand_name") or ""),
            str(extracted.get("campaign") or ""),
            " ".join(extracted.get("deliverables") or []),
            str(extracted.get("product") or ""),
            "pricing packages minimum rates negotiation",
        ]
    )
    rag_facts = req.rag_facts or facts_for_prompt(query or req.body, top_k=4)

    facts_text = "\n\n".join(
        f"[{f.get('source_id')}] {f.get('text')}" for f in rag_facts
    ) or "No RAG facts retrieved."
    history = ""
    for msg in req.chat_history:
        role = msg.get("role") or "client"
        history += f"{role}: {msg.get('content')}\n\n"
    user = sanitize_user_content(
        f"""Subject: {req.subject}
Min price (internal): {req.min_price}
Target price (internal): {req.goal_price}
Negotiation round: {req.negotiation_round}/{req.max_rounds}
Extracted lead JSON: {extracted}

Retrieved RAG facts (do not paste verbatim to the client):
{facts_text}

Thread:
{history}

Latest message:
{req.body}
"""
    )
    try:
        parsed, meta = complete_json(prompt_key, PROMPTS[prompt_key], user, correlation_id=correlation_id)
    except RouterError:
        return NegotiationResult(
            decision="HUMAN_REQUIRED",
            needs_human=True,
            reason="AI unavailable",
            provider="none",
            model="",
            offer_amount=offer,
        )

    decision = str(parsed.get("decision") or "HUMAN_REQUIRED").upper()
    if decision == "ACCEPT":
        decision = "READY_TO_CLOSE"
    if decision not in VALID_DECISIONS:
        decision = "HUMAN_REQUIRED"
    reply = str(parsed.get("reply_body") or parsed.get("reply") or "").strip()
    ok, why = reply_is_safe(reply)
    if not ok:
        return NegotiationResult(
            decision="HUMAN_REQUIRED",
            needs_human=True,
            reason=f"Reply failed safety: {why}",
            provider=meta["provider"],
            model=meta["model"],
            offer_amount=offer,
        )

    retrieved_ids = [str(f.get("source_id")) for f in rag_facts if f.get("source_id")]
    model_ids = [
        str(x)
        for x in (parsed.get("facts_used") or [])
        if x and str(x).strip().lower() not in {"none", "none recorded"}
    ]
    facts_used = list(dict.fromkeys(retrieved_ids + model_ids))
    needs_human = bool(parsed.get("needs_human")) or decision == "HUMAN_REQUIRED"
    return NegotiationResult(
        decision=decision,
        reply_subject=str(parsed.get("reply_subject") or (f"Re: {req.subject}" if req.subject else "Re: your email")),
        reply_body=reply,
        facts_used=facts_used,
        needs_human=needs_human,
        confidence=float(parsed.get("confidence") or 0),
        offer_amount=_num(parsed.get("offer_amount")) or offer,
        reason=str(parsed.get("reason") or ""),
        provider=meta["provider"],
        model=meta["model"],
        prompt_version=f"{prompt_key}_v1",
    )
