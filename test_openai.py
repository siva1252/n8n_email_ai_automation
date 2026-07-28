import requests
import json

FLASK_AI_URL = "http://127.0.0.1:5000"

def test_classify():
    print("\n--- Testing Classification ---")
    email_text = "Hi, we are from XYZ Brand. We want to offer you a sponsorship for our new app. Are you interested?"
    response = requests.post(f"{FLASK_AI_URL}/classify_email", json={"body": email_text})
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_negotiate():
    print("\n--- Testing Negotiation ---")
    data = {
        "body": "We can offer you 2000 rupees for one post. This is our final offer.",
        "chat_history": [
            {"role": "client", "content": "Hi, we want a collab."},
            {"role": "ai", "content": "Sure, what is your budget?"}
        ],
        "min_price": 4000,
        "goal_price": 5000
    }
    response = requests.post(f"{FLASK_AI_URL}/generate_reply", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

if __name__ == "__main__":
    try:
        test_classify()
        test_negotiate()
    except Exception as e:
        print(f"Test failed: {e}")
