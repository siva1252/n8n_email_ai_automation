from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests

import config


def extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError("No JSON object found in model response")


@dataclass
class ProviderResult:
    provider: str
    model: str
    content: str
    raw: dict[str, Any] = field(default_factory=dict)


class ProviderError(Exception):
    def __init__(self, provider: str, message: str, error_type: str = "provider_error"):
        super().__init__(message)
        self.provider = provider
        self.error_type = error_type


class BaseProvider:
    name = "base"

    def is_available(self) -> bool:
        return False

    def complete(self, messages: list[dict[str, str]], timeout: int) -> ProviderResult:
        raise NotImplementedError


class MockProvider(BaseProvider):
    name = "mock"

    def is_available(self) -> bool:
        return True

    def complete(self, messages: list[dict[str, str]], timeout: int) -> ProviderResult:
        user = " ".join(m.get("content", "") for m in messages if m.get("role") == "user").lower()
        system = " ".join(m.get("content", "") for m in messages if m.get("role") == "system").lower()
        if "spam" in system or "phishing" in system:
            is_spam = any(k in user for k in ("verify your password", "won a prize", "click here immediately", "crypto giveaway"))
            payload = {
                "decision": "SPAM" if is_spam else "NOT_SPAM",
                "confidence": 0.92 if is_spam else 0.88,
                "risk_signals": ["phishing_language"] if is_spam else [],
                "reason": "Mock spam decision",
            }
        elif "intent" in system:
            intent = "COLLABORATION"
            if "newsletter" in user:
                intent = "NEWSLETTER"
            elif "job" in user or "hiring" in user:
                intent = "JOB_RECRUITMENT"
            elif "personal" in user or "family" in user:
                intent = "PERSONAL"
            payload = {"intent": intent, "confidence": 0.9, "reason": "Mock intent"}
        elif "extract" in system:
            budget = None
            if "3500" in user:
                budget = 3500
            elif "5000" in user:
                budget = 5000
            elif "8000" in user:
                budget = 8000
            payload = {
                "brand_name": "Demo Brand",
                "contact_name": None,
                "sender_email": None,
                "phone": None,
                "platform": ["instagram"],
                "campaign": None,
                "product": None,
                "deliverables": ["1 reel"] if "reel" in user else [],
                "budget_offered": budget,
                "currency": "INR" if budget else None,
                "timeline": None,
                "location": None,
                "meeting_requested": "call" in user or "meet" in user,
                "human_contact_requested": "call" in user or "phone" in user,
                "contact_details": [],
                "confidence": 0.85,
            }
        elif "accept" in system:
            payload = {
                "decision": "ACCEPTED",
                "reply_subject": "Re: Collaboration",
                "reply_body": "Thank you — we accept the proposed collaboration and will follow up with next steps.",
                "facts_used": [],
                "needs_human": False,
                "confidence": 0.95,
            }
        elif "reject" in system:
            payload = {
                "decision": "REJECTED",
                "reply_subject": "Re: Collaboration",
                "reply_body": "Thank you for reaching out. We do not have capacity for this project right now and hope to collaborate in the future.",
                "facts_used": [],
                "needs_human": False,
                "confidence": 0.95,
            }
        else:
            payload = {
                "decision": "NEGOTIATE",
                "reply_subject": "Re: Collaboration",
                "reply_body": "Thanks for the offer. Our typical package for this deliverable is above the amount mentioned. Could you share budget flexibility and the full brief?",
                "facts_used": ["creator_policy.md"],
                "needs_human": False,
                "confidence": 0.84,
                "offer_amount": None,
                "reason": "Mock negotiation",
            }
        return ProviderResult(provider="mock", model="mock-deterministic", content=json.dumps(payload))


