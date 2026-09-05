from flask import Flask, jsonify, request

from config import AI_MOCK
from extract import extract_lead
from intent import classify_intent
from negotiation import negotiate
from rag import build_index, facts_for_prompt
from router import provider_health
from schemas import ExtractRequest, IntentRequest, NegotiationRequest, SpamRequest
from spam import classify_spam
from telemetry import log_event

app = Flask(__name__)


@app.get("/")
def index():
    return jsonify({"message": "Flask AI Gateway", "ai": True, "mock": AI_MOCK})


@app.get("/health")
@app.get("/api/ai/health")
def health():
    return jsonify({"status": "ok", **provider_health()})


@app.post("/classify_email")
@app.post("/ai/spam")
def classify_email():
    data = request.get_json(silent=True) or {}
    req = SpamRequest.model_validate(data)
    result = classify_spam(req, correlation_id=str(data.get("correlation_id") or ""))
    payload = result.model_dump()
    payload["category"] = "spam" if result.decision == "SPAM" else "useful"
    return jsonify(payload)


@app.post("/ai/intent")
def intent():
    data = request.get_json(silent=True) or {}
    result = classify_intent(IntentRequest.model_validate(data), correlation_id=str(data.get("correlation_id") or ""))
    return jsonify(result.model_dump())


@app.post("/ai/extract")
def extract():
    data = request.get_json(silent=True) or {}
    result = extract_lead(ExtractRequest.model_validate(data), correlation_id=str(data.get("correlation_id") or ""))
    return jsonify(result.model_dump())


@app.post("/generate_reply")
@app.post("/ai/negotiate")
def generate_reply():
    data = request.get_json(silent=True) or {}
    req = NegotiationRequest.model_validate(data)
    result = negotiate(req, correlation_id=str(data.get("correlation_id") or ""))
    payload = result.model_dump()
    payload["reply"] = result.reply_body
    return jsonify(payload)


@app.post("/ai/rag")
def rag_query():
    data = request.get_json(silent=True) or {}
    query = data.get("query") or data.get("body") or ""
    return jsonify({"facts": facts_for_prompt(query)})


@app.post("/ai/pipeline")
def pipeline():
    data = request.get_json(silent=True) or {}
    cid = str(data.get("correlation_id") or "")
    spam = classify_spam(SpamRequest.model_validate(data), correlation_id=cid)
    out = {"spam": spam.model_dump()}
    if spam.decision != "NOT_SPAM":
        log_event("pipeline_stopped", correlation_id=cid, reason=spam.decision)
        return jsonify(out)
    intent = classify_intent(IntentRequest.model_validate(data), correlation_id=cid)
    extract = extract_lead(ExtractRequest.model_validate(data), correlation_id=cid)
    out["intent"] = intent.model_dump()
    out["extract"] = extract.model_dump()
    neg_payload = dict(data)
    neg_payload["extracted"] = extract.model_dump()
    negotiation = negotiate(NegotiationRequest.model_validate(neg_payload), correlation_id=cid)
    out["negotiation"] = negotiation.model_dump()
    out["negotiation"]["reply"] = negotiation.reply_body
    return jsonify(out)


def boot():
    try:
        build_index()
    except Exception as exc:
        log_event("rag_boot_failed", error=str(exc))


boot()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
