import requests
import json

FLASK_AI_URL = "http://127.0.0.1:5000"

def test_classify(text):
    print(f"Testing Classification for: {text}")
    try:
        response = requests.post(f"{FLASK_AI_URL}/classify_email", json={
            "body": text
        })
        if response.status_code == 200:
            print("AI Result:", response.json())
        else:
            print("Error:", response.status_code, response.text)
    except Exception as e:
        print("Connection Failed:", e)

if __name__ == "__main__":
    email_text = "Hi this is siva from ICICI Bank we need collaboration with you for swipesavvu things what you intreset"
    test_classify(email_text)
