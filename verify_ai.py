import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv(dotenv_path="flask_ai/.env")

api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-1.5-flash")

def check_email(text):
    system_instruction = """You are an Expert Business Assistant. Analyze the email below. Determine if it is a Business Collaboration Inquiry (Brand deal, sponsorship, PR) or a Personal/Spam email. Return JSON in the format: {"category": "useful"} ONLY if it involves a professional negotiation, or {"category": "spam"} for personal chats, family emails, or random newsletters. Always output valid JSON only."""
    prompt = f"{system_instruction}\n\nEmail Body:\n{text}"
    
    try:
        response = model.generate_content(prompt)
        print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    email_text = "Hi this is siva from ICICI Bank we need collaboration with you for swipesavvu things what you intreset"
    check_email(email_text)
