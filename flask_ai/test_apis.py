"""
Flask APIs ni test cheyadaniki script
Run cheyadaniki: python test_apis.py
"""

import requests
import json

# Flask server URL
BASE_URL = "http://localhost:5000"

def test_root():
    """Root endpoint test"""
    print("\n" + "="*50)
    print("1. Testing GET /")
    print("="*50)
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_health():
    """Health check endpoint test"""
    print("\n" + "="*50)
    print("2. Testing GET /health")
    print("="*50)
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_classify_email():
    """Classify email endpoint test"""
    print("\n" + "="*50)
    print("3. Testing POST /classify_email")
    print("="*50)
    
    # Test case 1: Useful email
    print("\n--- Test Case 1: Useful email (collab) ---")
    try:
        data = {"body": "Hi, I want to collaborate with you"}
        response = requests.post(f"{BASE_URL}/classify_email", json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Request: {json.dumps(data, indent=2)}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test case 2: Spam email
    print("\n--- Test Case 2: Spam email ---")
    try:
        data = {"body": "Buy cheap products now!"}
        response = requests.post(f"{BASE_URL}/classify_email", json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Request: {json.dumps(data, indent=2)}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_generate_reply():
    """Generate reply endpoint test"""
    print("\n" + "="*50)
    print("4. Testing POST /generate_reply")
    print("="*50)
    
    # Test case 1: With custom price
    print("\n--- Test Case 1: With custom price ---")
    try:
        data = {"min_price": 10000}
        response = requests.post(f"{BASE_URL}/generate_reply", json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Request: {json.dumps(data, indent=2)}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test case 2: With default price
    print("\n--- Test Case 2: With default price (no min_price) ---")
    try:
        data = {}
        response = requests.post(f"{BASE_URL}/generate_reply", json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Request: {json.dumps(data, indent=2)}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    """Main function to run all tests"""
    print("\n" + "="*50)
    print("FLASK API TESTING")
    print("="*50)
    print(f"\nTesting APIs at: {BASE_URL}")
    print("\nNote: Make sure Flask server is running!")
    print("Run: python app.py")
    
    results = []
    
    # Run all tests
    results.append(("Root (/)", test_root()))
    results.append(("Health (/health)", test_health()))
    results.append(("Classify Email (/classify_email)", test_classify_email()))
    results.append(("Generate Reply (/generate_reply)", test_generate_reply()))
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")
    
    print("\n" + "="*50)

if __name__ == "__main__":
    main()

