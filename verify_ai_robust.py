import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv(dotenv_path="flask_ai/.env")

api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
if not models:
    print("No models found")
    exit(1)

model_name = models[0]
print(f"Using model: {model_name}")
model = genai.GenerativeModel(model_name)

def check_email(text):
    system_instruction = """You are an Expert Business Assistant. Analyze the email below. Determine if it is a Business Collaboration Inquiry (Brand deal, sponsorship, PR) or a Personal/Spam email. Return JSON in the format: {"category": "useful"} ONLY if it involves a professional negotiation, or {"category": "spam"} for personal chats, family emails, or random newsletters. Always output valid JSON only."""
    prompt = f"{system_instruction}\n\nEmail Body:\n{text}"
    
    try:
        response = model.generate_content(prompt)
        print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    email_text = "We need collaration of your posts and things what you have any time to do this thing"
    check_email(email_text)
