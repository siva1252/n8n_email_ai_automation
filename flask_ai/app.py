from flask import Flask, request, jsonify
import os
import json
import re
from pathlib import Path
from sarvamai import SarvamAI
from dotenv import load_dotenv

# Prefer project-root .env (Docker also injects via compose env_file)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

app = Flask(__name__)

api_key = os.environ.get("SARVAM_API_KEY")
client = SarvamAI(api_subscription_key=api_key) if api_key else None

# Sarvam chat models: sarvam-30b (faster) or sarvam-105b (stronger)
MODEL = os.environ.get("SARVAM_MODEL", "sarvam-30b")


def _extract_json(text: str) -> dict:
    """Parse JSON from model output, including fenced ```json blocks."""
    text = (text or "").strip()
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

    raise ValueError(f"No JSON object found in model response: {text[:200]}")


def _chat(system_instruction: str, user_content: str) -> dict:
    if not client:
        raise RuntimeError("SARVAM_API_KEY is not set")

    response = client.chat.completions(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content
    return _extract_json(content)


@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "This is Flask AI Server (Sarvam Edition)"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "Flask AI running with Sarvam",
        "model": MODEL,
        "api_key_configured": bool(api_key),
    })


@app.route("/classify_email", methods=["POST"])
def classify_email():
    data = request.get_json() or {}
    body = data.get("body", "")

    system_instruction = """You are an Expert Business Assistant. Analyze the email below.

Your goal is to identify Business Collaboration Inquiries (Brand deals, sponsorships, PR, promotion requests, partnership offers).

Even if the email is short, has spelling errors, or comes from an unknown company, if it mentions "promotion", "collab", "sponsorship", "deal", or "partnership", it should be considered "useful".

Return JSON in the format:
{
  "category": "useful",
  "reason": "Brief explanation why"
}

ONLY use "spam" for obvious newsletters, personal family chats, or random non-business garbage. If in doubt, mark as "useful" so the creator doesn't miss money. Always output valid JSON only."""

    try:
        result = _chat(system_instruction, f"Email Body:\n{body}")
        category = result.get("category", "spam")
        reason = result.get("reason", "No reason provided")
    except Exception as e:
        print(f"Classification error: {e}")
        category = "spam"
        reason = f"Error occurred: {str(e)}"

    return jsonify({"category": category, "reason": reason})


@app.route("/generate_reply", methods=["POST"])
def generate_reply():
    data = request.get_json() or {}
    min_price = data.get("min_price", 4000)
    goal_price = data.get("goal_price", 5000)
    chat_history = data.get("chat_history", [])
    incoming_body = data.get("body", "")
    action = data.get("action", "negotiate")

    if action == "accept":
        system_instruction = """You are a Business Manager. The exact terms of the deal have been accepted by the creator. Write a professional, polite email to the brand saying that we accept the deal and are excited to begin our collaboration. Output JSON exactly in this format: {"reply": "...", "decision": "accepted"}"""
    elif action == "reject":
        system_instruction = """You are a Business Manager. The creator has decided to decline the brand's offer. Write a professional, polite email to the brand stating that we do not have the time for this project right now, apologize for the inconvenience, and suggest that we might collaborate on another project in the future. Output JSON exactly in this format: {"reply": "...", "decision": "rejected"}"""
    else:
        system_instruction = f"""You are a shrewd Business Manager gently but firmly negotiating an email deal on behalf of a creator.
You negotiate just like a real human.
Rules:
- If they offer a low price (e.g. ₹3500), counter-offer high (e.g. ₹5000 or ₹6000).
- If they offer a high price initially (e.g. ₹10000), counter-offer even higher (e.g. ₹15000).
- If they hover near the minimum acceptable price (₹{min_price}), push them higher (e.g. to ₹{goal_price}) but keep the conversation open.
- Try to secure the best deal possible. Always try to negotiate their first offer.
- If they absolutely stand firm on a price at or above ₹{min_price} after some back-and-forth, set the decision status to 'ready_to_close'.
Output your response as JSON in this exact format:
{{
  "reply": "Your negotiation reply text here...",
  "decision": "negotiating"
}}
Valid decision values: "negotiating" or "ready_to_close". Always output valid JSON only."""

    history_text = "Chat History:\n"
    for msg in chat_history:
        role = "Sender" if msg.get("role") == "client" else "Creator (You)"
        history_text += f"{role}: {msg.get('content')}\n\n"

    history_text += f"Latest Sender Email or Instruction:\n{incoming_body}"

    try:
        result = _chat(system_instruction, history_text)
        reply = result.get("reply", "I need some more time to review this offer.")
        decision = result.get(
            "decision",
            action if action in ["accept", "reject"] else "negotiating",
        )
    except Exception as e:
        print(f"Reply error: {e}")
        reply = "We are reviewing your inquiry and will get back to you shortly."
        decision = action if action in ["accept", "reject"] else "negotiating"

    return jsonify({
        "reply": reply.strip(),
        "decision": decision,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
