from __future__ import annotations

import time
from typing import Any, Optional

import config
import provider_registry
from provider_registry import ProviderError, extract_json
from telemetry import log_event


class RouterError(Exception):
    def __init__(self, message: str, attempts: list[dict[str, Any]]):
        super().__init__(message)
        self.attempts = attempts
        self.error_type = "AI_UNAVAILABLE"


def complete_json(
    task: str,
    system: str,
    user: str,
    correlation_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the provider chain. Returns (parsed_json, meta). Raises RouterError if all fail."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    attempts: list[dict[str, Any]] = []
    chain = ["mock"] if config.AI_MOCK else list(config.PROVIDER_CHAIN)

    for name in chain:
        provider = provider_registry.REGISTRY.get(name)
        if provider is None or not provider.is_available():
            attempts.append({"provider": name, "status": "skipped", "reason": "unavailable"})
            continue
        timeout = config.PRIMARY_TIMEOUT if name in {"ollama", "mistral"} else config.FALLBACK_TIMEOUT
        retries = 0 if name == "ollama" else (config.MAX_RETRIES if name != "mock" else 0)
        for attempt in range(retries + 1):
            started = time.perf_counter()
            try:
                result = provider.complete(messages, timeout=timeout)
                parsed = extract_json(result.content)
                latency_ms = int((time.perf_counter() - started) * 1000)
                meta = {
                    "provider": result.provider,
                    "model": result.model,
                    "latency_ms": latency_ms,
                    "task": task,
                    "attempts": attempts
                    + [{"provider": name, "status": "success", "attempt": attempt, "latency_ms": latency_ms}],
                }
                log_event(
                    "ai_success",
                    correlation_id=correlation_id,
                    task=task,
                    provider=result.provider,
                    model=result.model,
                    latency_ms=latency_ms,
                )
                return parsed, meta
            except (ProviderError, ValueError, TypeError) as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                error_type = getattr(exc, "error_type", "invalid_output")
                attempts.append(
                    {
                        "provider": name,
                        "status": "error",
                        "attempt": attempt,
                        "error_type": error_type,
                        "latency_ms": latency_ms,
                    }
                )
                log_event(
                    "ai_attempt_failed",
                    correlation_id=correlation_id,
                    task=task,
                    provider=name,
                    error_type=error_type,
                    latency_ms=latency_ms,
                )
    raise RouterError("All AI providers failed", attempts)


def provider_health() -> dict[str, Any]:
    provider_registry.rebuild_registry()
    status = {}
    for name in ["ollama", "mistral", "groq", "cerebras", "openrouter", "mock"]:
        provider = provider_registry.REGISTRY.get(name)
        available = bool(provider and provider.is_available())
        item: dict[str, Any] = {"available": available, "configured": available}
        if name == "ollama" and provider:
            item["base_url"] = config.OLLAMA_BASE_URL
            item["preferred_model"] = config.OLLAMA_MODEL
        if name == "openrouter":
            item["model"] = config.OPENROUTER_MODEL
            item["free_route_only"] = True
        if name in {"mistral", "groq", "cerebras"}:
            item["configured"] = bool(getattr(config, f"{name.upper()}_API_KEY", ""))
        if name == "openrouter":
            item["configured"] = bool(config.OPENROUTER_API_KEY)
        status[name] = item
    return {
        "status": "ok",
        "ai": True,
        "chain_length": len([n for n in config.PROVIDER_CHAIN if status.get(n, {}).get("configured") or status.get(n, {}).get("available")]),
        "mock": config.AI_MOCK,
    }
