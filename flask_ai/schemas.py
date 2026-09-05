from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def _as_label_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    out: list[str] = []
    for item in value:
        if isinstance(item, dict):
            text = item.get("id") or item.get("name") or ""
            if text:
                out.append(str(text))
        elif item is not None:
            out.append(str(item))
    return out


class SpamRequest(BaseModel):
    body: str = ""
    subject: str = ""
    from_email: str = ""
    reply_to: str = ""
    labels: list[str] = Field(default_factory=list)
    headers: dict[str, Any] = Field(default_factory=dict)
    urls: list[str] = Field(default_factory=list)
    attachment_names: list[str] = Field(default_factory=list)

    @field_validator("labels", mode="before")
    @classmethod
    def coerce_labels(cls, value: Any) -> list[str]:
        return _as_label_list(value)

    @field_validator("urls", "attachment_names", mode="before")
    @classmethod
    def coerce_str_list(cls, value: Any) -> list[str]:
        return _as_label_list(value)


class SpamResult(BaseModel):
    decision: str
    confidence: float = 0.0
    risk_signals: list[str] = Field(default_factory=list)
    reason: str = ""
    provider: str = ""
    model: str = ""
    prompt_version: str = "spam_v1"


class IntentRequest(BaseModel):
    body: str = ""
    subject: str = ""


class IntentResult(BaseModel):
    intent: str
    confidence: float = 0.0
    reason: str = ""
    provider: str = ""
    model: str = ""
    prompt_version: str = "intent_v1"


class ExtractRequest(BaseModel):
    body: str = ""
    subject: str = ""
    from_email: str = ""
    reply_to: str = ""
    source_message_id: Optional[str] = None


class ExtractResult(BaseModel):
    brand_name: Optional[str] = None
    contact_name: Optional[str] = None
    sender_email: Optional[str] = None
    reply_to: Optional[str] = None
    phone: Optional[str] = None
    platform: list[str] = Field(default_factory=list)
    campaign: Optional[str] = None
    product: Optional[str] = None
    deliverables: list[str] = Field(default_factory=list)
    budget_offered: Optional[float] = None
    currency: Optional[str] = None
    timeline: Optional[str] = None
    location: Optional[str] = None
    meeting_requested: bool = False
    human_contact_requested: bool = False
    contact_details: list[str] = Field(default_factory=list)
    source_message_id: Optional[str] = None
    confidence: float = 0.0
    provider: str = ""
    model: str = ""
    prompt_version: str = "extract_v1"


class NegotiationRequest(BaseModel):
    body: str = ""
    subject: str = ""
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
    extracted: dict[str, Any] = Field(default_factory=dict)
    rag_facts: list[dict[str, Any]] = Field(default_factory=list)
    min_price: float = 4000
    goal_price: float = 5000
    negotiation_round: int = 0
    max_rounds: int = 3
    action: str = "negotiate"


class NegotiationResult(BaseModel):
    decision: str
    reply_subject: str = ""
    reply_body: str = ""
    facts_used: list[str] = Field(default_factory=list)
    needs_human: bool = False
    confidence: float = 0.0
    offer_amount: Optional[float] = None
    reason: str = ""
    provider: str = ""
    model: str = ""
    prompt_version: str = "negotiate_v1"


class RouterFailure(BaseModel):
    available: bool = False
    error_type: str = "AI_UNAVAILABLE"
    reason: str = "All AI providers failed"
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    decision: str = "HUMAN_REVIEW"
