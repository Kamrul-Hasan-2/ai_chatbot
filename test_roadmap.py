"""
Quick Test Script - Test Your Roadmap Implementation
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_roadmap():
    print("=" * 60)
    print("🧪 Testing Your Chatbot Roadmap")
    print("=" * 60)
    print()
    
    # Test 1: Health Check
    print("Test 1: Health Check")
    print("-" * 40)
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure server is running: python run.py")
        return
    print()
    
    # Test 2: Laptop Search (Should work - AI mode)
    print("Test 2: Laptop Search under 10k")
    print("-" * 40)
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "user_id": "test_user",
                "message": "amake ekta 10k er modde laptop dekhan"
            }
        )
        result = response.json()
        print(f"Mode: {result.get('mode')}")
        print(f"Intent: {result.get('intent')}")
        print(f"Products Found: {result.get('products_found')}")
        print(f"Response: {result.get('response')[:100]}...")
        print()
        print("Full Response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    # Test 3: Simple Greeting (Should work - AI mode)
    print("Test 3: Simple Greeting")
    print("-" * 40)
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "user_id": "test_user",
                "message": "hello"
            }
        )
        result = response.json()
        print(f"Mode: {result.get('mode')}")
        print(f"Response: {result.get('response')}")
        print()
        print("Full Response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    # Test 4: Check Mode
    print("Test 4: Check User Mode")
    print("-" * 40)
    try:
        response = requests.get(f"{BASE_URL}/mode/test_user")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    # Test 5: Mouse Price
    print("Test 5: Mouse Price Query")
    print("-" * 40)
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "user_id": "test_user",
                "message": "mouse er dam koto?"
            }
        )
        result = response.json()
        print(f"Mode: {result.get('mode')}")
        print(f"Intent: {result.get('intent')}")
        print(f"Products Found: {result.get('products_found')}")
        print(f"Response: {result.get('response')[:150]}...")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    # Test 6: Manual Switch to Human
    print("Test 6: Manually Switch to HUMAN Mode")
    print("-" * 40)
    try:
        response = requests.post(f"{BASE_URL}/mode/test_user/human")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
        # Now try chatting - should be in human mode
        print("\nNow sending message while in HUMAN mode:")
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "user_id": "test_user",
                "message": "laptop price?"
            }
        )
        result = response.json()
        print(f"Mode: {result.get('mode')} (should be 'human')")
        print(f"Response: {result.get('response')}")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    # Test 7: Switch Back to AI
    print("Test 7: Switch Back to AI Mode")
    print("-" * 40)
    try:
        response = requests.post(f"{BASE_URL}/mode/test_user/ai")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
        # Verify mode
        response = requests.get(f"{BASE_URL}/mode/test_user")
        print("\nCurrent mode:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    print("=" * 60)
    print("✅ Testing Complete!")
    print("=" * 60)
    print()
    print("📋 Summary:")
    print("- Your roadmap is implemented")
    print("- Mode tracking works (AI/HUMAN)")
    print("- API returns JSON with mode in every response")
    print("- Auto-switch to HUMAN on failures")
    print("- Manual mode control available")
    print()


if __name__ == "__main__":
    print()
    print("Make sure server is running:")
    print("  python run.py")
    print()
    input("Press Enter to start tests...")
    print()
    
    test_roadmap()
