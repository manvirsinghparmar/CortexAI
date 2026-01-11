"""Quick API test script."""
import requests
import json

BASE_URL = "http://localhost:8000"
API_KEY = "dev-key-1"

def test_health():
    print("Testing /health...")
    r = requests.get(f"{BASE_URL}/health")
    print(f"Status: {r.status_code}")
    print(f"Response: {r.json()}\n")

def test_chat():
    print("Testing /v1/chat...")
    r = requests.post(
        f"{BASE_URL}/v1/chat",
        headers={"X-API-Key": API_KEY},
        json={
            "prompt": "Say 'Hello, FastAPI works!' in one sentence",
            "provider": "openai",
            "model": "gpt-4o-mini"
        }
    )
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Response: {data['text'][:100]}...")
        print(f"Tokens: {data['token_usage']}")
        print(f"Cost: ${data['estimated_cost']:.6f}\n")
    else:
        print(f"Error: {r.text}\n")

def test_compare():
    print("Testing /v1/compare...")
    r = requests.post(
        f"{BASE_URL}/v1/compare",
        headers={"X-API-Key": API_KEY},
        json={
            "prompt": "What is 2+2?",
            "targets": [
                {"provider": "openai", "model": "gpt-4o-mini"},
                {"provider": "gemini"}
            ]
        }
    )
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Success: {data['success_count']}/{len(data['responses'])}")
        print(f"Total Cost: ${data['total_cost']:.6f}\n")
    else:
        print(f"Error: {r.text}\n")

def test_auth():
    print("Testing auth failure...")
    r = requests.post(
        f"{BASE_URL}/v1/chat",
        headers={"X-API-Key": "invalid"},
        json={"prompt": "test", "provider": "openai"}
    )
    print(f"Status: {r.status_code} (should be 401)")
    print(f"Error: {r.json()['detail']}\n")

if __name__ == "__main__":
    print("=== FastAPI Tests ===\n")
    print("Start server first: python run_server.py\n")

    try:
        test_health()
        test_auth()
        # Uncomment to test actual API calls (requires API keys)
        # test_chat()
        # test_compare()
    except requests.exceptions.ConnectionError:
        print("ERROR: Server not running. Start with: python run_server.py")
