"""
Quick Test: Verify "hi" returns database response
Expected: "আসসালামু-আলাইকুম স্যার, কোন বিষয়ে জানতে চাচ্ছেন?"
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_greeting():
    """Test greeting message"""
    print("\n" + "="*60)
    print("🧪 Testing: hi → Database Response")
    print("="*60)
    
    # Reset to AI mode
    user_id = "test_user"
    reset = requests.post(f"{BASE_URL}/mode/{user_id}/ai")
    print(f"✅ Reset to AI: {reset.json()}")
    
    # Send "hi"
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "user_id": user_id,
            "message": "hi"
        }
    )
    
    data = response.json()
    
    print(f"\n📨 Message: {data.get('message')}")
    print(f"🎯 Intent: {data.get('intent')}")
    print(f"📍 Mode: {data.get('mode')}")
    print(f"🤖 Response: {data.get('response')}")
    
    expected = "আসসালামু-আলাইকুম স্যার, কোন বিষয়ে জানতে চাচ্ছেন?"
    
    if expected in data.get('response', ''):
        print("\n✅ SUCCESS: Correct database response returned!")
    else:
        print(f"\n❌ FAILED: Expected '{expected}'")
        print(f"Got: {data.get('response')}")
    
    if data.get('mode') == 'ai':
        print("✅ Mode: AI (not sent to human) ✓")
    else:
        print("❌ Mode: HUMAN (should be AI)")
    
    return data

if __name__ == "__main__":
    try:
        # Check health first
        health = requests.get(f"{BASE_URL}/health").json()
        print("\n🏥 Health Check:")
        print(f"  Status: {health.get('status')}")
        print(f"  Database: {health.get('database_responses')} responses")
        print(f"  API: {health.get('api_configured')}")
        print(f"  Groq: {health.get('groq_available')}")
        
        # Test greeting
        test_greeting()
        
        # Test other greetings
        for msg in ["hello", "আসসালামু আলাইকুম", "hlw", "hai"]:
            print(f"\n{'='*60}")
            print(f"Testing: {msg}")
            print('='*60)
            
            response = requests.post(
                f"{BASE_URL}/chat",
                json={"user_id": "test", "message": msg}
            )
            data = response.json()
            print(f"Response: {data.get('response')[:80]}...")
            print(f"Mode: {data.get('mode')} | Intent: {data.get('intent')}")
        
        print("\n" + "="*60)
        print("✅ All greeting tests completed!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure server is running: python run.py")