class OllamaProvider(BaseProvider):
    name = "ollama"

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=3)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def _pick_model(self) -> str:
        try:
            r = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=3)
            names = [m.get("name") for m in r.json().get("models", [])]
        except requests.RequestException:
            names = []
        for candidate in (config.OLLAMA_MODEL, config.OLLAMA_FALLBACK_MODEL, "phi3:latest", "phi3"):
            if not candidate:
                continue
            if not names:
                return candidate
            if candidate in names or any(n.startswith(candidate.split(":")[0]) for n in names):
                match = next((n for n in names if n == candidate or n.startswith(candidate)), candidate)
                return match
        return names[0] if names else config.OLLAMA_MODEL

    def complete(self, messages: list[dict[str, str]], timeout: int) -> ProviderResult:
        model = self._pick_model()
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }
        try:
            r = requests.post(f"{config.OLLAMA_BASE_URL}/api/chat", json=payload, timeout=timeout)
            r.raise_for_status()
        except requests.Timeout as exc:
            raise ProviderError("ollama", str(exc), "timeout") from exc
        except requests.RequestException as exc:
            raise ProviderError("ollama", str(exc), "provider_error") from exc
        data = r.json()
        content = (data.get("message") or {}).get("content") or ""
        if not content:
            raise ProviderError("ollama", "empty response", "invalid_output")
        return ProviderResult(provider="ollama", model=model, content=content, raw=data)


class OpenAICompatibleProvider(BaseProvider):
    def __init__(self, name: str, base_url: str, api_key: str, model: str, extra_headers: Optional[dict] = None):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.extra_headers = extra_headers or {}

    def is_available(self) -> bool:
        return bool(self.api_key)

    def complete(self, messages: list[dict[str, str]], timeout: int) -> ProviderResult:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if self.name == "openrouter":
            body["models"] = [self.model]
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=timeout)
            r.raise_for_status()
        except requests.Timeout as exc:
            raise ProviderError(self.name, str(exc), "timeout") from exc
        except requests.RequestException as exc:
            raise ProviderError(self.name, str(exc), "provider_error") from exc
        data = r.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(self.name, "invalid response shape", "invalid_output") from exc
        model_used = data.get("model") or self.model
        return ProviderResult(provider=self.name, model=model_used, content=content or "", raw=data)


def build_registry() -> dict[str, BaseProvider]:
    registry: dict[str, BaseProvider] = {
        "mock": MockProvider(),
        "ollama": OllamaProvider(),
        "mistral": OpenAICompatibleProvider(
            "mistral", "https://api.mistral.ai/v1", config.MISTRAL_API_KEY, config.MISTRAL_MODEL
        ),
        "groq": OpenAICompatibleProvider(
            "groq", "https://api.groq.com/openai/v1", config.GROQ_API_KEY, config.GROQ_MODEL
        ),
        "cerebras": OpenAICompatibleProvider(
            "cerebras", "https://api.cerebras.ai/v1", config.CEREBRAS_API_KEY, config.CEREBRAS_MODEL
        ),
        "openrouter": OpenAICompatibleProvider(
            "openrouter",
            "https://openrouter.ai/api/v1",
            config.OPENROUTER_API_KEY,
            config.OPENROUTER_MODEL,
            extra_headers={"HTTP-Referer": "http://localhost:8000", "X-Title": "Influencer Email AI"},
        ),
    }
    return registry


def reload_provider_keys() -> None:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
    config.OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", config.OLLAMA_BASE_URL).rstrip("/")
    config.OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", config.OLLAMA_MODEL)
    config.OLLAMA_FALLBACK_MODEL = os.environ.get("OLLAMA_FALLBACK_MODEL", getattr(config, "OLLAMA_FALLBACK_MODEL", "phi3:latest"))
    config.MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
    config.GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
    config.CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "").strip()
    config.OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
    config.AI_MOCK = os.environ.get("AI_MOCK", "").strip().lower() in {"1", "true", "yes", "on"}
    config.USE_LOCAL_AI = os.environ.get("USE_LOCAL_AI", "").strip().lower() in {"1", "true", "yes", "on"}
    config.PROVIDER_CHAIN = (["ollama"] if config.USE_LOCAL_AI else []) + ["mistral", "groq", "cerebras", "openrouter"]


def rebuild_registry() -> dict[str, BaseProvider]:
    global REGISTRY
    reload_provider_keys()
    REGISTRY = build_registry()
    return REGISTRY


REGISTRY = build_registry()
