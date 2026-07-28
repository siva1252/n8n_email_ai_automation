import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="flask_ai/.env")

api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

for m in genai.list_models():
  if 'generateContent' in m.supported_generation_methods:
    print(m.name)
