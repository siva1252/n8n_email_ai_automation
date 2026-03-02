from flask import Flask, request, jsonify
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configure Gemini
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# Initialize models
generation_config = {"response_mime_type": "application/json"}
classify_model = genai.GenerativeModel("gemini-1.5-flash", generation_config=generation_config)
reply_model = genai.GenerativeModel("gemini-1.5-flash", generation_config=generation_config)


# root route
@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "This is Flask AI Server"}), 200

# health check
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "Flask AI running"})


# classify email
@app.route("/classify_email", methods=["POST"])
def classify_email():
    data = request.get_json()
    body = data.get("body", "")

    system_instruction = """You are an Expert Business Assistant. Analyze the email below. Determine if it is a Business Collaboration Inquiry (Brand deal, sponsorship, PR) or a Personal/Spam email. Return JSON in the format: {"category": "useful"} ONLY if it involves a professional negotiation, or {"category": "spam"} for personal chats, family emails, or random newsletters. Always output valid JSON only."""
    
    prompt = f"{system_instruction}\n\nEmail Body:\n{body}"
    
    try:
        response = classify_model.generate_content(prompt)
        result = json.loads(response.text)
        category = result.get("category", "spam")
    except Exception as e:
        print(f"Classification error: {e}")
        category = "spam"

    return jsonify({"category": category})


# generate reply
@app.route("/generate_reply", methods=["POST"])
def generate_reply():
    data = request.get_json()
    min_price = data.get("min_price", 4000)
    goal_price = data.get("goal_price", 5000)
    chat_history = data.get("chat_history", []) # Expected list of dicts: {"role": "client"/"ai", "content": "..."}
    incoming_body = data.get("body", "")
    action = data.get("action", "negotiate") # "negotiate", "accept", "reject"

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
  "decision": "negotiating" // or "ready_to_close"
}}
"""

    history_text = "Chat History:\n"
    for msg in chat_history:
        role = "Sender" if msg.get("role") == "client" else "Creator (You)"
        history_text += f"{role}: {msg.get('content')}\n\n"

    history_text += f"Latest Sender Email or Instruction:\n{incoming_body}\n\nPlease generate the next reply and determine the status based on the system instructions."

    prompt = f"{system_instruction}\n\n{history_text}"

    try:
        response = reply_model.generate_content(prompt)
        result = json.loads(response.text)
        reply = result.get("reply", "I need some more time to review this offer.")
        decision = result.get("decision", action if action in ["accept", "reject"] else "negotiating")
    except Exception as e:
        print(f"Reply error: {e}")
        reply = "We are reviewing your inquiry and will get back to you shortly."
        decision = action if action in ["accept", "reject"] else "negotiating"

    return jsonify({
        "reply": reply.strip(),
        "decision": decision
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
