from flask import Flask, request, jsonify
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configure OpenAI
api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# The model to use
MODEL = "gpt-4o-mini"

# root route
@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "This is Flask AI Server (OpenAI Edition)"}), 200

# health check
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "Flask AI running with OpenAI"})


# classify email
@app.route("/classify_email", methods=["POST"])
def classify_email():
    data = request.get_json()
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
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Email Body:\n{body}"}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        category = result.get("category", "spam")
        reason = result.get("reason", "No reason provided")
    except Exception as e:
        print(f"Classification error: {e}")
        category = "spam"
        reason = f"Error occurred: {str(e)}"

    return jsonify({"category": category, "reason": reason})


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

    history_text += f"Latest Sender Email or Instruction:\n{incoming_body}"

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": history_text}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
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
